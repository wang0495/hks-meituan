"""Synthesizer：MoE提案按权重组装路线。

架构：锦标赛模式（并行3策略竞争，启发式评分选最优）。

═════════════════════════════════════════════════════════════
  架构决策记录（ADR）— 别瞎改，每条都是踩过坑的
═════════════════════════════════════════════════════════════

ADR-S1: _cap_route_stops 必须在 _ensure_* 之前执行
  - _ensure_food/poi 将遗漏站点追加到列表末尾
  - _cap_route_stops 用 steps[:max] 从头部截断
  - 如果 cap 在 ensure 之后，追加的餐饮站点会被截掉 → 路线无餐饮
  - 修复：调换顺序为 cap → ensure，追加的站点不受截断影响
  - 2026-05-15 实测：修复前 4/5通过(6.8)，修复后首次 5/5通过(7.0)

ADR-S2: 不要在 _cap_route_stops 里做餐饮保留逻辑
  - 尝试过：截断时优先保留 _type=lunch/dinner 的站点
  - 失败原因：餐饮站点被保留但位置乱了，LLM编排的地理顺序被破坏
  - geo_continuity 从 7-8 暴跌到 4-5，overall 从 6.8 降到 6.0
  - 结论：不能在后处理阶段破坏LLM的时间/地理编排

ADR-S3: 不要用后处理规则强制多样性
  - 尝试过：按category多样性替换同质POI、黑名单连锁餐厅、去重同category
  - 全部失败：替换的POI破坏了地理连续性，或者LLM方差把效果吃掉
  - 根因：diversity瓶颈不在后处理，在数据——娱乐类只有39个(3.5%多为夜店)，
    自然风光只有1个(0.05%)。路线永远只能在景点+文化+运动+餐饮里打转。
  - 详见 docs/optimization_log.md

ADR-S4: LLM prompt微调对diversity效果不可控
  - 尝试过：在观光/特种兵/休闲的diversity_rule中加"至少N种类型"
  - 效果：某个场景diversity+1，但另一个场景geo-2或overall-1
  - 根因：LLM对prompt中"多样性"的理解是随机飘的，无法稳定控制
  - 同一个prompt跑2次，场景3可能得6也可能得7，场景4可能得7也可能得5
  - 结论：prompt微调只能修复逻辑矛盾（如美食型2家上限），不能用来提升指标

ADR-S5: 美食型的餐厅上限矛盾必须修复
  - 原代码：第7条说"最多选4家"，第8条说"总共不超过2家" → LLM困惑
  - 修复：第8条区分"美食型"和"非美食型"，美食型不受2家限制
  - 效果：美食场景diversity从5→6，overall从6→7
  - 注意：这只是修复逻辑矛盾，不是提升上限。盲目提高上限会导致路线过长

ADR-S6: food_list 必须包含 category/tags 字段
  - 原代码：food_list只有name/price/lat/lng，LLM无法判断餐厅类型
  - 修复：补充category/rating/tags，让LLM能做类型多样性选择
  - 效果：配合ADR-S5，美食场景能选出不同子类型的餐厅

ADR-S7: narrator 必须用 enable_llm_polish=False
  - synthesizer内部调generate_narrative，SSE路由也会调一次
  - 如果都用True，6站路线 = 12次LLM调用（synthesizer 6次 + SSE 6次）
  - 修复：synthesizer传False（模板），SSE路径独立做LLM润色
  - 同时narrator内部改为asyncio.gather并行，6站从串行30s→并行5s

ADR-S8: 不引入外部搜索API做"攻略专家"
  - 尝试过：新增 guide_expert（第9位MoE专家），调用 UAPI Pro 搜索真实旅游攻略
  - 失败原因：
    1) UAPI Pro 免费版每日仅40次请求，5场景测试直接耗尽全天配额
    2) 429限流后 guide_expert 退化为 LLM knowledge fallback，效果与无 guide 持平
    3) 用 LLM knowledge fallback 时测试 4/5(6.8) vs 不用 guide 也是 4/5(6.8)，无提升
    4) 外部搜索依赖网络可用性，生产环境可靠性无法保证
  - 根因：路线规划的核心信息来源是 POI 数据库（2000+ POI）+ LLM 推理能力，
    外部搜索只能提供"参考路线顺序"，但这个信息 LLM 自身已经能从 POI 数据推导
  - 替代方案：如果要提升路线质量，应从 POI 数据丰富度（增加标签/评分/热度）
    和 prompt 工程入手，而非引入外部搜索依赖
  - 2026-05-20 实测：guide_expert(搜索可用) 4/5(6.8) vs guide_expert(429降级) 3/5(6.6) vs 无guide 4/5(6.8)
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import datetime, timedelta

import numpy as np

from backend.agents_v3.experts.base import (
    _haversine_km,
    _is_likely_macau,
    _llm_decide,
)
from backend.agents_v3.nodes.synthesizer_food import (
    _ensure_food_in_route,
    _ensure_food_scene_food_count,
    _ensure_min_food_in_route,
)
from backend.agents_v3.nodes.synthesizer_scoring import (
    _get_route_name_set,
    _score_route_heuristic,
)
from backend.agents_v3.nodes.synthesizer_time import (
    _calc_available_minutes,
    _category_stay_min,
    _enforce_time_windows,
    _recalc_route_times,
    _rule_assign_times,
    _smooth_times,
)
from backend.agents_v3.state import AGENT_META, TravelState, sse_emit

# ── 名称去重组 ──
_DUP_GROUPS = [
    {
        "长隆海洋王国",
        "海洋王国",
        "横琴长隆海洋王国",
        "珠海长隆海洋王国",
        "珠海横琴长隆海洋王国",
        "珠海海洋王国",
    },
    {"长隆海洋科学馆", "横琴长隆海洋科学馆", "珠海长隆海洋科学馆"},
    {"情侣路", "珠海情侣路", "情侣路海滨", "情侣路海滨步道", "情侣路中段"},
    {"珠海渔女", "渔女像", "珠海渔女雕像"},
    {"外伶仃岛", "珠海外伶仃岛", "伶仃岛"},
    {"淇澳岛", "珠海淇澳岛"},
    {"长隆马戏城", "珠海长隆横琴国际马戏城"},
]


def _canonical_name(name: str) -> str:
    for group in _DUP_GROUPS:
        if any(kw in name for kw in group):
            return next(iter(group))
    return name


def _fuzzy_dedup_key(name: str) -> str | None:
    import re

    patterns = [
        (r"(湾仔.*海鲜)", "湾仔海鲜"),
        (r"(夏湾.*夜市)", "夏湾夜市"),
        (r"(横琴.*蚝)", "横琴蚝庄"),
        (r"(情侣路.*)", "情侣路"),
        (r"(长隆.*)", "长隆"),
    ]
    for pat, key in patterns:
        if re.search(pat, name):
            return key
    return None


def _dedup_route(steps: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for step in steps:
        name = step.get("poi", {}).get("name", "")
        key = _canonical_name(name)
        if key in seen:
            continue
        fuzzy_key = _fuzzy_dedup_key(name)
        if fuzzy_key and fuzzy_key in seen:
            continue
        seen.add(key)
        if fuzzy_key:
            seen.add(fuzzy_key)
        result.append(step)
    return result


# ── 地理重排：消除跨区跳跃 ──
_MAX_LEG_KM = 15.0


def _geo_reroute(steps: list[dict], max_leg_km: float = _MAX_LEG_KM) -> list[dict]:
    """后处理：全路线贪心最近邻重排，消除折返。"""
    if len(steps) <= 2:
        return steps

    needs_reroute = False
    for i in range(1, len(steps)):
        prev_poi = steps[i - 1].get("poi", {})
        cur_poi = steps[i].get("poi", {})
        lat1, lng1 = prev_poi.get("lat", 0), prev_poi.get("lng", 0)
        lat2, lng2 = cur_poi.get("lat", 0), cur_poi.get("lng", 0)
        if lat1 and lat2:
            d = _haversine_km(lat1, lng1, lat2, lng2)
            if d > max_leg_km:
                needs_reroute = True
                break

    if not needs_reroute:
        return steps

    fixed = [steps[0]]
    remaining = list(steps[1:])

    while remaining:
        cur = fixed[-1]
        cur_poi = cur.get("poi", {})
        cur_lat, cur_lng = cur_poi.get("lat", 0), cur_poi.get("lng", 0)

        best_idx = 0
        best_dist = float("inf")
        for j, s in enumerate(remaining):
            p = s.get("poi", {})
            lat, lng = p.get("lat", 0), p.get("lng", 0)
            if cur_lat and lat:
                d = _haversine_km(cur_lat, cur_lng, lat, lng)
            else:
                d = 999
            if d < best_dist:
                best_dist = d
                best_idx = j

        fixed.append(remaining.pop(best_idx))

    return fixed


# ── 站数上限 ──
_SCENE_MAX_STOPS = {
    "美食型": 6,
    "休闲型": 5,
    "目的地型": 4,
    "特种兵型": 8,
    "观光型": 6,
}


def _cap_route_stops(route: dict, scene_type: str, intent: dict) -> dict:
    steps = route.get("route", [])
    if not steps:
        return route

    max_stops = _SCENE_MAX_STOPS.get(scene_type, 6)
    group_type = intent.get("group", {}).get("type", "")
    if group_type in ("亲子", "退休") and max_stops > 4:
        max_stops -= 1

    if len(steps) <= max_stops:
        return route

    route["route"] = steps[:max_stops]
    return route


# ── DPP多样性重排 ──


def _dpp_select(kernel_matrix: np.ndarray, max_length: int, epsilon: float = 1e-10) -> list[int]:
    """贪心DPP选择：最大化log det(L_S)，平衡质量(对角线)和多样性(非对角线)。"""
    n = kernel_matrix.shape[0]
    if n <= max_length:
        return list(range(n))
    cis = np.zeros((max_length, n))
    di2s = np.copy(np.diag(kernel_matrix))
    selected = []
    selected.append(int(np.argmax(di2s)))
    while len(selected) < max_length:
        k = len(selected) - 1
        ci_opt = cis[:k, selected[-1]]
        di_opt = math.sqrt(max(di2s[selected[-1]], epsilon))
        elements = kernel_matrix[selected[-1], :]
        eis = (elements - np.dot(ci_opt, cis[:k, :])) / di_opt
        cis[k, :] = eis
        di2s -= np.square(eis)
        for s in selected:
            di2s[s] = -np.inf
        best = int(np.argmax(di2s))
        if di2s[best] < epsilon:
            break
        selected.append(best)
    return selected


def _build_category_vector(cat: str) -> float:
    """把category映射成数值，同类型=相似值。"""
    _GROUPS = {
        "自然风光": 0.0,
        "海滨景点": 0.05,
        "水上运动场所": 0.1,
        "文化景点": 0.2,
        "文化": 0.2,
        "地标景点": 0.25,
        "夜景地标": 0.3,
        "运动": 0.4,
        "亲子游乐": 0.45,
        "正餐": 0.55,
        "海鲜餐饮": 0.6,
        "地方小吃": 0.65,
        "夜市小吃": 0.7,
        "甜品饮品": 0.75,
        "茶餐厅": 0.8,
        "购物": 0.85,
        "海景咖啡馆": 0.9,
        "温泉SPA": 0.92,
        "休闲娱乐": 0.95,
        "密室逃脱": 0.95,
        "攀岩": 0.95,
    }
    return _GROUPS.get(cat, 0.5)


def _dpp_rerank_route(route: dict, scene_type: str) -> dict:
    """用DPP对路线步骤做多样性重排。"""
    steps = route.get("route", [])
    if len(steps) <= 3:
        return route

    n = len(steps)
    kernel = np.zeros((n, n))

    for i in range(n):
        poi_i = steps[i].get("poi", {})
        quality = poi_i.get("rating", 4.0) / 5.0
        if poi_i.get("avg_price", 0) == 0:
            quality = min(quality * 1.1, 1.0)
        kernel[i, i] = quality

    for i in range(n):
        cat_i = steps[i].get("poi", {}).get("_display_category") or steps[i].get("poi", {}).get(
            "category", ""
        )
        val_i = _build_category_vector(cat_i)
        for j in range(i + 1, n):
            cat_j = steps[j].get("poi", {}).get("_display_category") or steps[j].get("poi", {}).get(
                "category", ""
            )
            val_j = _build_category_vector(cat_j)
            similarity = 0.9 if cat_i == cat_j else max(0, 1.0 - abs(val_i - val_j) * 2)
            quality_avg = (kernel[i, i] + kernel[j, j]) / 2
            kernel[i, j] = similarity * quality_avg
            kernel[j, i] = kernel[i, j]

    selected = _dpp_select(kernel, n)
    reordered = _recalc_route_times([steps[i] for i in selected])
    reordered = _dedup_route(reordered)
    reordered = _enforce_time_windows(reordered)

    route["route"] = reordered
    return route


def _find_must_keep_pois(
    last_stops: list[str],
    route_names: set[str],
    all_proposals: list[dict],
) -> list[dict]:
    """找出必须保留但被遗漏的核心POI。"""
    proposal_map = {}
    for p in all_proposals:
        name = p.get("content", {}).get("name", "")
        if name:
            proposal_map[name] = p

    must_keep = []
    for stop_name in last_stops:
        if any(stop_name in rn or rn in stop_name for rn in route_names):
            continue
        matched = proposal_map.get(stop_name)
        if not matched:
            for name, p in proposal_map.items():
                if stop_name in name or name in stop_name:
                    matched = p
                    break
        if matched:
            must_keep.append(matched)
    return must_keep


def _insert_poi_at_nearest(steps: list[dict], content: dict) -> None:
    """按地理就近原则将POI插入路线。"""
    mk_lat = content.get("lat", 0)
    mk_lng = content.get("lng", 0)
    best_idx = len(steps)
    best_dist = float("inf")

    for i, s in enumerate(steps):
        poi = s.get("poi", {})
        lat, lng = poi.get("lat", 0), poi.get("lng", 0)
        if mk_lat and mk_lng and lat and lng:
            d = _haversine_km(mk_lat, mk_lng, lat, lng)
            if d < best_dist:
                best_dist = d
                best_idx = i + 1

    prev_dep = (
        steps[best_idx - 1].get("departure_time", "10:00") if steps and best_idx > 0 else "10:00"
    )
    try:
        arr_t = datetime.strptime(prev_dep, "%H:%M") + timedelta(minutes=15)
    except ValueError:
        arr_t = datetime.strptime("10:15", "%H:%M")

    steps.insert(
        best_idx,
        {
            "poi": content,
            "arrival_time": arr_t.strftime("%H:%M"),
            "departure_time": (arr_t + timedelta(minutes=60)).strftime("%H:%M"),
            "travel_from_prev": {
                "distance_m": int(best_dist * 1000) if best_dist < float("inf") else 2000,
                "time_min": 15,
            },
            "_type": "must_keep",
        },
    )


def _must_keep_core_pois(
    route: dict,
    prev_round_context: dict,
    all_proposals: list[dict],
) -> dict:
    """反馈重入时，确保上一轮的核心POI保留在路线中。"""
    if not prev_round_context or not route or not route.get("route"):
        return route

    last_stops = prev_round_context.get("last_stops", [])
    if not last_stops:
        return route

    steps = route["route"]
    route_names: set[str] = set()
    for s in steps:
        n = s.get("poi", {}).get("name", "")
        route_names.add(n)
        c = _canonical_name(n)
        if c != n:
            route_names.add(c)

    must_keep = _find_must_keep_pois(last_stops, route_names, all_proposals)
    if not must_keep:
        return route

    for mk in must_keep:
        _insert_poi_at_nearest(steps, mk.get("content", {}))

    route["route"] = _dedup_route(steps)
    return route


def _ensure_poi_in_route(route: dict, poi_proposals: list[dict], intent: dict) -> dict:
    """确保路线中包含指定POI。"""
    if not route or not route.get("route") or not poi_proposals:
        return route
    if intent.get("scene_type", "") == "美食型":
        return route

    steps = route["route"]
    route_names = _get_route_name_set(steps)

    missing = [
        pp
        for pp in poi_proposals
        if not any(
            pp.get("content", {}).get("name", "") in rn
            or rn in pp.get("content", {}).get("name", "")
            for rn in route_names
        )
    ]
    if not missing:
        return route

    try:
        t = datetime.strptime(steps[-1].get("departure_time", "17:00"), "%H:%M")
    except ValueError:
        t = datetime.strptime("17:00", "%H:%M")

    try:
        end_dt = datetime.strptime(intent.get("time", {}).get("end", "21:00"), "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")

    for pp in missing:
        content = pp.get("content", {})
        stay_min = int(content.get("avg_stay_min", 60))
        departure = t + timedelta(minutes=stay_min)
        if departure > end_dt or len(steps) >= 10:
            break
        steps.append(
            {
                "poi": content,
                "arrival_time": t.strftime("%H:%M"),
                "departure_time": departure.strftime("%H:%M"),
                "travel_from_prev": {"distance_m": 3000, "time_min": 20},
                "_type": "",
            }
        )
        t = departure + timedelta(minutes=20)

    steps = _enforce_time_windows(_dedup_route(steps))
    route["route"] = steps
    route["total_cost"] = {
        "time_min": route.get("total_cost", {}).get("time_min", 0),
        "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
    }
    return route


# ── LLM路线编排 ──


def _build_poi_list_for_llm(poi_proposals: list[dict]) -> list[dict]:
    """构建POI列表供LLM使用。"""
    return [
        {
            "name": p.get("content", {}).get("name", ""),
            "category": p.get("content", {}).get("category", ""),
            "lat": round(p.get("content", {}).get("lat", 0), 3),
            "lng": round(p.get("content", {}).get("lng", 0), 3),
            "price": p.get("content", {}).get("avg_price", 0),
            "stay_min": p.get("content", {}).get("avg_stay_min", 90),
            "tags": p.get("content", {}).get("tags", [])[:3],
            "confidence": p.get("confidence", 0.5),
            "expert": p.get("agent", "poi"),
        }
        for p in poi_proposals
    ]


def _build_food_list_for_llm(food_proposals: list[dict]) -> list[dict]:
    """构建餐饮列表供LLM使用。"""
    return [
        {
            "name": p.get("content", {}).get("name", ""),
            "category": p.get("content", {}).get("category", ""),
            "price": p.get("content", {}).get("avg_price", 0),
            "rating": p.get("content", {}).get("rating", 0),
            "tags": p.get("content", {}).get("tags", [])[:3],
            "lat": round(p.get("content", {}).get("lat", 0), 3),
            "lng": round(p.get("content", {}).get("lng", 0), 3),
            "meal_time": p.get("content", {}).get("meal_time", ""),
            "business_hours": p.get("content", {}).get(
                "business_hours", p.get("content", {}).get("opening_hours", "")
            ),
            "reason": p.get("reasoning", ""),
        }
        for p in food_proposals
    ]


def _build_hotel_list_for_llm(hotel_proposals: list[dict]) -> list[dict]:
    """构建酒店列表供LLM使用。"""
    return [
        {
            "name": p.get("content", {}).get("name", ""),
            "lat": round(p.get("content", {}).get("lat", 0), 3),
            "lng": round(p.get("content", {}).get("lng", 0), 3),
        }
        for p in hotel_proposals
    ]


def _calc_distances_for_llm(poi_list: list[dict]) -> list[dict]:
    """计算距离矩阵供LLM使用。"""
    distances = []
    for i, p1 in enumerate(poi_list):
        for j, p2 in enumerate(poi_list):
            if i < j and p1.get("lat") and p2.get("lat"):
                d = _haversine_km(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
                entry = {"from": p1["name"], "to": p2["name"], "km": round(d, 1)}
                if d > 15:
                    entry["warning"] = "⚠️跨区不推荐"
                distances.append(entry)
    return distances


_LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "横琴": (22.12, 113.53),
    "金湾": (22.08, 113.38),
    "金湾机场": (22.05, 113.38),
    "斗门": (22.22, 113.29),
    "唐家湾": (22.36, 113.58),
    "拱北": (22.23, 113.55),
    "香洲": (22.27, 113.57),
    "吉大": (22.25, 113.57),
    "湾仔": (22.20, 113.53),
    "华发": (22.24, 113.53),
    "井岸": (22.20, 113.30),
    "三灶": (22.08, 113.37),
}


def _get_short_trip_hint(avail_min: float) -> str:
    """获取短途提示。"""
    if avail_min >= 240:
        return ""
    max_stops = min(5, max(3, int(avail_min / 60)))
    return f"\n9. 【短途硬约束】可用时间仅{int(avail_min/60)}小时，安排{max_stops}站左右（含1-2站餐饮），每站停留30-45分钟即可，不用每站都深度体验"


def _get_location_coords(location: str) -> tuple[float, float] | None:
    """获取位置坐标。"""
    if not location:
        return None
    for name, coords in _LOCATION_COORDS.items():
        if name in location:
            return coords
    return None


async def _llm_assemble_route(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
    *,
    temperature: float = 0.1,
    strategy_hint: str = "",
) -> dict | None:
    """LLM编排路线，感知expert_weights影响推荐优先级。"""
    poi_list = _build_poi_list_for_llm(poi_proposals)
    food_list = _build_food_list_for_llm(food_proposals)
    hotel_list = _build_hotel_list_for_llm(hotel_proposals)
    traffic_order = (
        traffic_proposal.get("content", {}).get("suggested_order", []) if traffic_proposal else []
    )
    distances = _calc_distances_for_llm(poi_list)

    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")
    start_time = intent.get("time", {}).get("start", "09:00")
    end_time = intent.get("time", {}).get("end", "21:00")
    budget = intent.get("budget", {}).get("per_person", 0)

    avail_min = _calc_available_minutes(start_time, end_time)
    _max_stops_hint = _get_short_trip_hint(avail_min)
    location = intent.get("location") or ""
    _location_coords = _get_location_coords(location)
    _location_hint = ""
    if _location_coords:
        _location_hint = f"\n10. 【区域约束】用户在{location}附近（坐标{_location_coords[0]:.2f},{_location_coords[1]:.2f}），只选该区域5km内的POI，远距离的不要选"

    # 场景规则
    if scene_type == "美食型":
        diversity_rule = """7. 【美食场景规则·最重要·硬约束】
   - 这是一条美食探索路线！餐饮是主角，不是景点配角
   - 选3-5家餐厅，按时间排列：早茶/早点→午餐→下午茶→晚餐
   - 【子类型多样性·硬约束】餐厅类型必须多样，至少覆盖3种不同子类型：
     · 海鲜类（海鲜餐厅/鱼排/蚝）— 最多1家
     · 正餐类（粤菜/烧腊/煲仔/火锅/烧烤）— 最多1家
     · 小吃类（粉面粥/排档）— 最多1家
     · 茶餐厅/甜品/饮品 — 最多1家
     · 综合美食场所（夜市/美食街）— 最多1家
   - 禁止选2家同子类型的餐厅（如2家海鲜、2家茶餐厅都不行）
   - 海景咖啡馆不是餐厅！除非用户明确要咖啡馆，否则不要放进美食路线
   - 中间最多穿插1个散步点，不需要为了"多样性"硬塞景点/购物/文化"""
    elif scene_type == "目的地型":
        dest_center = intent.get("destination_center")
        dest_name = intent.get("destination_name", "")
        geo_rule = ""
        if dest_center:
            geo_rule = f"\n   - 所有站点必须在目的地坐标({dest_center[0]:.2f},{dest_center[1]:.2f})10km范围内，超出范围的POI直接排除"
        diversity_rule = f"""7. 【目的地场景规则】
   - 用户指定了{dest_name or '大景区'}，会在该景区待3-4小时（不是整天！）
   - 路线至少3-4站：核心景区 + 周边补充景点1-2个 + 附近餐饮1个
   - 不需要大范围跨区域{geo_rule}
   - 【时间节奏】核心景区上午到达，停留3-4小时，下午出来后去周边补充景点
   - 餐饮安排在景区游览之后（午餐12:00或晚餐18:00），不要在景区前安排远距离用餐
   - 如果只有半天（如下午场），路线精简为核心景点+附近一餐，不硬凑"""
    elif scene_type == "特种兵型":
        diversity_rule = """7. 【特种兵场景规则·硬约束】
   - 路线应覆盖尽可能多的类型：地标+自然+文化+娱乐+餐饮
   - 【地理硬约束】同区域景点必须连排！先走完一个区域再跳下一个区域
   - 禁止折返：如果已经从A区到了B区，不要再回A区
   - 单段距离>15km的跳跃最多1次（否则时间不够）
   - 餐饮穿插在赶场间隙，选快节奏的
   - 查看距离矩阵！标有"⚠️跨区不推荐"的不要排相邻"""
    elif scene_type == "休闲型":
        diversity_rule = """7. 【休闲场景规则】
   - 路线节奏慢、站点少（3-4个），每站停留时间长
   - 类型可以少但质量要高：1个好景点+1个好餐厅+1个休闲点"""
    else:
        diversity_rule = """7. 【观光场景规则】
   - 路线应包含至少3种类型（景点+餐饮+公园/文化等），避免全景点或全公园
   - 禁止为了多样性硬塞无关POI
   - VR馆/密室逃脱/攀岩等室内娱乐只在用户明确提及时才选，否则不选"""

    weight_desc = ", ".join(
        f"{k}={v:.1f}" for k, v in sorted(expert_weights.items(), key=lambda x: -x[1]) if v >= 0.3
    )

    system = f"""你是旅行路线编排专家。你需要把MoE专家精选的景点、餐厅、住宿组合成一条完整的一日游路线。

【最重要】你有权拒绝不合理的编排：
- 如果总时间<3小时，最多排3-4站，不要硬塞更多
- 如果景点分散在多个岛/区且交通时间>2小时，只保留一个区域，明确说明"舍弃了XX区域因为距离太远"
- 如果用户要求跳岛（如东澳岛+外伶仃岛），这是不可能一天完成的，只选一个岛，说明原因
- 如果候选POI地理跨度过大（>30km），只选最紧凑的一个区域
- 宁可排一条短而精的路线，也不要排一条长而散的烂路线

你的任务（按优先级）：
1. 【地理连贯·最重要】通过坐标判断地理位置紧凑性，同区域景点连走，绝不折返。
   - 禁止把横琴的景点和淇澳岛/唐家湾的景点排同一条路线（距离>20km）
   - 优先把坐标接近的POI排在相邻位置
   - 如果景点分散在多个区域，只选其中一个区域的，舍弃远的
2. 【时间节奏】按情绪曲线设计：
   - 上午({start_time}-12:00)：精力好，主力景点（地标/特色/户外）
   - 午餐(11:30-13:00)：选距离此时最近景点的餐厅
   - 下午(13:00-17:00)：次级景点或轻松项目
   - 晚餐(17:30-19:00)：选距离此时最近景点的餐厅
   - 傍晚/晚上：休闲收尾（海边/观景/夜景）
3. 【餐饮就近】餐厅必须插在距它最近的景点旁边
4. 【时间硬约束】总行程必须在{start_time}-{end_time}内完成
   - 如果时间塞不下所有POI，砍掉距离远的/评分低的，不要硬排
5. 【场景适配】{'亲子：景点间距要短，不超过5km' if group_type == '亲子' else ''}{'情侣：安排海滨/浪漫路线' if group_type == '情侣' else ''}{'特种兵：紧凑排列' if '特种兵' in pace else ''}
6. 【住宿尾置】如有住宿，放路线最后
7. 【距离硬约束】距离矩阵中标有"⚠️跨区不推荐"的景点对，禁止排在同一条路线中。
{diversity_rule}
8. 【用户意图优先·硬约束】
   - 景点必须全部出现在ordered_stops中（如果地理跨区太远，舍弃距离最远的那个）
   - 餐厅规则（非美食型）：午餐最多1家，晚餐最多1家，总共不超过2家，选地理位置最紧凑的
   - 餐厅规则（美食型）：不受2家限制，按第7条美食场景规则执行，可以选3-4家不同类型餐厅
   - 如果用户需求是"吃海鲜"，只选海鲜类餐厅，不要选咖啡馆/甜品店
   - 如果用户需求是"逛街拍照"，只选适合拍照逛街的地方，不要选VR馆/密室逃脱/攀岩等室内娱乐
   - 【关键词优先】如果用户明确提到"沙滩"/"海滩"/"海岛"/"温泉"/"公园"等关键词，路线中该类POI必须占50%以上，不要用无关类型凑数
   - 禁止为了"多样性"硬塞与用户意图无关的POI类型{_max_stops_hint}{_location_hint}

专家权重: {weight_desc}
{f"策略提示: {strategy_hint}" if strategy_hint else ""}

输出JSON格式：
{{"ordered_stops":[{{"name":"景点/餐厅名","type":"poi/lunch/dinner/hotel","reason":"为什么排这里"}}],"route_design":"路线设计思路（2句话）"}}
只输出JSON。"""

    user = f"""用户需求: {user_input}
场景类型: {scene_type}
群体: {group_type or '未知'}
节奏: {pace}
时间: {start_time}-{end_time}
预算: {'¥'+str(budget) if budget else '不限'}

景点精选（{len(poi_list)}个）:
{json.dumps(poi_list, ensure_ascii=False)}

餐厅精选（{len(food_list)}个）:
{json.dumps(food_list, ensure_ascii=False)}

{'住宿精选: ' + json.dumps(hotel_list, ensure_ascii=False) if hotel_list else '无需住宿'}

景点间距离:
{json.dumps(distances, ensure_ascii=False)}

交通建议顺序: {json.dumps(traffic_order, ensure_ascii=False) if traffic_order else '无'}

请编排最优路线。"""

    result = await _llm_decide(system, user, temperature=temperature)
    if not result or "ordered_stops" not in result:
        return None

    route = _build_route_from_llm_order(
        result["ordered_stops"], poi_proposals, food_proposals, hotel_proposals, intent
    )
    return route


# ── LLM stop处理 ──


def _build_name_map(proposal_lists: list[list[dict]]) -> dict[str, dict]:
    """从多个proposal列表构建name→content映射。"""
    name_map: dict[str, dict] = {}
    for proposals in proposal_lists:
        for p in proposals:
            name = p.get("content", {}).get("name", "")
            if name:
                name_map[name] = p.get("content", {})
    return name_map


def _fuzzy_match_name(name: str, name_map: dict[str, dict]) -> dict | None:
    """模糊匹配名称到content。"""
    if name in name_map:
        return name_map[name]

    for n, c in name_map.items():
        if name in n or n in name:
            return c

    clean = name.replace("（", "(").replace("）", ")").replace(" ", "")
    for n, c in name_map.items():
        clean_n = n.replace("（", "(").replace("）", ")").replace(" ", "")
        if clean in clean_n or clean_n in clean:
            return c

    return None


def _get_pace_params(pace: str) -> tuple[float, int]:
    """根据节奏返回 (stay_multiplier, travel_base)。"""
    if "特种兵" in pace:
        return 0.7, 10
    if "闲逛" in pace or "慢" in pace:
        return 1.3, 20
    return 1.0, 15


def _build_route_from_llm_order(
    ordered_stops: list[dict],
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    intent: dict,
) -> dict | None:
    name_map = _build_name_map([poi_proposals, food_proposals, hotel_proposals])
    stay_mult, travel_base = _get_pace_params(intent.get("pace", "平衡型"))

    start_time_str = intent.get("time", {}).get("start", "09:00")
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    steps = []
    prev_stop = None
    used_names: set[str] = set()

    for stop in ordered_stops:
        step, t, prev_stop = _process_llm_stop(
            stop, name_map, used_names, t, prev_stop, stay_mult, travel_base
        )
        if step:
            steps.append(step)

    if not steps:
        return None

    try:
        end_dt = datetime.strptime(intent.get("time", {}).get("end", "21:00"), "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")
    if end_dt <= datetime.strptime(start_time_str, "%H:%M"):
        end_dt += timedelta(days=1)

    steps = [s for s in steps if datetime.strptime(s["arrival_time"], "%H:%M") <= end_dt]
    return {"route": _enforce_time_windows(_dedup_route(steps))}


def _process_llm_stop(
    stop: dict,
    name_map: dict,
    used_names: set[str],
    t: datetime,
    prev_stop: dict | None,
    stay_mult: float,
    travel_base: int,
) -> tuple[dict | None, datetime, dict | None]:
    """处理单个LLM stop，返回 (step, new_time, new_prev_stop)。"""
    content = _fuzzy_match_name(stop.get("name", ""), name_map)
    if not content:
        return None, t, prev_stop

    canon = _canonical_name(stop.get("name", ""))
    if canon in used_names:
        return None, t, prev_stop
    used_names.add(canon)

    stop_type = stop.get("type", "poi")
    if stop_type == "hotel":
        return None, t, prev_stop
    stay_min = (
        50 if stop_type in ("lunch", "dinner") else int(content.get("avg_stay_min", 90) * stay_mult)
    )

    lat, lng = content.get("lat", 0), content.get("lng", 0)
    travel_min = travel_base
    if prev_stop and lat and lng and prev_stop.get("lat") and prev_stop.get("lng"):
        travel_min = max(
            5, min(60, int(_haversine_km(lat, lng, prev_stop["lat"], prev_stop["lng"]) * 8))
        )

    departure = t + timedelta(minutes=stay_min)
    step = {
        "poi": content,
        "arrival_time": t.strftime("%H:%M"),
        "departure_time": departure.strftime("%H:%M"),
        "travel_from_prev": {"distance_m": int(travel_min * 120), "time_min": travel_min},
        "_type": stop_type if stop_type != "poi" else "",
    }
    return step, departure + timedelta(minutes=travel_min), content


# ── 锦标赛：并行3策略竞争，启发式评分选最优 ──


async def _tournament_assemble(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
) -> dict | None:
    """并行跑3种策略，锦标赛选最优。"""
    strategies = [
        (
            "🏆 地理优先策略：最小化总路程，同区域景点连走，绝不折返。距离>10km的不要排在同一条路线。",
            0.1,
        ),
        (
            "🎯 类型优先策略：最大化类别多样性，确保覆盖景点+餐饮+文化/运动/购物等至少4种不同类型。宁可路线长一点也要保证多样性。",
            0.3,
        ),
        (
            "⭐ 体验优先策略：只选高评分POI(rating>=4.0)，宁缺毋滥。质量比数量重要，3个优质POI胜过8个平庸的。",
            0.2,
        ),
    ]

    tasks = [
        _llm_assemble_route(
            poi_proposals,
            food_proposals,
            hotel_proposals,
            traffic_proposal,
            intent,
            user_input,
            scene_type,
            expert_weights,
            temperature=t,
            strategy_hint=hint,
        )
        for hint, t in strategies
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    scored: list[tuple[float, dict]] = []
    for route in results:
        if route and isinstance(route, dict) and route.get("route"):
            score = _score_route_heuristic(route, poi_proposals, food_proposals, intent)
            scored.append((score, route))

    if not scored:
        for route in results:
            if isinstance(route, dict):
                return route
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


# ── 兜底 ──


def _build_fallback_narrative(route: dict) -> dict:
    steps = []
    for s in route.get("route", []):
        name = s.get("poi", {}).get("name", "未知")
        meal_type = s.get("_type", "")
        if meal_type:
            desc = f"在{name}享用{'午餐' if meal_type == 'lunch' else '晚餐'}"
        else:
            desc = f"前往{name}"
        steps.append({"description": desc, "emotion_design": "default"})
    return {"opening": "为您规划了以下行程：", "steps": steps, "closing": "祝您旅途愉快！"}


def _filter_fallback_proposals(proposals: list[dict], agent_types: tuple[str, ...]) -> list[dict]:
    """过滤兜底提案。"""
    return [
        p
        for p in proposals
        if p.get("agent") in agent_types
        and p.get("content", {}).get("name")
        and not _is_likely_macau(p.get("content", {}).get("name", ""))
    ]


def _nearest_neighbor_sort(contents: list[dict]) -> list[dict]:
    """最近邻排序。"""
    if not contents:
        return contents

    ordered = [contents[0]]
    remaining = contents[1:]
    while remaining:
        cur = ordered[-1]
        best = None
        best_d = float("inf")
        for r in remaining:
            d = (
                _haversine_km(cur["lat"], cur["lng"], r["lat"], r["lng"])
                if cur.get("lat") and r.get("lat")
                else 999
            )
            if d < best_d:
                best_d = d
                best = r
        if best:
            ordered.append(best)
            remaining.remove(best)
        else:
            break
    return ordered


def _fallback_assemble(proposals: list[dict], intent: dict) -> dict | None:
    """规则兜底组装。"""
    poi_proposals = _filter_fallback_proposals(proposals, ("poi", "poi_expert"))
    food_proposals = _filter_fallback_proposals(proposals, ("food", "food_expert"))
    _filter_fallback_proposals(proposals, ("hotel", "hotel_expert"))

    if not poi_proposals and not food_proposals:
        return None

    all_contents = [p.get("content", {}) for p in poi_proposals]
    for p in food_proposals:
        c = p.get("content", {})
        c["_food_flag"] = True
        all_contents.append(c)

    all_contents = _nearest_neighbor_sort(all_contents)

    try:
        t = datetime.strptime(intent.get("time", {}).get("start", "09:00"), "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    steps = []
    prev = None
    for c in all_contents:
        is_food = c.pop("_food_flag", False)
        stay_min = (
            50
            if is_food
            else int(c.get("avg_stay_min", 0)) or _category_stay_min(c.get("category", ""))
        )
        travel_min = 15
        if prev and c.get("lat") and prev.get("lat"):
            dist = _haversine_km(c["lat"], c["lng"], prev["lat"], prev["lng"])
            travel_min = max(5, min(60, int(dist * 8)))

        meal_type = ""
        if is_food:
            meal_type = "dinner" if t >= datetime.strptime("15:00", "%H:%M") else "lunch"

        steps.append(
            {
                "poi": c,
                "arrival_time": t.strftime("%H:%M"),
                "departure_time": (t + timedelta(minutes=stay_min)).strftime("%H:%M"),
                "travel_from_prev": {"distance_m": int(travel_min * 120), "time_min": travel_min},
                "_type": meal_type,
            }
        )
        t = t + timedelta(minutes=stay_min + travel_min)
        prev = c

    steps = _dedup_route(steps)
    steps = _enforce_time_windows(steps)

    total_time = 0
    try:
        end_t = datetime.strptime(steps[-1].get("departure_time", "18:00"), "%H:%M")
        start_t = datetime.strptime(steps[0].get("arrival_time", "09:00"), "%H:%M")
        total_time = int((end_t - start_t).total_seconds() / 60)
    except ValueError:
        total_time = len(steps) * 90

    return {
        "route": steps,
        "total_cost": {
            "time_min": total_time,
            "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
        },
        "emotion_curve": [],
    }


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════


_POI_AGENTS = {"poi", "poi_expert", "budget_hacker", "destination", "local_expert"}
_FOOD_AGENTS = {"food", "food_expert"}
_HOTEL_AGENTS = {"hotel", "hotel_expert"}


def _classify_proposals(
    proposals: list[dict],
) -> tuple[list[dict], list[dict], list[dict], dict | None]:
    """按agent类型分类提案。"""
    poi_proposals = [
        p
        for p in proposals
        if p.get("agent") in _POI_AGENTS
        and p.get("content", {}).get("name")
        and not _is_likely_macau(p.get("content", {}).get("name", ""))
    ]
    food_proposals = [
        p
        for p in proposals
        if p.get("agent") in _FOOD_AGENTS
        and p.get("content", {}).get("name")
        and not _is_likely_macau(p.get("content", {}).get("name", ""))
    ]
    hotel_proposals = [
        p
        for p in proposals
        if p.get("agent") in _HOTEL_AGENTS
        and p.get("content", {}).get("name")
        and not _is_likely_macau(p.get("content", {}).get("name", ""))
    ]
    traffic_proposal = next(
        (p for p in proposals if p.get("agent") in ("traffic", "traffic_expert")), None
    )
    return poi_proposals, food_proposals, hotel_proposals, traffic_proposal


def _post_process_single_day_route(
    route: dict, intent: dict, scene_type: str, pace: str, errors: list[str]
) -> None:
    """单日路线后处理。"""
    geo_threshold = 10.0 if scene_type == "目的地型" else _MAX_LEG_KM
    route["route"] = _geo_reroute(route["route"], max_leg_km=geo_threshold)
    new_steps, dropped = _rule_assign_times(route["route"], intent, scene_type, pace)
    route["route"] = new_steps
    if dropped:
        errors.append(f"规则时间分配砍站: {dropped}")

    start_time_str = intent.get("time", {}).get("start", "09:00")
    end_time_str = intent.get("time", {}).get("end", "21:00")
    route["route"] = _smooth_times(route["route"], start_time_str, end_time_str)

    steps = route.get("route", [])
    if steps:
        try:
            _s = datetime.strptime(steps[0].get("arrival_time", "09:00"), "%H:%M")
            _e = datetime.strptime(steps[-1].get("departure_time", "18:00"), "%H:%M")
            route["total_cost"] = {
                "time_min": int((_e - _s).total_seconds() / 60),
                "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
            }
        except ValueError:
            pass


def _apply_single_day_constraints(
    route: dict,
    proposals: list[dict],
    poi_proposals: list[dict],
    food_proposals: list[dict],
    intent: dict,
    scene_type: str,
    errors: list[str],
    prev_round_context: dict | None = None,
) -> None:
    """单日路线约束应用。"""
    if prev_round_context and route and route.get("route"):
        route = _must_keep_core_pois(route, prev_round_context, proposals)

    if route and route.get("route"):
        route = _cap_route_stops(route, scene_type, intent)
        try:
            _avail = (
                datetime.strptime(intent.get("time", {}).get("end", "21:00"), "%H:%M")
                - datetime.strptime(intent.get("time", {}).get("start", "09:00"), "%H:%M")
            ).total_seconds() / 60
        except ValueError:
            _avail = 720
        if _avail < 240:
            _short_max = min(5, max(3, int(_avail / 60)))
            steps = route.get("route", [])
            if len(steps) > _short_max:
                route["route"] = steps[:_short_max]

    if route and route.get("route"):
        route = _ensure_food_in_route(route, food_proposals, intent)
        route = _ensure_poi_in_route(route, poi_proposals, intent)
    if route and route.get("route") and food_proposals:
        route = _ensure_min_food_in_route(route, food_proposals, intent)
        route = _ensure_food_scene_food_count(route, food_proposals, scene_type)


async def _stream_single_day_steps(state: TravelState, route: dict) -> bool:
    """流式推送单日路线步骤。"""
    if not route or not route.get("route"):
        return False

    steps = route["route"]
    await sse_emit(
        state,
        "agent_result",
        {"agent": "synthesizer", "summary": f"正在推送 {len(steps)} 站路线..."},
    )
    for i, step in enumerate(steps):
        await sse_emit(
            state,
            "step",
            {
                "index": i + 1,
                "poi": step.get("poi", {}),
                "arrival_time": step.get("arrival_time"),
                "departure_time": step.get("departure_time"),
                "narrative": "",
                "emotion_design": "",
                "scene_tags": step.get("poi", {}).get("_scene_tags", []),
            },
        )
    return True


def _init_synthesizer_state(state: TravelState) -> tuple[dict, str, dict, list[str]]:
    """初始化synthesizer状态。"""
    intent = dict(state.get("user_intent", {}))
    if state.get("destination_center"):
        intent["destination_center"] = state["destination_center"]
    if state.get("destination_name"):
        intent["destination_name"] = state["destination_name"]
    return intent, state.get("scene_type", "观光型"), state.get("expert_weights", {}), []


async def synthesizer(state: TravelState) -> dict:
    """MoE Synthesizer：按expert_weights组装路线。"""
    meta = AGENT_META.get("synthesizer", {})
    await sse_emit(state, "agent_start", {"agent": "synthesizer", **meta})
    await sse_emit(
        state,
        "agent_thinking",
        {"agent": "synthesizer", "text": "收集提案，锦标赛并行3策略竞争..."},
    )

    proposals = list(state.get("reworked_proposals") or state.get("proposals", []))
    intent, scene_type, expert_weights, errors = _init_synthesizer_state(state)

    poi_proposals, food_proposals, hotel_proposals, traffic_proposal = _classify_proposals(
        proposals
    )

    if scene_type == "美食型" and len(poi_proposals) > 2:
        poi_proposals = sorted(
            poi_proposals, key=lambda p: p.get("content", {}).get("rating", 0), reverse=True
        )[:2]

    if not poi_proposals and not food_proposals:
        errors.append("无有效POI提案")
        return {"route": None, "narrative": None, "errors": errors}

    pace = intent.get("pace", "平衡型")
    route: dict | None = None
    _steps_streamed = False

    route = await _tournament_assemble(
        poi_proposals,
        food_proposals,
        hotel_proposals,
        traffic_proposal,
        intent,
        state.get("user_input", ""),
        scene_type,
        expert_weights,
    )
    if not route or not route.get("route"):
        route = _fallback_assemble(proposals, intent)

    if route and route.get("route"):
        _post_process_single_day_route(route, intent, scene_type, pace, errors)

    _apply_single_day_constraints(
        route,
        proposals,
        poi_proposals,
        food_proposals,
        intent,
        scene_type,
        errors,
        state.get("prev_round_context"),
    )
    _steps_streamed = await _stream_single_day_steps(state, route)

    narrative = None
    if route:
        try:
            from backend.services.narrator import generate_narrative

            narrative = await generate_narrative(
                route, intent, city=intent.get("city", "珠海"), enable_llm_polish=False
            )
        except Exception as e:
            errors.append(f"文案生成失败: {e}")
            narrative = _build_fallback_narrative(route)

    ret: dict = {"route": route, "narrative": narrative, "errors": errors}
    if _steps_streamed:
        ret["_steps_streamed"] = True
    return ret
