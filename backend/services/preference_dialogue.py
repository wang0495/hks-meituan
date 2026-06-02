"""CityFlow 偏好对话与需求向量提取模块。

职责:
1. extract_demand_vector() — LLM 从对话中提取需求向量（语义方向，不出数值）
2. ask_preference_question() — LLM 针对缺失维度生成口语化追问
3. analyze_user_response() — LLM 从用户回答中提取偏好值

原则:
- LLM 只输出语义方向（0~1 浮点数），不出求解器权重
- 每轮只问 1 个维度
- 低置信度的维度标记出来供追问
"""

from __future__ import annotations

import json
import logging
import os
import re

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Prompt 模板
# ---------------------------------------------------------------------------

_DEMAND_EXTRACT_PROMPT = """你是 CityFlow 出行规划助手。用户用自然语言描述出行需求，
你需要提取语义"需求向量"。注意：只提取方向和置信度，不出具体数值权重。

需求向量各维度含义：
- efficiency_seeking (0~1): 是否在意效率/赶时间？0=完全不赶, 1=争分夺秒
- excitement_seeking (0~1): 是否想要兴奋刺激的体验？0=不需要, 1=非常想要
- tranquility_seeking (0~1): 是否想要宁静放松？0=不需要, 1=非常需要
- budget_sensitivity (0~1): 预算敏感度？0=不在意钱, 1=非常在意
- novelty_seeking (0~1): 是否想尝试新东西？0=老地方也行, 1=一定要新鲜的
- social_desire (0~1): 社交需求？0=想独处, 1=想热闹
- physical_energy (0~1): 体力意愿？0=不想动, 1=体力充沛

对话历史：
{dialogue_history}

输出 JSON 格式（只输出 JSON，不要其他文字）：
{{
  "demand_vector": {{
    "efficiency_seeking": 0.5,
    "excitement_seeking": 0.3,
    ...
  }},
  "_confidence": {{
    "efficiency_seeking": 0.9,
    ...
  }},
  "emotion_need": "放松/新鲜感/恢复/null",
  "notes": "对该用户的简要分析"
}}

规则：
- 置信度 < 0.4 的维度应被标记为待追问
- 如果发现情感信号词（烦/无聊/累/压抑等），填入 emotion_need
- 信息不足的维度取 0.5 中性值，置信度设低
"""

_QUESTION_PROMPT = """你是 CityFlow 出行规划助手，正在和用户聊天了解出行偏好。

已知偏好：
{known_prefs}

缺失维度（需要问的）：
{missing_dimensions}

用户刚才说了：{last_user_input}

请选择 1 个缺失维度，生成一句非常口语化、自然的追问。
规则：
- 一次只问 1 个维度！！！
- 语气要像朋友聊天，不能像问卷
- 如果用户刚说了相关内容，不要重复问

举例：
  budget → "预算方面～大概人均多少比较舒服？"
  pace → "你们今天是打算特种兵式刷景点，还是懒洋洋闲逛一天？"
  tranquility_seeking → "偏向安静治愈的氛围，还是热闹有活力的？"
  physical_energy → "体力怎么样？乐意多走走路还是想轻松点？"

输出 JSON（只输出 JSON）：
{"question": "问句", "dimension": "维度名", "reason": "为什么问这个"}
"""

_ANALYZE_RESPONSE_PROMPT = """用户对出行偏好的追问做了回答。

追问的维度：{dimension}
用户的回答：{user_response}

请解析用户在这个维度上的偏好强度（0~1），以及情感需求。
输出 JSON（只输出 JSON）：
{{
  "value": 0~1,
  "confidence": 0~1,
  "emotion_need": "放松/新鲜感/恢复/null"
}}

规则：
- "随便""都行""不知道" → value=0.5, confidence=0.2
- "不要太X" → 取对应的低值, 如 "不要太累" → physical_energy=0.2
- "有点X" → 取中高值, 如 "有点累" → physical_energy=0.3
- 语气词（吧/啊/呢）不影响判断
"""


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------

_client: AsyncOpenAI | None = None

# Generic tool schema for Qwen models — avoids response_format's NotEnoughCvError
_GENERIC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_result",
            "description": "Submit the structured analysis result",
            "parameters": {"type": "object"},
        },
    },
]
_GENERIC_TOOL_CHOICE = {"type": "function", "function": {"name": "submit_result"}}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        from backend.config.settings import get_settings
        s = get_settings()
        _client = AsyncOpenAI(base_url=s.llm.base_url, api_key=s.llm.api_key)
    return _client


def _is_qwen() -> bool:
    from backend.config.settings import get_settings
    return "qwen" in get_settings().llm.model.lower()


async def _call_llm(system: str, user: str, max_tokens: int = 300) -> dict | None:
    """调用 LLM 返回 JSON。带重试。"""
    client = _get_client()
    import asyncio as _aio

    model = os.getenv("LLM_MODEL", "deepseek-chat")
    kwargs: dict = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    use_tools = False
    if "qwen" in model.lower():
        use_tools = True
        kwargs["tools"] = _GENERIC_TOOLS
        kwargs["tool_choice"] = _GENERIC_TOOL_CHOICE
    else:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(5):
        try:
            resp = await client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            if use_tools and msg.tool_calls:
                raw = msg.tool_calls[0].function.arguments or ""
            else:
                raw = msg.content or ""
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            if attempt < 4:
                await _aio.sleep(2)
            else:
                logger.warning("[PreferenceDialogue] LLM 调用失败(5次): %s", e)
    return None


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


async def extract_demand_vector(
    user_input: str,
    dialogue_history: list[dict] | None = None,
) -> dict:
    """LLM 从对话中提取需求向量（语义方向，不出数值）。

    返回:
    {
        "demand_vector": {efficiency_seeking: 0.5, ...},
        "_confidence": {efficiency_seeking: 0.9, ...},
        "emotion_need": "放松" or None,
        "notes": "..."
    }

    降级: LLM 不可用时返回默认中性向量。
    """
    history_str = ""
    if dialogue_history:
        history_str = "\n".join(
            f"{m['role']}: {m['content']}" for m in dialogue_history[-6:]
        )
    else:
        history_str = f"user: {user_input}"

    result = await _call_llm(
        _DEMAND_EXTRACT_PROMPT.replace("{dialogue_history}", history_str),
        f"用户输入: {user_input}",
        max_tokens=400,
    )

    if result and "demand_vector" in result:
        return result

    # 降级：返回默认中性向量
    return {
        "demand_vector": {
            "efficiency_seeking": 0.5,
            "excitement_seeking": 0.5,
            "tranquility_seeking": 0.5,
            "budget_sensitivity": 0.5,
            "novelty_seeking": 0.5,
            "social_desire": 0.5,
            "physical_energy": 0.5,
        },
        "_confidence": {},
        "emotion_need": None,
        "notes": "降级：LLM 不可用，使用默认向量",
    }


async def ask_preference_question(
    known_prefs: dict,
    missing_dimensions: list[str],
    last_user_input: str,
) -> dict | None:
    """针对缺失维度生成一句口语化追问。

    参数:
        known_prefs: 已知偏好 {"pace": "闲逛型", ...}
        missing_dimensions: 缺失维度列表 ["budget", "tranquility_seeking"]
        last_user_input: 用户刚说的话

    返回:
        {"question": "预算方面～？", "dimension": "budget", "reason": "..."}
        或 None（LLM 失败时返回默认问题）
    """
    if not missing_dimensions:
        return None

    result = await _call_llm(
        _QUESTION_PROMPT.replace("{known_prefs}", json.dumps(known_prefs, ensure_ascii=False))
        .replace("{missing_dimensions}", str(missing_dimensions))
        .replace("{last_user_input}", last_user_input),
        f"已知偏好: {known_prefs}\n缺失维度: {missing_dimensions}\n用户: {last_user_input}",
    )

    if result and "question" in result:
        return result

    # 降级：默认问题
    default_questions = {
        "budget": "预算方面～大概人均多少比较舒服？",
        "pace": "你们今天是打算特种兵式刷景点，还是懒洋洋闲逛一天？",
        "tranquility_seeking": "偏向安静治愈的氛围，还是热闹有活力的？",
        "physical_energy": "体力怎么样？乐意多走走路还是想轻松点？",
        "excitement_seeking": "想要兴奋刺激的体验，还是平缓放松的？",
        "novelty_seeking": "想去没去过的地方，还是老地方也可以？",
        "social_desire": "想一个人安静待着，还是和朋友一起热闹？",
    }
    dim = missing_dimensions[0]
    return {
        "question": default_questions.get(
            dim, f"关于{dim}你有什么偏好？"
        ),
        "dimension": dim,
        "reason": "降级：LLM 不可用，使用默认问题",
    }


async def analyze_user_response(
    dimension: str,
    user_response: str,
) -> dict:
    """从用户回答中提取对某个维度的偏好值。

    返回:
    {"value": 0~1, "confidence": 0~1, "emotion_need": "..."}
    """
    result = await _call_llm(
        _ANALYZE_RESPONSE_PROMPT.replace("{dimension}", dimension),
        f"维度: {dimension}\n回答: {user_response}",
    )

    if result and "value" in result:
        return result

    # 降级：简单关键词
    text = user_response.lower()
    val = 0.5
    if any(w in text for w in ["随便", "都行", "不知道", "无所谓"]):
        val = 0.5
    elif any(w in text for w in ["不想", "不要", "别", "不"]):
        val = 0.2
    elif any(w in text for w in ["有点", "稍微"]):
        val = 0.3
    elif any(w in text for w in ["非常", "很", "特别", "超"]):
        val = 0.8

    return {"value": val, "confidence": 0.3, "emotion_need": None}


def get_missing_dimensions(demand_vector: dict, confidence: dict) -> list[str]:
    """找出置信度低的需求维度，按优先级排序。

    优先级: budget > pace > tranquility > physical > novelty > excitement > social
    """
    priority = [
        "budget_sensitivity",
        "physical_energy",
        "tranquility_seeking",
        "novelty_seeking",
        "excitement_seeking",
        "social_desire",
    ]

    missing = []
    for dim in priority:
        if dim in demand_vector:
            conf = confidence.get(dim, 0)
            if conf < 0.4:
                missing.append(dim)

    return missing
