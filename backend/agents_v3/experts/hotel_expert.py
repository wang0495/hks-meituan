"""Hotel expert: detect overnight need, fetch hotels, pick 2 best via LLM."""

from __future__ import annotations

import json

from backend.agents_v3.experts.base import (
    _llm_decide,
    _load_all_pois,
    _proposal,
    _sanitize_for_prompt,
    sse_expert,
)
from backend.agents_v3.state import TravelState


@sse_expert("hotel")
async def hotel_expert(state: TravelState) -> dict:
    """Recommend hotels when the user likely needs overnight stay."""
    weight = state.get("expert_weights", {}).get("hotel", 0)
    if weight < 0.3:
        return {"proposals": []}

    candidates = state.get("expert_candidates", {}).get("hotel", [])
    intent = state.get("user_intent", {})
    user_input = str(state.get("user_input", ""))
    errors: list[str] = []

    # ── Detect overnight need ──
    need_hotel = any(
        kw in user_input
        for kw in ["晚", "两", "二", "三天", "住宿", "酒店", "民宿", "二日", "两日", "过夜"]
    )
    if not need_hotel:
        judge = await _llm_decide(
            '判断用户是否需要住宿。输出JSON: {"need":true/false,"reason":"理由"}',
            f"用户输入: {_sanitize_for_prompt(user_input)}",
        )
        if judge and judge.get("need"):
            need_hotel = True

    if not need_hotel:
        return {"proposals": []}

    # ── Fetch hotels from API + candidates ──
    all_pois = await _load_all_pois()
    target_city = intent.get("city", "珠海")
    all_pois = [p for p in all_pois if p.get("city", "") == target_city or not p.get("city")]
    hotel_sources = all_pois + candidates
    hotels = [
        c
        for c in hotel_sources
        if any(kw in c.get("category", "") for kw in ["住宿", "酒店", "民宿"])
        or any(kw in c.get("name", "") for kw in ["酒店", "民宿", "宾馆", "公寓"])
    ]

    # Deduplicate
    seen_names: set[str] = set()
    unique_hotels: list[dict] = []
    for h in hotels:
        name = h.get("name", "")
        if name not in seen_names:
            seen_names.add(name)
            unique_hotels.append(h)
    hotels = unique_hotels

    # ── Collect POI locations for proximity scoring ──
    poi_locations: list[dict] = []
    for c in candidates[:15]:
        if c.get("category", "") not in ["住宿", "酒店", "民宿", "餐饮", "美食"]:
            lat, lng = c.get("lat", 0), c.get("lng", 0)
            if lat and lng:
                poi_locations.append(
                    {"name": c.get("name", ""), "lat": round(lat, 3), "lng": round(lng, 3)}
                )

    summaries = [
        {
            "name": h.get("name", ""),
            "price": h.get("avg_price", 0),
            "rating": h.get("rating", 0),
            "tags": h.get("tags", [])[:3],
            "area": h.get("tags", [""])[0] if h.get("tags") else "",
            "lat": round(h.get("lat", 0), 3) if h.get("lat") else None,
            "lng": round(h.get("lng", 0), 3) if h.get("lng") else None,
        }
        for h in hotels[:20]
    ]

    group_type = intent.get("group", {}).get("type", "")
    group_hint = ""
    if group_type == "亲子":
        group_hint = "优先选有亲子房/儿童设施的酒店，位置靠近主要景点。"
    elif group_type == "情侣":
        group_hint = "优先选有海景/景观房的酒店，位置选安静浪漫的区域。"
    elif group_type == "商务":
        group_hint = "优先选交通便利、靠近商业区的酒店。"

    # ── LLM decision ──
    system = f"""你是住宿推荐专家。根据用户需求从候选酒店中挑选最合适的。

考虑因素：
1. 预算合理性（不超预算）
2. 评分和口碑（优先高评分）
3. 位置便利性：通过坐标判断，选离主要景点最近的区域
4. {group_hint if group_hint else '群体适配'}

输出JSON: {{"picks":[{{"name":"酒店名","reason":"推荐理由（含位置优势）","confidence":0.8}}]}}
最多选2个。只输出JSON。"""

    user = f"""用户需求: {_sanitize_for_prompt(user_input)}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
群体: {group_type or '未知'}

用户可能游览的景点:
{json.dumps(poi_locations[:8], ensure_ascii=False)}

候选酒店（含坐标）:
{json.dumps(summaries, ensure_ascii=False)}

请根据酒店与景点的坐标距离推荐。"""

    result = await _llm_decide(system, user)

    proposals = []
    if result and "picks" in result:
        name_map = {h.get("name", ""): h for h in hotels}
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for h in hotels:
                    if name in h.get("name", "") or h.get("name", "") in name:
                        content = h
                        break
            if content:
                proposals.append(
                    _proposal(
                        "hotel", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐")
                    )
                )

    # Fallback: rating sort
    if not proposals and hotels:
        scored = sorted(hotels, key=lambda h: h.get("rating", 4.0), reverse=True)
        for h in scored[:2]:
            proposals.append(_proposal("hotel", h, 0.5, "规则引擎：评分排序"))

    return {"proposals": proposals, "errors": errors}
