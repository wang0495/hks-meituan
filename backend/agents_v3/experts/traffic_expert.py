"""Traffic expert: compute distance matrix, ask LLM for optimal route order."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.agents_v3.experts.base import (
    _haversine_km,
    _llm_decide,
    _proposal,
    _sanitize_for_prompt,
    sse_expert,
)

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState


def _nearest_neighbor_order(poi_locs: list[dict]) -> list[str]:
    """Nearest-neighbor heuristic to sort POIs by proximity."""
    if not poi_locs:
        return []
    order = [poi_locs[0]["name"]]
    remaining = list(range(1, len(poi_locs)))
    current = 0
    while remaining:
        best_idx = None
        best_dist = float("inf")
        for idx in remaining:
            p = poi_locs[idx]
            c = poi_locs[current]
            if p.get("lat") and c.get("lat"):
                d = _haversine_km(p["lat"], p["lng"], c["lat"], c["lng"])
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
        if best_idx is not None:
            order.append(poi_locs[best_idx]["name"])
            remaining.remove(best_idx)
            current = best_idx
        else:
            break
    return order


_TRAFFIC_EXPERT_SCENE_HINTS: dict[str, str] = {
    "亲子": """
【亲子路线设计】
- 上午精力好，安排主要景点（如海洋公园、动物园）
- 午后孩子易疲倦，安排室内/轻松项目
- 景点间距要短（带小孩不宜>5km/次）
- 避开交通高峰时段""",
    "情侣": """
【情侣路线设计】
- 安排水畔/海滨漫步路线（情侣路沿线最佳）
- 下午安排咖啡厅或艺术区（轻松浪漫氛围）
- 傍晚安排观景台/海边看日落
- 晚上安排夜景好的地点""",
    "朋友": """
【朋友路线设计】
- 可安排较紧凑的打卡路线
- 午餐和晚餐穿插不同特色街区
- 可以走主题路线（美食街、文创区）""",
}


def _extract_traffic_expert_poi_locs(candidates: list[dict], max_count: int = 30) -> list[dict]:
    """提取交通专家用的POI位置信息。"""
    return [{"name": c.get("name", ""), "lat": c.get("lat", 0), "lng": c.get("lng", 0), "category": c.get("category", ""), "tags": c.get("tags", [])[:3]} for c in candidates[:max_count] if c.get("category", "") not in ["住宿", "酒店", "民宿"]]


def _calc_traffic_expert_distances(poi_locs: list[dict], max_count: int = 12) -> list[dict]:
    """计算POI之间的距离矩阵。"""
    distances = []
    for i, p1 in enumerate(poi_locs[:max_count]):
        for j, p2 in enumerate(poi_locs[:max_count]):
            if i < j and p1.get("lat") and p2.get("lat"):
                d = _haversine_km(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
                if d > 0.5:
                    distances.append({"from": p1["name"], "to": p2["name"], "km": round(d, 1)})
    return distances


@sse_expert("traffic")
async def traffic_expert(state: TravelState) -> dict:
    """Analyze POI distribution and plan transport + route ordering."""
    weight = state.get("expert_weights", {}).get("traffic", 0)
    if weight < 0.3:
        return {"proposals": []}

    candidates = state.get("expert_candidates", {}).get("traffic", [])
    intent = state.get("user_intent", {})
    user_input = str(state.get("user_input", ""))

    poi_locs = _extract_traffic_expert_poi_locs(candidates)
    distances = _calc_traffic_expert_distances(poi_locs)

    group_type = intent.get("group", {}).get("type", "")
    scene_hint = _TRAFFIC_EXPERT_SCENE_HINTS.get(group_type, "\n- 平衡地理效率和游览体验")

    system = f"""你是城市旅行路线规划专家。你需要设计一条高质量的一日游路线。

你的核心任务：
1. 【地理连贯】按区域聚类排序，避免来回折返（跨区移动>10km会严重降低体验）
2. 【时间节奏】遵循情绪曲线设计：
   - 上午(9-12点)：精力充沛，安排主力景点（户外/特色/地标）
   - 午餐(11:30-13:00)：选景点附近的特色餐饮
   - 下午(13-17点)：安排次级景点或室内（午后适合轻松活动）
   - 傍晚(17-19点)：安排观景/休闲（海边/公园/观景台）
   - 晚上(19点后)：如需要，安排夜景/美食/娱乐
3. 【场景适配】{scene_hint}
4. 【高效交通】同区域景点连走，跨区域利用公共交通干线

输出JSON:
{{"mode":"推荐交通方式","route_suggestion":"路线设计思路（2-3句话）","estimated_total_time":"总交通耗时(分钟)","tips":"交通建议","suggested_order":["景点1","景点2",...],"confidence":0.8}}

关键：suggested_order必须是最优游览顺序，综合考虑地理距离、时间节奏和用户体验。
只输出JSON。"""

    user = f"""用户需求: {_sanitize_for_prompt(user_input)}
群体: {group_type or '未知'}
节奏: {pace}
场景要求: {_sanitize_for_prompt(json.dumps(scene_reqs, ensure_ascii=False)) if scene_reqs else '无特殊要求'}
城市: {intent.get('city', '珠海')}

景点位置:
{json.dumps(poi_locs, ensure_ascii=False)}

景点间距离(>0.5km):
{json.dumps(distances[:25], ensure_ascii=False)}

请设计最优路线顺序。注意：优先地理连贯（同区域连走），其次考虑时间节奏。"""

    result = await _llm_decide(system, user)

    if result:
        result["distances"] = distances
        return {
            "proposals": [
                _proposal("traffic", result, result.get("confidence", 0.7), "LLM交通规划")
            ]
        }

    # Fallback: nearest-neighbor ordering
    if poi_locs and distances:
        order = _nearest_neighbor_order(poi_locs)
        return {
            "proposals": [
                _proposal(
                    "traffic",
                    {
                        "mode": "公共交通+步行",
                        "suggested_order": order,
                        "estimated_total_time": 60,
                        "distances": distances,
                    },
                    0.5,
                    "规则引擎：最近邻排序",
                )
            ]
        }

    return {
        "proposals": [
            _proposal(
                "traffic", {"mode": "公共交通", "estimated_total_time": 60}, 0.4, "默认交通方案"
            )
        ]
    }
