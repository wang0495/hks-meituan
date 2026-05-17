"""Destination expert: handle destination-type scenes (theme parks, resorts, etc.)."""

from __future__ import annotations

import json

from backend.agents_v3.experts.base import (
    sse_expert,
    _proposal,
    _llm_decide,
    _haversine_km,
    _is_likely_macau,
    _sanitize_for_prompt,
)
from backend.agents_v3.state import TravelState

# Known destination coordinates
_DEST_COORDS: dict[str, tuple[float, float]] = {
    "长隆": (22.11, 113.54),
    "海洋王国": (22.11, 113.54),
    "御温泉": (22.17, 113.28),
    "圆明新园": (22.27, 113.55),
    "梦幻水城": (22.27, 113.55),
}

# Default: central Zhuhai
_DEFAULT_COORDS: tuple[float, float] = (22.27, 113.57)

# Categories to exclude from POI picks
_EXCLUDE_CATS = {"住宿", "酒店", "民宿", "餐饮", "美食"}


def _detect_destination(user_input: str) -> tuple[str | None, tuple[float, float]]:
    """Return (destination_name, coords) or (None, default_coords)."""
    for name, coords in _DEST_COORDS.items():
        if name in user_input:
            return name, coords
    return None, _DEFAULT_COORDS


@sse_expert("destination")
async def destination_expert(state: TravelState) -> dict:
    """Select supplementary POIs near a user-specified destination."""
    weight = state.get("expert_weights", {}).get("destination", 0)
    if weight < 0.3:
        return {"proposals": []}

    candidates = state.get("expert_candidates", {}).get("destination", [])
    intent = state.get("user_intent", {})
    user_input = str(state.get("user_input", ""))
    errors: list[str] = []

    dest_name, (center_lat, center_lng) = _detect_destination(user_input)

    if dest_name is None:
        # No destination keyword matched -- skip this expert
        return {"proposals": []}

    # Filter candidates to within 5km of destination
    nearby: list[dict] = []
    for c in candidates:
        cat = c.get("category", "")
        if cat in _EXCLUDE_CATS:
            continue
        if _is_likely_macau(c.get("name", "")):
            continue
        lat = c.get("lat", 0)
        lng = c.get("lng", 0)
        if not lat or not lng:
            continue
        if _haversine_km(lat, lng, center_lat, center_lng) <= 5.0:
            nearby.append(c)

    if not nearby:
        return {"proposals": []}

    summaries = [
        {
            "name": c.get("name", ""),
            "category": c.get("category", ""),
            "rating": c.get("rating", 0),
            "price": c.get("avg_price", 0),
            "tags": c.get("tags", [])[:3],
            "lat": round(c.get("lat", 0), 3),
            "lng": round(c.get("lng", 0), 3),
        }
        for c in nearby[:20]
    ]

    group_type = intent.get("group", {}).get("type", "")

    # LLM decision
    system = f"""你是珠海旅游规划专家。用户指定了大景区，需要在附近选择补充景点和餐厅。

核心要求：
1. 所有推荐必须在{dest_name}附近5km范围内
2. 选1-2个附近补充景点（公园/文化/购物），让用户在景区之外也有去处
3. 选1家附近餐厅（游览完景区后用餐）
4. 不要重复推荐{dest_name}本身
{f'5. 群体适配：{group_type}群体的特殊需求' if group_type else ''}

输出JSON: {{"picks":[{{"name":"景点/餐厅名","reason":"推荐理由","confidence":0.8,"type":"景点/餐厅"}}]}}
最多选3个。只输出JSON。"""

    user = f"""用户需求: {_sanitize_for_prompt(user_input)}
指定景区: {dest_name}（坐标: {center_lat}, {center_lng}）
群体: {group_type or '未知'}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人

{dest_name}附近候选（{len(summaries)}个）:
{json.dumps(summaries, ensure_ascii=False)}

请在{dest_name}附近选补充景点和餐厅。"""

    result = await _llm_decide(system, user)

    proposals = []
    if result and "picks" in result:
        name_map = {c.get("name", ""): c for c in nearby}
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for c in nearby:
                    if name in c.get("name", "") or c.get("name", "") in name:
                        content = c
                        break
            if content:
                proposals.append(
                    _proposal("destination", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐"))
                )

    # Fallback: top-rated nearby
    if not proposals:
        sorted_nearby = sorted(nearby, key=lambda c: c.get("rating", 0), reverse=True)
        for c in sorted_nearby[:2]:
            proposals.append(_proposal("destination", c, 0.5, f"规则引擎：{dest_name}附近高评分"))

    return {"proposals": proposals, "errors": errors}
