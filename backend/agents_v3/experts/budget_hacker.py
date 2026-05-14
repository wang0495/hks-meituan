"""Budget hacker expert: select free/cheap POIs for low-budget travelers."""

from __future__ import annotations

import json

from backend.agents_v3.experts.base import (
    sse_expert,
    _proposal,
    _llm_decide,
    _is_likely_macau,
)
from backend.agents_v3.state import TravelState

# Categories that are inherently free or cheap
_BUDGET_CATEGORIES = {"公园", "自然", "文化", "历史", "广场", "海滩", "海滨"}

# Price threshold for "cheap"
_PRICE_CAP = 50

# Categories to exclude entirely
_EXCLUDE_CATS = {"住宿", "酒店", "民宿"}


@sse_expert("budget_hacker")
async def budget_hacker(state: TravelState) -> dict:
    """Select free/cheap POIs optimized for budget-conscious travelers."""
    weight = state.get("expert_weights", {}).get("budget_hacker", 0)
    if weight < 0.3:
        return {"proposals": []}

    candidates = state.get("expert_candidates", {}).get("budget_hacker", [])
    intent = state.get("user_intent", {})
    user_input = str(state.get("user_input", ""))
    errors: list[str] = []

    # Pre-filter: free or cheap POIs
    budget_pois: list[dict] = []
    for c in candidates:
        cat = c.get("category", "")
        if cat in _EXCLUDE_CATS:
            continue
        if _is_likely_macau(c.get("name", "")):
            continue
        if c.get("rating") is None:
            continue

        price = c.get("avg_price", 0)
        is_free_or_cheap = (price == 0 or price <= _PRICE_CAP)
        is_budget_category = cat in _BUDGET_CATEGORIES

        # Include parks, beaches, historical streets by category even if no price info
        if is_free_or_cheap or is_budget_category:
            budget_pois.append(c)

    # Geo-constraint: use poi_expert's candidate center as anchor
    # Only pick free POIs within 10km of the main cluster
    poi_pool = state.get("expert_candidates", {}).get("poi", [])
    if poi_pool and len(poi_pool) >= 2:
        # Calculate center of poi pool
        lats = [p.get("lat", 0) for p in poi_pool if p.get("lat")]
        lngs = [p.get("lng", 0) for p in poi_pool if p.get("lng")]
        if lats and lngs:
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)
            from backend.agents_v3.experts.base import _haversine_km
            budget_pois = [
                p for p in budget_pois
                if p.get("lat") and p.get("lng")
                and _haversine_km(center_lat, center_lng, p["lat"], p["lng"]) <= 10.0
            ]

    if not budget_pois:
        return {"proposals": []}

    summaries = [
        {
            "name": c.get("name", ""),
            "category": c.get("category", ""),
            "rating": c.get("rating", 0),
            "price": c.get("avg_price", 0),
            "tags": c.get("tags", [])[:3],
            "scene_tags": c.get("_scene_tags", [])[:3],
            "lat": round(c.get("lat", 0), 3) if c.get("lat") else None,
            "lng": round(c.get("lng", 0), 3) if c.get("lng") else None,
        }
        for c in budget_pois[:30]
    ]

    group_type = intent.get("group", {}).get("type", "")
    budget = intent.get("budget", {}).get("per_person", 0)

    # LLM decision
    system = f"""你是穷游规划专家。用户预算极低，请选择免费或超值景点和餐饮。

核心要求：
1. 所有推荐必须是免费（price=0）或超值（price<=50元）的POI
2. 优先选免费景点：公园、海滩、历史街区、观景台
3. 如果有餐饮候选，选人均30元以内的小吃/排档
4. 类型搭配：自然+文化+休闲，不重复同类型
5. 地理紧凑：通过坐标选距离近的POI，减少交通费
{f'6. 群体适配：{group_type}群体的特殊需求' if group_type else ''}

输出JSON: {{"picks":[{{"name":"POI名","reason":"推荐理由（含为什么超值）","confidence":0.8,"type":"景点/餐饮"}}]}}
选3-5个最佳性价比POI。只输出JSON。"""

    user = f"""用户需求: {user_input}
预算: {budget if budget else '极低'}元/人
群体: {group_type or '未知'}

免费/超值候选（{len(summaries)}个）:
{json.dumps(summaries, ensure_ascii=False)}

请选出最具性价比的POI组合。"""

    result = await _llm_decide(system, user)

    proposals = []
    if result and "picks" in result:
        name_map = {c.get("name", ""): c for c in budget_pois}
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for c in budget_pois:
                    if name in c.get("name", "") or c.get("name", "") in name:
                        content = c
                        break
            if content:
                proposals.append(
                    _proposal("budget_hacker", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐"))
                )

    # Fallback: highest-rated free POIs
    if not proposals:
        free = [c for c in budget_pois if c.get("avg_price", -1) == 0]
        if not free:
            free = budget_pois
        free.sort(key=lambda c: c.get("rating", 0), reverse=True)
        for c in free[:4]:
            proposals.append(_proposal("budget_hacker", c, 0.5, "规则引擎：免费高分"))

    return {"proposals": proposals, "errors": errors}
