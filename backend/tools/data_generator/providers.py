"""
LLM Provider 接口

用户需要自己实现一个 LLMProvider 子类来连接大模型。

快速开始：
  1. 复制下方 OpenAIProvider 模板，填入你的 API Key
  2. 运行：python -m backend.tools.data_generator.main --task all
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """
    LLM 调用抽象接口
    ─────────────────
    用户需实现 generate() 方法，接收提示文本，返回解析后的结构化数据。

    实现示例见下方 OpenAIProvider 或自定义 provider。
    """

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        调用大模型，返回原始响应文本。

        Args:
            prompt: 完整的生成提示（已在 pipeline 中构建好）
            **kwargs: 额外参数（temperature、max_tokens 等）

        Returns:
            LLM 返回的原始文本（JSON 字符串或纯文本）

        Raises:
            RuntimeError: 调用失败时抛出
        """
        ...

    @abstractmethod
    def parse_response(self, raw: str) -> Any:
        """
        将 LLM 原始响应解析为 Python 数据结构。

        Args:
            raw: generate() 返回的原始文本

        Returns:
            解析后的 Python 对象（通常为 list[dict] 或 dict）
        """
        ...


# ──────────────────────────────────────────────
# 预置适配器模板
# ──────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    """
    OpenAI 兼容 API 适配器

    使用前设置环境变量：
      export OPENAI_API_KEY="sk-xxx"
      export OPENAI_BASE_URL="https://api.openai.com/v1"   # 可选，默认 OpenAI
      export LLM_MODEL="gpt-4o"                            # 可选，默认 gpt-4o

    或直接在下方 __init__ 中填入。
    """

    def __init__(
        self,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        import os

        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.temperature = temperature
        self.max_tokens = max_tokens

        if not self.api_key:
            raise ValueError(
                "未设置 OPENAI_API_KEY。\n"
                "请通过环境变量或 OpenAIProvider(api_key='...') 传入。"
            )

    def generate(self, prompt: str, **kwargs) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个 CityFlow 旅游路线规划系统的数据生成器。"
                        "严格按照用户要求的 JSON 格式输出，不包含任何额外说明。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""

    def parse_response(self, raw: str) -> Any:
        """尝试解析 JSON，失败时抛出详细错误"""
        return _parse_json(raw)


# ──────────────────────────────────────────────
# LongCat (OpenAI 格式 + JSON mode) 适配器
# ──────────────────────────────────────────────

class LongCatProvider(LLMProvider):
    """
    LongCat 平台适配器（使用 OpenAI 格式 + JSON mode）

    实测 LongCat 支持 OpenAI 格式的 response_format={"type": "json_object"},
    该模式强制模型输出合法 JSON，大幅提高数据生成可靠性。

    API 地址: https://api.longcat.chat/openai/v1/chat/completions
    模型:    LongCat-Flash-Lite

    使用方式:
      python -m backend.tools.data_generator.main \\
        --provider LongCatProvider \\
        --provider-args '{"api_key": "ak_2C232w6Wj58e9Pw8a86gd2id76U58"}'
    """

    SYSTEM_PROMPT = (
        "你是一个 CityFlow 旅游路线规划系统的数据生成专家。\n"
        "你的任务是根据用户要求生成指定格式的 JSON 数据。\n"
        "输出格式必须是 JSON 对象，其中包含一个名为 \"data\" 的数组字段。\n"
        "每条数据必须包含输出格式中列出的所有字段，不得遗漏。\n"
        "只输出 JSON，不要包含任何额外说明。"
    )

    def __init__(
        self,
        api_key: str = "",
        model: str = "LongCat-Flash-Lite",
        base_url: str = "https://api.longcat.chat/openai",
        temperature: float = 0.3,
        max_tokens: int = 64000,
    ):
        import os

        self.api_key = api_key or os.getenv("LONGCAT_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "LongCat-Flash-Lite")
        self.base_url = base_url or os.getenv("LONGCAT_BASE_URL", "https://api.longcat.chat/openai")
        self.temperature = temperature
        self.max_tokens = max_tokens

        if not self.api_key:
            raise ValueError(
                "未设置 LongCat API Key。\n"
                "请通过环境变量 LONGCAT_API_KEY 或 LongCatProvider(api_key='...') 传入。"
            )

    def generate(self, prompt: str, **kwargs) -> str:
        """
        调用 LongCat API（OpenAI 格式 + JSON mode）。

        使用 response_format={"type": "json_object"} 确保输出合法 JSON。
        JSON mode 要求 system prompt 包含"json"关键词并引导模型输出 JSON。
        """
        import httpx

        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=300.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # OpenAI 响应格式: { "choices": [{"message": {"content": "..."}}]}
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")

            # 检测截断
            finish_reason = choice.get("finish_reason", "")
            if finish_reason == "length":
                # 截断了，记录警告但继续尝试解析
                pass

            if not content:
                raise RuntimeError(
                    f"LLM 返回空内容: {json.dumps(data, ensure_ascii=False)[:300]}"
                )
            return content

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"LongCat API 返回错误 (HTTP {e.response.status_code}): "
                f"{e.response.text[:500]}"
            )
        except httpx.RequestError as e:
            raise RuntimeError(f"LongCat API 请求失败: {e}")

    def parse_response(self, raw: str) -> Any:
        """
        解析 JSON mode 的响应。

        JSON mode 强制模型输出 `{"data": [...]}` 或直接数组格式。
        """
        raw = raw.strip()
        parsed = _parse_json(raw)

        # JSON mode 有时返回 {"data": [...]} 结构
        if isinstance(parsed, dict):
            if "data" in parsed:
                return parsed["data"]
            # 尝试找第一个数组值
            for v in parsed.values():
                if isinstance(v, list):
                    return v
            # 如果只有单个对象，包装成列表
            return [parsed]

        return parsed


# ──────────────────────────────────────────────
# 共享工具函数
# ──────────────────────────────────────────────

def _parse_json(raw: str) -> Any:
    """安全的 JSON 解析，兼容 LLM 可能的多余包裹和截断"""
    raw = raw.strip()
    # 移除 ```json ... ``` 包裹
    if raw.startswith("```"):
        for prefix in ("```json\n", "```json\r\n", "```\n", "```\r\n", "```"):
            if raw.startswith(prefix):
                raw = raw.removeprefix(prefix)
                break
        for suffix in ("\n```", "\r\n```"):
            if raw.endswith(suffix):
                raw = raw.removesuffix(suffix)
                break
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 截断恢复：尝试从末尾往前找合法的 JSON 结束点
        pass

    # 截断恢复策略：找到最后一个完整的 } 或 ]，截断后重试
    for end_char in ("\n]", "}]", "]}", "]", "}"):
        idx = raw.rfind(end_char)
        if idx > 0:
            candidate = raw[: idx + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise RuntimeError(
        f"LLM 返回的 JSON 解析失败（含截断恢复尝试）\n"
        f"原始响应前 300 字符:\n{raw[:300]}"
    )


# ──────────────────────────────────────────────
# Stub Provider（测试用，返回示例数据）
# ──────────────────────────────────────────────

class StubProvider(LLMProvider):
    """
    桩 Provider：返回硬编码的示例数据。
    用于在不连接 LLM 时测试管线流程。
    """

    def __init__(self, sample_data: list | dict | None = None):
        self.sample_data = sample_data or self._default_sample()

    def _default_sample(self) -> list[dict]:
        return [
            {
                "poi_id": "poi_00001",
                "poi_name": "珠海渔女",
                "city": "珠海",
                "category": "文化",
                "highlights": [
                    {
                        "id": "hl_poi_00001a",
                        "name": "海滨观景台",
                        "type": "view",
                        "description": "俯瞰情侣路海岸线，适合拍照发呆",
                        "duration_min": 20,
                        "emotion_boost": {"tranquility": 0.3, "excitement": 0.1},
                    },
                    {
                        "id": "hl_poi_00001b",
                        "name": "渔女雕像打卡",
                        "type": "photo",
                        "description": "珠海地标，必拍景点，早晚光线最佳",
                        "duration_min": 10,
                        "emotion_boost": {"excitement": 0.2},
                    },
                    {
                        "id": "hl_poi_00001c",
                        "name": "情侣路漫步",
                        "type": "walk",
                        "description": "沿着海岸线散步，感受海风",
                        "duration_min": 40,
                        "emotion_boost": {"tranquility": 0.4, "physical_demand": 0.2},
                    },
                ],
            },
        ]

    def generate(self, prompt: str, **kwargs) -> str:
        return json.dumps(self.sample_data, ensure_ascii=False)

    def parse_response(self, raw: str) -> Any:
        return json.loads(raw)
