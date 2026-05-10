"""LLM智能路线策划器。

在intent_parser和solver之间插入，用LLM推理出最佳路线方案。
解决POI数据不完美时的语义推理问题。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        _client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _client


def _build_poi_summary(pois: list[dict], max_count: int = 50) -> str:
    """将候选POI列表压缩为LLM友好的摘要格式。"""
    lines = []
    for i, p in enumerate(pois[:max_count]):
        name = p.get("name", "?")
        cat = p.get("category", "?")
        price = p.get("avg_price", 0)
        hours = p.get("business_hours", "?")
        rating = p.get("rating", 0)
        tags = p.get("_scene_tags", [])[:3]
        indoor = p.get("constraints", {}).get("is_indoor", None)
        pet = p.get("constraints", {}).get("pet_friendly", False)

        extras = []
        if indoor is True:
            extras.append("室内")
        elif indoor is False:
            extras.append("室外")
        if pet:
            extras.append("宠物友好")

        tag_str = ",".join(tags) if tags else ""
        extra_str = f" [{' '.join(extras)}]" if extras else ""
        lines.append(
            f"- {p.get('id','')} {name} [{cat}] ¥{price} ⏰{hours} ⭐{rating} "
            f"标签:{tag_str}{extra_str}"
        )
    return "\n".join(lines)


def _build_planner_prompt(
    user_input: str,
    user_intent: dict[str, Any],
    poi_summary: str,
    perception_ctx: Any = None,
) -> str:
    """构建LLM Planner的prompt。"""
    time_info = user_intent.get("time", {})
    budget_info = user_intent.get("budget", {})
    group_info = user_intent.get("group", {})
    prefs = user_intent.get("preferences", {})
    pace = user_intent.get("pace", "平衡型")
    hard_constraints = user_intent.get("hard_constraints", [])

    # 感知上下文
    weather = ""
    if perception_ctx:
        weather = f"天气:{getattr(perception_ctx, 'weather', '?')} 温度:{getattr(perception_ctx, 'temperature', '?')}°C"

    prompt = f"""你是珠海旅游路线规划专家。根据用户需求和可用POI数据，规划最佳路线。

## 用户需求
- 原始输入: {user_input}
- 时间: {time_info.get('start', '?')} - {time_info.get('end', '?')}
- 预算: ¥{budget_info.get('per_person', 500)}/人 ({budget_info.get('type', '弹性')})
- 人群: {group_info.get('type', '?')} ({group_info.get('size', 1)}人)
- 偏好: 文化={prefs.get('culture', 0.5)} 美食={prefs.get('food', 0.5)} 自然={prefs.get('nature', 0.5)} 社交={prefs.get('social', 0.5)}
- 节奏: {pace}
- 硬约束: {', '.join(hard_constraints) if hard_constraints else '无'}
- {weather}

## 可用POI列表（共{poi_summary.count(chr(10))+1}个）
{poi_summary}

## 规划要求
1. 从POI列表中选择3-6个，按访问顺序排列
2. 严格遵守时间约束：总时长不超过用户指定的时间范围
3. 严格遵守预算约束：总花费不超过预算
4. 严格遵守硬约束（室内/宠物友好/深夜营业等）
5. 确保category多样性：不要连续安排同类POI
6. 地理上合理：不要反复横跳，优先选择距离近的POI
7. 如果用户需求在数据中找不到完美匹配，选择最接近的替代方案并说明原因

输出JSON格式:
{{
  "recommended_pois": ["poi_id1", "poi_id2", "poi_id3"],
  "reasoning": "选择这些POI的原因",
  "warnings": ["提醒用户注意的事项"],
  "intent_refinements": {{
    "hard_constraints": ["可能需要补充的硬约束"],
    "preferences_adjusted": {{"culture": 0.5}}
  }}
}}"""

    return prompt


async def plan_route(
    user_input: str,
    user_intent: dict[str, Any],
    candidate_pois: list[dict[str, Any]],
    perception_ctx: Any = None,
) -> dict[str, Any] | None:
    """用LLM规划路线方案。

    Args:
        user_input: 用户原始输入
        user_intent: intent_parser解析结果
        candidate_pois: 候选POI列表
        perception_ctx: 感知上下文

    Returns:
        LLM规划结果dict，失败返回None
    """
    try:
        poi_summary = _build_poi_summary(candidate_pois, max_count=50)
        prompt = _build_planner_prompt(user_input, user_intent, poi_summary, perception_ctx)

        client = _get_client()
        resp = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        text = resp.choices[0].message.content or ""
        result = json.loads(text)

        # 验证输出格式
        if "recommended_pois" not in result:
            logger.warning("LLM Planner missing recommended_pois")
            return None

        # 验证推荐的POI ID在候选列表中
        valid_ids = {p.get("id") for p in candidate_pois}
        result["recommended_pois"] = [
            pid for pid in result["recommended_pois"] if pid in valid_ids
        ]

        if not result["recommended_pois"]:
            logger.warning("LLM Planner recommended no valid POIs")
            return None

        logger.info(
            "LLM Planner: recommended %d POIs, reasoning: %s",
            len(result["recommended_pois"]),
            result.get("reasoning", "")[:100],
        )
        return result

    except Exception as e:
        logger.warning("LLM Planner failed: %s", e)
        return None
