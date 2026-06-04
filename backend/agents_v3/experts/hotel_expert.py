"""Hotel expert: detect overnight need, fetch hotels, pick 2 best via LLM."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.agents_v3.experts.base import (
    _llm_decide,
    _load_all_pois,
    _proposal,
    _sanitize_for_prompt,
    sse_expert,
)

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState


_HOTEL_EXPERT_KEYWORDS = ["住宿", "酒店", "民宿"]
_HOTEL_EXPERT_NAME_KEYWORDS = ["酒店", "民宿", "宾馆", "公寓"]
_HOTEL_EXPERT_EXCLUDE_CATS = ["住宿", "酒店", "民宿", "餐饮", "美食"]


async def _check_need_hotel_expert(user_input: str) -> bool:
    """判断是否需要住宿。"""
    if any(kw in user_input for kw in ["晚", "两", "二", "三天", "住宿", "酒店", "民宿", "二日", "两日", "过夜"]):
        return True
    judge = await _llm_decide('判断用户是否需要住宿。输出JSON: {"need":true/false,"reason":"理由"}', f"用户输入: {_sanitize_for_prompt(user_input)}")
    return bool(judge and judge.get("need"))


def _filter_hotels_expert(all_pois: list[dict], candidates: list[dict]) -> list[dict]:
    """筛选住宿POI并去重。"""
    hotel_sources = all_pois + candidates
    hotels = [c for c in hotel_sources if any(kw in c.get("category", "") for kw in _HOTEL_EXPERT_KEYWORDS) or any(kw in c.get("name", "") for kw in _HOTEL_EXPERT_NAME_KEYWORDS)]
    seen: set[str] = set()
    unique = []
    for h in hotels:
        name = h.get("name", "")
        if name not in seen:
            seen.add(name)
            unique.append(h)
    return unique


def _build_hotel_expert_summaries(hotels: list[dict], max_count: int = 20) -> list[dict]:
    """构建住宿摘要。"""
    return [{"name": h.get("name", ""), "price": h.get("avg_price", 0), "rating": h.get("rating", 0), "tags": h.get("tags", [])[:3], "area": h.get("tags", [""])[0] if h.get("tags") else "", "lat": round(h.get("lat", 0), 3) if h.get("lat") else None, "lng": round(h.get("lng", 0), 3) if h.get("lng") else None} for h in hotels[:max_count]]


def _extract_hotel_expert_poi_locs(candidates: list[dict], max_count: int = 15) -> list[dict]:
    """提取POI位置信息。"""
    return [{"name": c.get("name", ""), "lat": round(c.get("lat", 0), 3), "lng": round(c.get("lng", 0), 3)} for c in candidates[:max_count] if c.get("category", "") not in _HOTEL_EXPERT_EXCLUDE_CATS and c.get("lat") and c.get("lng")]


def _match_hotel_expert_picks(picks: list[dict], hotels: list[dict]) -> list[dict]:
    """匹配LLM picks到酒店。"""
    proposals = []
    name_map = {h.get("name", ""): h for h in hotels}
    for pick in picks:
        name = pick.get("name", "")
        content = name_map.get(name)
        if not content:
            for h in hotels:
                if name in h.get("name", "") or h.get("name", "") in name:
                    content = h
                    break
        if content:
            proposals.append(_proposal("hotel", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐")))
    return proposals


_HOTEL_EXPERT_GROUP_HINTS: dict[str, str] = {
    "亲子": "优先选有亲子房/儿童设施的酒店，位置靠近主要景点。",
    "情侣": "优先选有海景/景观房的酒店，位置选安静浪漫的区域。",
    "商务": "优先选交通便利、靠近商业区的酒店。",
}


def _build_hotel_expert_system_prompt(group_hint: str) -> str:
    """构建系统提示。"""
    return f"""你是住宿推荐专家。根据用户需求从候选酒店中挑选最合适的。

考虑因素：
1. 预算合理性（不超预算）
2. 评分和口碑（优先高评分）
3. 位置便利性：通过坐标判断，选离主要景点最近的区域
4. {group_hint if group_hint else '群体适配'}

输出JSON: {{"picks":[{{"name":"酒店名","reason":"推荐理由（含位置优势）","confidence":0.8}}]}}
最多选2个。只输出JSON。"""


def _build_hotel_expert_user_prompt(user_input: str, intent: dict, group_type: str, poi_locations: list[dict], summaries: list[dict]) -> str:
    """构建用户提示。"""
    return f"""用户需求: {_sanitize_for_prompt(user_input)}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
群体: {group_type or '未知'}

用户可能游览的景点:
{json.dumps(poi_locations[:8], ensure_ascii=False)}

候选酒店（含坐标）:
{json.dumps(summaries, ensure_ascii=False)}

请根据酒店与景点的坐标距离推荐。"""


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

    if not await _check_need_hotel_expert(user_input):
        return {"proposals": []}

    all_pois = await _load_all_pois()
    target_city = intent.get("city", "珠海")
    all_pois = [p for p in all_pois if p.get("city", "") == target_city or not p.get("city")]
    hotels = _filter_hotels_expert(all_pois, candidates)

    poi_locations = _extract_hotel_expert_poi_locs(candidates)
    summaries = _build_hotel_expert_summaries(hotels)

    group_type = intent.get("group", {}).get("type", "")
    group_hint = _HOTEL_EXPERT_GROUP_HINTS.get(group_type, "")

    system = _build_hotel_expert_system_prompt(group_hint)
    user = _build_hotel_expert_user_prompt(user_input, intent, group_type, poi_locations, summaries)
    result = await _llm_decide(system, user)
    proposals = _match_hotel_expert_picks(result.get("picks", []) if result else [], hotels) if result and "picks" in result else []

    if not proposals and hotels:
        for h in sorted(hotels, key=lambda h: h.get("rating", 4.0), reverse=True)[:2]:
            proposals.append(_proposal("hotel", h, 0.5, "规则引擎：评分排序"))

    return {"proposals": proposals, "errors": errors}
