"""Destination expert: handle destination-type scenes (theme parks, resorts, etc.)."""

from __future__ import annotations

import json

from backend.agents_v3.experts.base import (
    _haversine_km,
    _is_likely_macau,
    _llm_decide,
    _proposal,
    _sanitize_for_prompt,
    sse_expert,
)
from backend.agents_v3.state import TravelState

# Known destination coordinates
_DEST_COORDS: dict[str, tuple[float, float]] = {
    "长隆": (22.11, 113.54),
    "海洋王国": (22.11, 113.54),
    "御温泉": (22.17, 113.28),
    "圆明新园": (22.27, 113.55),
    "梦幻水城": (22.27, 113.55),
    # 扩展：覆盖更多核心目的地
    "海泉湾": (22.10, 113.26),
    "港珠澳大桥": (22.22, 113.58),
    "东澳岛": (22.01, 113.72),
    "外伶仃岛": (22.08, 114.00),
    "金沙滩": (22.06, 113.32),
    "创新方": (22.12, 113.52),
    "景山公园": (22.24, 113.57),
    "海滨公园": (22.26, 113.58),
    "海滨泳场": (22.22, 113.57),
    "梅溪牌坊": (22.28, 113.53),
    "野狸岛": (22.28, 113.59),
    "罗西尼": (22.30, 113.52),
    "唐家湾": (22.36, 113.58),
    "横琴": (22.12, 113.52),
    "飞沙滩": (22.04, 113.34),
    "三板村": (22.10, 113.35),
    "灯笼沙": (22.18, 113.25),
    "黄杨山": (22.25, 113.27),
    "斗门古街": (22.22, 113.29),
    "接霞庄": (22.20, 113.26),
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

    # 优先从 state 读取 expert_router 已检测的目的地信息
    dest_name = state.get("destination_name")
    center = state.get("destination_center")
    if not dest_name or not center:
        dest_name, center = _detect_destination(user_input)
    center_lat, center_lng = center

    if dest_name is None:
        # No destination keyword matched -- skip this expert
        return {"proposals": []}

    # ── 强制包含核心目的地POI ──
    # 从 candidates 中找到核心目的地对应的POI（名称匹配）
    core_dest = None
    for c in candidates:
        cname = c.get("name", "")
        if dest_name in cname or cname in dest_name:
            core_dest = c
            break
    # 如果精确匹配没找到，用坐标找最近的（1km内）
    if not core_dest:
        for c in candidates:
            lat = c.get("lat", 0)
            lng = c.get("lng", 0)
            if lat and lng and _haversine_km(lat, lng, center_lat, center_lng) <= 1.0:
                core_dest = c
                break

    # Filter candidates: 渐进扩大半径（岛类POI稀疏）
    _is_island = any(kw in dest_name for kw in ("岛", "群岛"))
    nearby: list[dict] = []
    for radius in ([5.0] if not _is_island else [5.0, 10.0, 20.0]):
        nearby = []
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
            if _haversine_km(lat, lng, center_lat, center_lng) <= radius:
                nearby.append(c)
        if nearby:
            break

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
    _radius_desc = "15km" if _is_island else "5km"
    system = f"""你是珠海旅游规划专家。用户指定了大景区，需要在附近选择补充景点和餐厅。

核心要求：
1. 所有推荐必须在{dest_name}附近{_radius_desc}范围内
2. 选1-2个附近补充景点（公园/文化/购物），让用户在景区之外也有去处
3. 选1家附近餐厅（游览完景区后用餐）
4. 不要重复推荐{dest_name}本身
{'5. 海岛场景注意：渡轮单程至少60分钟，只选同一个岛或邻近岛的POI，不要选大陆上的' if _is_island else ''}
{f'6. 群体适配：{group_type}群体的特殊需求' if group_type else ''}

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
                    _proposal(
                        "destination",
                        content,
                        pick.get("confidence", 0.7),
                        pick.get("reason", "LLM推荐"),
                    )
                )

    # Fallback: top-rated nearby
    if not proposals:
        sorted_nearby = sorted(nearby, key=lambda c: c.get("rating", 0), reverse=True)
        for c in sorted_nearby[:2]:
            proposals.append(_proposal("destination", c, 0.5, f"规则引擎：{dest_name}附近高评分"))

    # ── 强制包含核心目的地 ──
    if core_dest:
        # 检查是否已在 proposals 中（名称匹配）
        already = any(
            core_dest.get("name", "") in p.get("content", {}).get("name", "")
            or p.get("content", {}).get("name", "") in core_dest.get("name", "")
            for p in proposals
        )
        if not already:
            proposals.insert(
                0, _proposal("destination", core_dest, 1.0, f"核心目的地：{dest_name}")
            )

    return {"proposals": proposals, "errors": errors}
