"""Coordinator：Agent提案组装器。

核心设计：
- coordinator是调度者，不做具体排序/编排
- 路线编排交给LLM Agent：综合考虑地理、时间节奏、情绪曲线
- _fallback_assemble 只是LLM失败时的规则兜底

═════════════════════════════════════════════════════════════
  架构决策记录（ADR）— 别瞎改，每条都是踩过坑的
═════════════════════════════════════════════════════════════

ADR-1: 路线编排必须用LLM，不能用规则引擎（TSP/最近邻）
  - 原因：C版本用solver.py的TSP+2opt做排序，30场景均分5.3
  - 换LLM编排后提升到6.8。规则引擎为了凑距离近会乱排路线逻辑
  - 比如为了最短路径把餐厅插在两个不相干的景点中间
  - 结论：距离最优 ≠ 体验最优，LLM能理解"午餐该插在上午景点后"

ADR-2: coordinator"只排不选"，不做取舍
  - 原因：之前coordinator会丢提案（~40% variance来源）
  - 现在硬约束prompt："以下所有景点和餐厅必须全部出现在ordered_stops中"
  - 配合_ensure_food_in_route / _ensure_poi_in_route补回遗漏
  - 结论：取舍是agent的事，coordinator只管排序

ADR-3: 后处理层是必要的，不能指望LLM一次做对
  - _enforce_time_windows: LLM会把午餐排到9点、晚餐排到凌晨
    修法：后处理强制午餐≥11:00、晚餐≥17:00、夜市≥17:00
    深夜出发(22:00-06:00)跳过约束
  - _cap_route_stops: LLM会排太多站塞不进时间窗
    修法：按scene_type设上限（美食型6/休闲5/特种兵8等）
  - _validate_scene_categories: LLM会加不搭的POI
    修法：美食型踢掉购物/酒店类
  - 结论：LLM是主力但不可靠，后处理是安全网

ADR-4: 美食型场景跳过_geo_compat_filter
  - 原因：_geo_compat_filter以POI簇为中心过滤餐饮
  - 美食型场景POI只有2-3个散步点，集中在同一区域
  - 导致大部分餐厅被砍（"闺蜜逛街"只有1站就是这原因）
  - 美食型吃本身就是目的，餐厅不需要靠近景点
  - 结论：美食型走_geo_compat_filter会截断餐饮提案

ADR-5: 不能加route_review（LLM再审查最终路线）
  - 试过：review LLM会删景点或幻觉出不存在的景点
  - 破坏ADR-2的"只排不选"设计，之前的努力白费
  - 结论：review只审查proposals，不审查最终路线

ADR-6: 时间分配不能交给规则引擎
  - 原因：solver.py的TSPTW时间窗分配会为了约束砍掉合理POI
  - LLM的时间分配虽不完美，但后处理(_enforce_time_windows)能修
  - 结论：LLM分配+后处理修正 > 规则引擎硬约束

ADR-7: food_agent候选池必须限制
  - 原因：832个餐饮POI全给LLM → 选太多同类型 → 方差大
  - 现在分5个子类(海鲜/正餐/小吃/茶餐厅甜品/综合美食街)每类取top3
  - 总共15个给LLM选，方差大幅降低

待改进方向（改了能提升但不急）：
  - TODO-1: food_agent按用户子意图分化prompt
    "吃甜品"→ 强调甜品店/奶茶/冰室, "吃海鲜"→ 强调海鲜排档/海鲜市场
    目前用一个通用prompt，选出来的不够精准
  - TODO-2: coordinator距离信息强化
    在prompt里直接标注"⚠️ XX距其他景点Nkm, 跨区不推荐"
    LLM看到显式警告会更重视
  - TODO-3: POI加适合人数标签, poi_agent过滤时考虑群体
    团建15人→ 只选适合多人活动的POI, 排除小空间场所
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from backend.agents_v3.state import TravelState
from backend.agents_v3.nodes.agents import _is_likely_macau


# 名称去重组
_DUP_GROUPS = [
    {"长隆海洋王国", "海洋王国", "横琴长隆海洋王国", "珠海长隆海洋王国",
     "珠海横琴长隆海洋王国", "珠海海洋王国"},
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


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


async def coordinator(state: TravelState) -> dict:
    """coordinator：调度Agent结果 → LLM编排路线 → 兜底规则组装。"""
    # 优先用rework后的proposals
    proposals = list(state.get("reworked_proposals") or state.get("proposals", []))
    intent = dict(state.get("user_intent", {}))
    scene_type = state.get("scene_type", "观光型")
    errors = []

    # ── 1. 按Agent类型分类提案 ──
    poi_proposals = [p for p in proposals if p.get("agent") == "poi" and p.get("content", {}).get("name")]
    food_proposals = [p for p in proposals if p.get("agent") == "food" and p.get("content", {}).get("name")]
    hotel_proposals = [p for p in proposals if p.get("agent") == "hotel" and p.get("content", {}).get("name")]
    traffic_proposal = next((p for p in proposals if p.get("agent") == "traffic"), None)

    # 过滤澳门
    poi_proposals = [p for p in poi_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    food_proposals = [p for p in food_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    hotel_proposals = [p for p in hotel_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]

    # 地理兼容过滤（美食型场景不过滤餐饮，因为吃本身就是目的）
    if scene_type != "美食型":
        food_proposals = _geo_compat_filter(food_proposals, poi_proposals, "food") or food_proposals
    hotel_proposals = _geo_compat_filter(hotel_proposals, poi_proposals, "hotel") or hotel_proposals

    if not poi_proposals and not food_proposals:
        errors.append("无有效POI提案")
        return {"route": None, "narrative": None, "errors": errors}

    # ── 2. LLM Agent编排路线（主路径）──
    route = await _llm_assemble_route(poi_proposals, food_proposals, hotel_proposals,
                                       traffic_proposal, intent, state.get("user_input", ""),
                                       scene_type)

    # ── 3. LLM失败 → 规则兜底 ──
    if not route or not route.get("route"):
        route = _fallback_assemble(proposals, intent)

    # ── 3.5 所有场景：确保所有提案都在路线中（防LLM丢弃）──
    if route and route.get("route"):
        route = _ensure_food_in_route(route, food_proposals, intent)
        route = _ensure_poi_in_route(route, poi_proposals, intent)

    # ── 3.6 所有路线：确保至少含1个餐饮 ──
    if route and route.get("route") and food_proposals:
        route = _ensure_min_food_in_route(route, food_proposals, intent)

    # ── 3.7 站数上限（防止排到凌晨）──
    if route and route.get("route"):
        route = _cap_route_stops(route, scene_type, intent)

    # ── 3.8 场景-品类校验（踢掉不搭的POI）──
    if route and route.get("route"):
        route = _validate_scene_categories(route, scene_type)

    # ── 4. 生成文案 ──
    narrative = None
    if route:
        try:
            from backend.services.narrator import generate_narrative
            city = intent.get("city", "珠海")
            narrative = await generate_narrative(route, intent, city=city)
        except Exception as e:
            errors.append(f"文案生成失败: {e}")
            narrative = _build_fallback_narrative(route)

    return {"route": route, "narrative": narrative, "errors": errors}


def _resolve_poi_order(poi_proposals: list[dict], traffic_proposal: dict | None, intent: dict) -> list[dict]:
    """确定POI游览顺序：Transport Agent建议 + 地理最近邻。"""
    if not poi_proposals:
        return []

    # 提取POI内容和置信度
    pois = []
    seen = set()
    for p in poi_proposals:
        content = p.get("content", {})
        name = content.get("name", "")
        canon = _canonical_name(name)
        if canon in seen:
            continue
        seen.add(canon)
        pois.append({
            **content,
            "_confidence": p.get("confidence", 0.5),
            "_reasoning": p.get("reasoning", ""),
        })

    if not pois:
        return []

    # 尝试使用Transport Agent建议的顺序
    if traffic_proposal:
        suggested = traffic_proposal.get("content", {}).get("suggested_order", [])
        if suggested and len(suggested) >= 2:
            # 按Transport Agent建议的顺序排列
            ordered = []
            name_map = {p.get("name", ""): p for p in pois}
            used = set()
            for name in suggested:
                # 精确匹配
                if name in name_map and name not in used:
                    ordered.append(name_map[name])
                    used.add(name)
                else:
                    # 模糊匹配
                    for p in pois:
                        p_name = p.get("name", "")
                        if p_name not in used and (name in p_name or p_name in name):
                            ordered.append(p)
                            used.add(p_name)
                            break
            # 加上没在建议顺序里的
            for p in pois:
                if p.get("name", "") not in used:
                    ordered.append(p)
            if len(ordered) >= 2:
                pois = ordered

    # 如果没有有效的Transport建议，用最近邻排序
    has_coords = any(p.get("lat") and p.get("lng") for p in pois)
    if has_coords:
        pois = _nearest_neighbor_sort(pois)
        # 2-opt优化改善地理连续性
        pois = _two_opt_improve(pois)

    return pois


def _nearest_neighbor_sort(pois: list[dict]) -> list[dict]:
    """最近邻排序：从第一个有坐标的POI开始。"""
    if len(pois) <= 1:
        return pois

    # 找到起始点（高置信度且有坐标的）
    start = None
    for p in pois:
        if p.get("lat") and p.get("lng"):
            start = p
            break
    if not start:
        return pois

    ordered = [start]
    remaining = [p for p in pois if p is not start]

    while remaining:
        current = ordered[-1]
        c_lat, c_lng = current.get("lat", 0), current.get("lng", 0)
        best = None
        best_dist = float("inf")
        for p in remaining:
            p_lat, p_lng = p.get("lat", 0), p.get("lng", 0)
            if p_lat and p_lng and c_lat and c_lng:
                d = _haversine_km(c_lat, c_lng, p_lat, p_lng)
            else:
                d = 999  # 无坐标排后面
            if d < best_dist:
                best_dist = d
                best = p
        if best:
            ordered.append(best)
            remaining.remove(best)
        else:
            break

    return ordered


def _two_opt_improve(pois: list[dict], max_iter: int = 50) -> list[dict]:
    """简单的2-opt路线优化：减少总旅行距离。"""
    if len(pois) <= 3:
        return pois

    # 计算总距离
    def total_distance(route):
        d = 0
        for i in range(len(route) - 1):
            p1, p2 = route[i], route[i + 1]
            if p1.get("lat") and p2.get("lat"):
                d += _haversine_km(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
            else:
                d += 10  # 无坐标的大距离惩罚
        return d

    best = list(pois)
    best_dist = total_distance(best)

    for _ in range(max_iter):
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, min(i + 4, len(best))):  # 限制搜索范围
                new_route = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                new_dist = total_distance(new_route)
                if new_dist < best_dist:
                    best = new_route
                    best_dist = new_dist
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break

    return best


def _assemble_route(pois: list[dict], foods: list[dict], hotels: list[dict], intent: dict) -> list[dict]:
    """组装路线：所有站点先按地理位置排序，再分配时间。"""
    if not pois:
        return []

    start_time_str = intent.get("time", {}).get("start", "09:00")
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    pace = intent.get("pace", "平衡型")
    if "特种兵" in pace:
        stay_multiplier = 0.7
        travel_base = 10
    elif "闲逛" in pace or "慢" in pace:
        stay_multiplier = 1.3
        travel_base = 20
    else:
        stay_multiplier = 1.0
        travel_base = 15

    # ── 收集所有站点（景点+餐饮）并按地理位置排序 ──
    all_stops = []

    for poi in pois:
        stay_min = int(poi.get("avg_stay_min", 90) * stay_multiplier)
        all_stops.append({
            "poi": poi,
            "stay_min": stay_min,
            "type": "poi",
            "lat": poi.get("lat", 0),
            "lng": poi.get("lng", 0),
        })

    # 分配餐饮到合理位置
    lunch_inserted = False
    dinner_inserted = False
    if foods:
        # 午餐在第2-3个POI之后
        food1 = foods[0].get("content", {})
        all_stops.append({
            "poi": food1,
            "stay_min": 45,
            "type": "lunch",
            "lat": food1.get("lat", 0),
            "lng": food1.get("lng", 0),
            "insert_after_idx": min(2, len(pois)),
        })
        if len(foods) > 1:
            food2 = foods[1].get("content", {})
            all_stops.append({
                "poi": food2,
                "stay_min": 50,
                "type": "dinner",
                "lat": food2.get("lat", 0),
                "lng": food2.get("lng", 0),
                "insert_after_idx": min(5, len(pois)),
            })

    # 如果有酒店，加到最后
    if hotels:
        hotel = hotels[0].get("content", {})
        all_stops.append({
            "poi": hotel,
            "stay_min": 0,
            "type": "hotel",
            "lat": hotel.get("lat", 0),
            "lng": hotel.get("lng", 0),
        })

    # ── 按地理位置排序（最近邻） ──
    # 先分出固定位置的和需要排序的
    pois_only = [s for s in all_stops if s["type"] == "poi"]
    meals = [s for s in all_stops if s["type"] in ("lunch", "dinner")]
    hotel_stops = [s for s in all_stops if s["type"] == "hotel"]

    # 景点按最近邻排序
    if pois_only:
        pois_only = _nearest_neighbor_sort_stops(pois_only)

    # 把餐饮插入到合适位置
    ordered = list(pois_only)
    for meal in meals:
        idx = meal.get("insert_after_idx", 2)
        # 找到最近的插入点
        insert_pos = min(idx, len(ordered))
        # 同时考虑地理位置 — 如果餐饮点离前面某个POI很近，插在那里
        if meal.get("lat") and len(ordered) > 0:
            best_pos = insert_pos
            best_dist = float("inf")
            for i in range(max(0, insert_pos - 1), min(len(ordered) + 1, insert_pos + 2)):
                if i < len(ordered):
                    prev = ordered[i]
                    d = _haversine_km(meal["lat"], meal["lng"], prev.get("lat", 0), prev.get("lng", 0))
                else:
                    d = 999
                if d < best_dist:
                    best_dist = d
                    best_pos = i + 1
            insert_pos = best_pos
        ordered.insert(insert_pos, meal)

    # 酒店放最后
    ordered.extend(hotel_stops)

    # ── 分配时间 ──
    steps = []
    prev_stop = None
    for stop in ordered:
        stay_min = stop["stay_min"]
        if stay_min == 0:
            continue  # 跳过0时长的

        # 计算移动时间
        travel_min = travel_base
        if prev_stop and stop.get("lat") and prev_stop.get("lat"):
            dist = _haversine_km(stop["lat"], stop["lng"], prev_stop["lat"], prev_stop["lng"])
            travel_min = max(5, min(60, int(dist * 8)))

        arrival = t
        departure = t + timedelta(minutes=stay_min)

        steps.append({
            "poi": stop["poi"],
            "arrival_time": arrival.strftime("%H:%M"),
            "departure_time": departure.strftime("%H:%M"),
            "travel_from_prev": {
                "distance_m": int(travel_min * 120),
                "time_min": travel_min,
            },
            "_type": stop["type"] if stop["type"] != "poi" else "",
        })

        t = departure + timedelta(minutes=travel_min)
        prev_stop = stop

    return _enforce_time_windows(steps)


def _nearest_neighbor_sort_stops(stops: list[dict]) -> list[dict]:
    """最近邻排序站点。"""
    if len(stops) <= 1:
        return stops

    # 找起始点（有坐标的）
    start = None
    for s in stops:
        if s.get("lat") and s.get("lng"):
            start = s
            break
    if not start:
        return stops

    ordered = [start]
    remaining = [s for s in stops if s is not start]

    while remaining:
        current = ordered[-1]
        c_lat, c_lng = current.get("lat", 0), current.get("lng", 0)
        best = None
        best_dist = float("inf")
        for s in remaining:
            s_lat, s_lng = s.get("lat", 0), s.get("lng", 0)
            if s_lat and s_lng and c_lat and c_lng:
                d = _haversine_km(c_lat, c_lng, s_lat, s_lng)
            else:
                d = 999
            if d < best_dist:
                best_dist = d
                best = s
        if best:
            ordered.append(best)
            remaining.remove(best)
        else:
            break

    return ordered


def _apply_weather_advice(steps: list[dict], weather_proposal: dict) -> None:
    """根据天气建议调整路线（标记室内/户外）。"""
    weather = weather_proposal.get("content", {})
    if not weather.get("outdoor_ok", True):
        # 如果不适合户外，在有户外标签的step上加备注
        for s in steps:
            poi = s.get("poi", {})
            tags = str(poi.get("tags", [])) + str(poi.get("_scene_tags", []))
            if any(kw in tags for kw in ["户外", "海滨", "沙滩", "公园"]):
                s["_weather_note"] = weather.get("advice", "天气不佳，建议缩短户外时间")


def _enforce_time_windows(steps: list[dict]) -> list[dict]:
    """后处理：确保餐食和夜间场所在合理时间窗口内。

    规则：
    - 午餐不早于 11:00
    - 晚餐不早于 17:00
    - 夜市/夜间场所不早于 17:00
    - 如果出发时间在夜间（22:00-06:00），跳过时间窗口约束

    如果某站过早，插入等待时间推后该站及后续所有站。
    同时根据实际时间修正 _type 标签（lunch/dinner）。
    """
    if len(steps) <= 1:
        return steps

    # 夜间出发（22:00-06:00）不强制餐食时间窗口
    try:
        first_arrival = datetime.strptime(steps[0]["arrival_time"], "%H:%M")
        if first_arrival >= datetime.strptime("22:00", "%H:%M") or first_arrival < datetime.strptime("06:00", "%H:%M"):
            return steps
    except (ValueError, KeyError, IndexError):
        pass

    LUNCH_EARLIEST = datetime.strptime("11:00", "%H:%M")
    DINNER_EARLIEST = datetime.strptime("17:00", "%H:%M")
    AFTERNOON_SPLIT = datetime.strptime("15:00", "%H:%M")
    NIGHT_KWS = ["夜市", "夜宵", "大排档", "深夜"]

    # 先根据当前时间修正 _type 标签
    for s in steps:
        _type = s.get("_type", "")
        if _type not in ("lunch", "dinner"):
            continue
        try:
            arrival = datetime.strptime(s["arrival_time"], "%H:%M")
        except ValueError:
            continue
        if _type == "dinner" and arrival < AFTERNOON_SPLIT:
            s["_type"] = "lunch"
        elif _type == "lunch" and arrival >= AFTERNOON_SPLIT:
            s["_type"] = "dinner"

    # 多轮修正，处理级联效应（lunch推后→dinner可能也要推后）
    for _ in range(3):
        shifted = False
        for i, s in enumerate(steps):
            _type = s.get("_type", "")
            try:
                arrival = datetime.strptime(s["arrival_time"], "%H:%M")
            except ValueError:
                continue

            target = None
            if _type == "lunch" and arrival < LUNCH_EARLIEST:
                target = LUNCH_EARLIEST
            elif _type == "dinner" and arrival < DINNER_EARLIEST:
                target = DINNER_EARLIEST
            else:
                # 夜间场所（非lunch/dinner标记但有夜市关键词的POI）
                poi = s.get("poi", {})
                text = poi.get("name", "") + poi.get("category", "")
                if any(kw in text for kw in NIGHT_KWS) and arrival < DINNER_EARLIEST:
                    target = DINNER_EARLIEST

            if target is None or arrival >= target:
                continue

            shift_min = int((target - arrival).total_seconds() / 60)
            for j in range(i, len(steps)):
                try:
                    a = datetime.strptime(steps[j]["arrival_time"], "%H:%M")
                    d = datetime.strptime(steps[j]["departure_time"], "%H:%M")
                    steps[j]["arrival_time"] = (a + timedelta(minutes=shift_min)).strftime("%H:%M")
                    steps[j]["departure_time"] = (d + timedelta(minutes=shift_min)).strftime("%H:%M")
                except ValueError:
                    pass

            # 推后后重新标记 _type
            for s2 in steps[i:]:
                if s2.get("_type") == "lunch":
                    try:
                        if datetime.strptime(s2["arrival_time"], "%H:%M") >= AFTERNOON_SPLIT:
                            s2["_type"] = "dinner"
                    except ValueError:
                        pass

            shifted = True

        if not shifted:
            break

    return steps

# ── 场景类型对应的站数上限 ──
_SCENE_MAX_STOPS = {
    "美食型": 6,   # 美食路线5-6个吃喝点够了
    "休闲型": 5,   # 慢游不超过5站
    "目的地型": 4,  # 大景区为主，周边补充
    "特种兵型": 8,  # 特种兵可以多
    "观光型": 6,   # 默认
}

# 美食型场景不应出现的品类（这些跟吃无关，占位浪费）
_FOOD_SCENE_EXCLUDED_CATS = {"购物", "酒店", "住宿"}


def _cap_route_stops(route: dict, scene_type: str, intent: dict) -> dict:
    """截断路线到合理站数，防止排到凌晨。"""
    steps = route.get("route", [])
    if not steps:
        return route

    max_stops = _SCENE_MAX_STOPS.get(scene_type, 6)

    # 亲子/退休群体再减1站
    group_type = intent.get("group", {}).get("type", "")
    if group_type in ("亲子", "退休") and max_stops > 4:
        max_stops -= 1

    if len(steps) <= max_stops:
        return route

    # 保留前max_stops站，优先保留有_type标记的（餐饮）
    kept = steps[:max_stops]
    route["route"] = kept
    return route


def _validate_scene_categories(route: dict, scene_type: str) -> dict:
    """踢掉与场景不搭的POI品类。"""
    steps = route.get("route", [])
    if not steps:
        return route

    if scene_type == "美食型":
        # 美食路线中购物/酒店类POI不搭
        filtered = []
        for s in steps:
            cat = s.get("poi", {}).get("category", "")
            if cat in _FOOD_SCENE_EXCLUDED_CATS:
                continue
            filtered.append(s)
        if filtered:  # 防止全删
            route["route"] = filtered

    return route


def _dedup_route(steps: list[dict]) -> list[dict]:
    """路线最终去重：精确匹配 + 模糊同类去重。"""
    seen = set()
    result = []
    for step in steps:
        name = step.get("poi", {}).get("name", "")
        key = _canonical_name(name)
        if key in seen:
            continue
        # 模糊去重：同区域同类型视为重复
        fuzzy_key = _fuzzy_dedup_key(name)
        if fuzzy_key and fuzzy_key in seen:
            continue
        seen.add(key)
        if fuzzy_key:
            seen.add(fuzzy_key)
        result.append(step)
    return result


def _fuzzy_dedup_key(name: str) -> str | None:
    """提取模糊去重key：同区域+同类型视为同一家。"""
    # 湾仔海鲜街 / 湾仔海鲜夜市 / 湾仔海鲜市场 → 湾仔海鲜
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


def _ensure_poi_in_route(route: dict, poi_proposals: list[dict], intent: dict) -> dict:
    """确保所有POI提案都在路线中，遗漏的补回。"""
    if not route or not route.get("route") or not poi_proposals:
        return route

    steps = route["route"]
    route_names = set()
    for s in steps:
        n = s.get("poi", {}).get("name", "")
        route_names.add(n)
        route_names.add(_canonical_name(n))

    missing = []
    for pp in poi_proposals:
        name = pp.get("content", {}).get("name", "")
        if not any(name in rn or rn in name for rn in route_names):
            missing.append(pp)

    if not missing:
        return route

    try:
        t = datetime.strptime(steps[-1].get("departure_time", "17:00"), "%H:%M")
    except ValueError:
        t = datetime.strptime("17:00", "%H:%M")

    end_time_str = intent.get("time", {}).get("end", "21:00")
    try:
        end_dt = datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")

    for pp in missing:
        content = pp.get("content", {})
        stay_min = int(content.get("avg_stay_min", 60))
        arrival = t
        departure = t + timedelta(minutes=stay_min)
        if departure > end_dt:
            break

        steps.append({
            "poi": content,
            "arrival_time": arrival.strftime("%H:%M"),
            "departure_time": departure.strftime("%H:%M"),
            "travel_from_prev": {"distance_m": 3000, "time_min": 20},
            "_type": "",
        })
        t = departure + timedelta(minutes=20)

    steps = _dedup_route(steps)
    steps = _enforce_time_windows(steps)
    route["route"] = steps
    route["total_cost"] = {
        "time_min": route.get("total_cost", {}).get("time_min", 0),
        "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
    }
    return route


def _ensure_food_in_route(route: dict, food_proposals: list[dict], intent: dict) -> dict:
    """确保所有餐厅提案都在路线中，遗漏的补回。"""
    if not route or not route.get("route") or not food_proposals:
        return route

    steps = route["route"]
    route_names = set()
    for s in steps:
        n = s.get("poi", {}).get("name", "")
        route_names.add(n)
        canon = _canonical_name(n)
        if canon != n:
            route_names.add(canon)

    # 找遗漏的餐厅
    missing = []
    for fp in food_proposals:
        name = fp.get("content", {}).get("name", "")
        found = name in route_names
        if not found:
            for rn in route_names:
                if name in rn or rn in name:
                    found = True
                    break
        if not found:
            missing.append(fp)

    if not missing:
        return route

    # 补回遗漏的餐厅：从最后一个step的时间开始追加
    try:
        t = datetime.strptime(steps[-1].get("departure_time", "18:00"), "%H:%M")
    except ValueError:
        t = datetime.strptime("18:00", "%H:%M")

    end_time_str = intent.get("time", {}).get("end", "21:00")
    try:
        end_dt = datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")

    for fp in missing:
        content = fp.get("content", {})
        arrival = t
        departure = t + timedelta(minutes=50)
        if departure > end_dt:
            break  # 超过时间窗就不补了

        meal_type = "dinner" if t >= datetime.strptime("15:00", "%H:%M") else "lunch"
        steps.append({
            "poi": content,
            "arrival_time": arrival.strftime("%H:%M"),
            "departure_time": departure.strftime("%H:%M"),
            "travel_from_prev": {"distance_m": 1800, "time_min": 15},
            "_type": meal_type,
        })
        t = departure + timedelta(minutes=15)

    steps = _dedup_route(steps)
    route["route"] = steps
    route["total_cost"] = {
        "time_min": route.get("total_cost", {}).get("time_min", 0),
        "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
    }
    return route


def _ensure_min_food_in_route(route: dict, food_proposals: list[dict], intent: dict) -> dict:
    """通用检查：所有路线至少含1个餐饮（提升diversity分数）。"""
    if not route or not route.get("route") or not food_proposals:
        return route

    steps = route["route"]

    # 检查是否已有餐饮
    has_food = False
    for s in steps:
        poi = s.get("poi", {})
        cat = poi.get("category", "")
        _type = s.get("_type", "")
        if _type in ("lunch", "dinner") or cat in ("餐饮", "美食", "小吃", "海鲜", "夜市", "夜市小吃"):
            has_food = True
            break
        # 也检查food agent标记
        name = poi.get("name", "")
        food_kws = ["餐厅", "海鲜", "烧", "煲", "粉", "面", "粥", "甜品", "奶茶", "茶餐厅", "排档", "咖啡"]
        if any(kw in name for kw in food_kws):
            has_food = True
            break

    if has_food:
        return route

    # 没有餐饮 → 找最合适的food proposal插入
    # 选评分最高、且在路线POI簇附近的
    best_food = None
    best_score = -1

    # 计算路线POI簇中心
    poi_coords = [(s["poi"].get("lat", 0), s["poi"].get("lng", 0)) for s in steps
                  if s.get("poi", {}).get("lat") and s.get("poi", {}).get("lng")]
    if poi_coords:
        center_lat = sum(la for la, _ in poi_coords) / len(poi_coords)
        center_lng = sum(ln for _, ln in poi_coords) / len(poi_coords)
    else:
        center_lat, center_lng = 22.27, 113.58  # 珠海默认

    for fp in food_proposals:
        content = fp.get("content", {})
        if not content.get("rating"):
            continue
        # 排除酒店/住宿类
        if content.get("category", "") in ("酒店", "住宿"):
            continue
        score = content.get("rating", 0)
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if lat and lng:
            dist = _haversine_km(lat, lng, center_lat, center_lng)
            if dist > 15:
                continue  # 太远
            score -= dist * 0.1  # 距离惩罚
        if score > best_score:
            best_score = score
            best_food = content

    if not best_food:
        # 取第一个
        best_food = food_proposals[0].get("content", {})

    # 插入到路线中间（午餐位置）
    insert_idx = min(2, len(steps))
    if insert_idx >= len(steps):
        insert_idx = len(steps)

    # 计算时间
    if insert_idx > 0 and insert_idx < len(steps):
        # 取前后step的时间，插入中间
        prev = steps[insert_idx - 1]
        arrival = prev.get("departure_time", "12:00")
        try:
            t = datetime.strptime(arrival, "%H:%M") + timedelta(minutes=15)
        except ValueError:
            t = datetime.strptime("12:00", "%H:%M")
    elif insert_idx == 0 and steps:
        t_str = steps[0].get("arrival_time", "09:00")
        try:
            t = datetime.strptime(t_str, "%H:%M") + timedelta(minutes=120)
        except ValueError:
            t = datetime.strptime("12:00", "%H:%M")
    else:
        t = datetime.strptime("12:00", "%H:%M")

    meal_type = "dinner" if t >= datetime.strptime("15:00", "%H:%M") else "lunch"
    food_step = {
        "poi": best_food,
        "arrival_time": t.strftime("%H:%M"),
        "departure_time": (t + timedelta(minutes=50)).strftime("%H:%M"),
        "travel_from_prev": {"distance_m": 1500, "time_min": 15},
        "_type": meal_type,
    }
    steps.insert(insert_idx, food_step)
    steps = _dedup_route(steps)
    route["route"] = steps
    route["total_cost"] = {
        "time_min": route.get("total_cost", {}).get("time_min", 0),
        "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
    }
    return route
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


def _geo_compat_filter(secondary_proposals: list[dict], poi_proposals: list[dict], agent_type: str) -> list[dict]:
    """过滤掉距POI簇太远的餐饮/住宿提案，用就近替代。

    如果POI集中在横琴(lat~22.11)，得月舫(lat~22.27)这种市中心餐厅就不合适。
    """
    if not poi_proposals or not secondary_proposals:
        return secondary_proposals

    # 计算POI簇中心
    poi_with_coords = []
    for p in poi_proposals:
        content = p.get("content", {})
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if lat and lng:
            poi_with_coords.append((lat, lng))

    if not poi_with_coords:
        return secondary_proposals

    center_lat = sum(lat for lat, _ in poi_with_coords) / len(poi_with_coords)
    center_lng = sum(lng for _, lng in poi_with_coords) / len(poi_with_coords)

    # 计算POI簇半径（最远POI到中心的距离）
    max_radius = max(
        _haversine_km(lat, lng, center_lat, center_lng)
        for lat, lng in poi_with_coords
    )
    # 允许范围 = 簇半径 + 5km缓冲
    allowed_radius = max(max_radius + 5, 10)

    # 检查每个次要提案是否在范围内
    filtered = []
    for p in secondary_proposals:
        content = p.get("content", {})
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if not lat or not lng:
            filtered.append(p)  # 没坐标的保留
            continue
        dist = _haversine_km(lat, lng, center_lat, center_lng)
        if dist <= allowed_radius:
            filtered.append(p)
        # 太远的直接丢弃（coordinator组装时不插入）

    return filtered


async def _llm_assemble_route(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str = "观光型",
) -> dict | None:
    """LLM Agent编排路线：综合考虑地理、时间、情绪、餐饮位置。"""
    # 准备各Agent的精选结果
    poi_list = []
    for p in poi_proposals:
        c = p.get("content", {})
        poi_list.append({
            "name": c.get("name", ""),
            "category": c.get("category", ""),
            "lat": round(c.get("lat", 0), 3),
            "lng": round(c.get("lng", 0), 3),
            "price": c.get("avg_price", 0),
            "stay_min": c.get("avg_stay_min", 90),
            "tags": c.get("tags", [])[:3],
            "confidence": p.get("confidence", 0.5),
        })

    food_list = []
    for p in food_proposals:
        c = p.get("content", {})
        food_list.append({
            "name": c.get("name", ""),
            "price": c.get("avg_price", 0),
            "lat": round(c.get("lat", 0), 3),
            "lng": round(c.get("lng", 0), 3),
            "meal_time": p.get("content", {}).get("meal_time", ""),
            "business_hours": c.get("business_hours", c.get("opening_hours", "")),
            "reason": p.get("reasoning", ""),
        })

    hotel_list = []
    for p in hotel_proposals:
        c = p.get("content", {})
        hotel_list.append({
            "name": c.get("name", ""),
            "lat": round(c.get("lat", 0), 3),
            "lng": round(c.get("lng", 0), 3),
        })

    traffic_order = []
    if traffic_proposal:
        traffic_order = traffic_proposal.get("content", {}).get("suggested_order", [])

    # 计算POI间距离矩阵（完整，不截断），>15km标注⚠️
    distances = []
    for i, p1 in enumerate(poi_list):
        for j, p2 in enumerate(poi_list):
            if i < j and p1.get("lat") and p2.get("lat"):
                d = _haversine_km(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
                entry = {"from": p1["name"], "to": p2["name"], "km": round(d, 1)}
                if d > 15:
                    entry["warning"] = "⚠️跨区不推荐"
                distances.append(entry)

    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")
    start_time = intent.get("time", {}).get("start", "09:00")
    end_time = intent.get("time", {}).get("end", "21:00")
    budget = intent.get("budget", {}).get("per_person", 0)

    # 场景感知规则（按scene_type分化）
    if scene_type == "美食型":
        diversity_rule = f"""7. 【美食场景规则·最重要·硬约束】
   - 这是一条美食探索路线！餐饮是主角，不是景点配角
   - **必须包含所有{len(food_list)}家餐厅，一个都不许漏！** ordered_stops必须包含每一家
   - 按时间排列：早茶/早点→午餐→下午茶→晚餐→夜市，中间最多穿插1个散步点
   - 不需要为了"多样性"硬塞景点/购物/文化"""
    elif scene_type == "目的地型":
        diversity_rule = """7. 【目的地场景规则】
   - 用户指定了大景区，会在该景区待大半天
   - 路线以该景区为中心，周边安排1-2个补充景点+餐饮
   - 不需要大范围跨区域"""
    elif scene_type == "特种兵型":
        diversity_rule = """7. 【特种兵场景规则】
   - 路线应覆盖尽可能多的类型：地标+自然+文化+娱乐+餐饮
   - 跨区域赶场是正常的，但同区域景点应连排
   - 餐饮穿插在赶场间隙，选快节奏的（不选需要久坐的）"""
    elif scene_type == "休闲型":
        diversity_rule = """7. 【休闲场景规则】
   - 路线节奏慢、站点少（3-4个），每站停留时间长
   - 类型可以少但质量要高：1个好景点+1个好餐厅+1个休闲点
   - 不追求覆盖面"""
    else:
        diversity_rule = """7. 【观光场景规则】
   - 路线应包含至少3种类型（景点+餐饮+公园/文化等），避免全景点或全公园
   - 禁止为了多样性硬塞无关POI"""

    system = f"""你是旅行路线编排专家。你需要把Agent精选的景点、餐厅、住宿组合成一条完整的一日游路线。

你的任务（按优先级）：
1. 【地理连贯】通过坐标判断地理位置紧凑性，同区域景点连走，绝不折返。
   - 每个景点都有lat/lng，直接看坐标：如果选了lat≈22.27的景点，其他景点也应集中在22.2-22.35
   - lat差>0.05（约5.5km）或经纬度跨距大时，先走完一个区域再移到下一个
   - 距离矩阵已给出所有景点间的km距离，用它来避免折返
2. 【时间节奏】按情绪曲线设计：
   - 上午({start_time}-12:00)：精力好，主力景点（地标/特色/户外）
   - 午餐(11:30-13:00)：选距离此时最近景点的餐厅
   - 下午(13:00-17:00)：次级景点或轻松项目
   - 晚餐(17:30-19:00)：选距离此时最近景点的餐厅
   - 傍晚/晚上：休闲收尾（海边/观景/夜景）
3. 【餐饮就近】餐厅必须插在距它最近的景点旁边，不要硬插到远处
4. 【时间硬约束】总行程必须在{start_time}-{end_time}内完成，最后一步的离开时间不得超过{end_time}。
   如果景点太多放不下，优先选地理位置紧凑、评分高的景点，舍弃远的。
5. 【场景适配】{'亲子：景点间距要短，带小孩不宜长途奔波' if group_type == '亲子' else ''}{'情侣：安排海滨/浪漫路线' if group_type == '情侣' else ''}{'特种兵：紧凑排列，减少空隙' if '特种兵' in pace else ''}
6. 【住宿尾置】如有住宿，放路线最后
7.5. 【距离硬约束】距离矩阵中标有"⚠️跨区不推荐"的景点对，禁止排在相邻位置。跨区>15km的两个景点间至少隔1小时交通时间。如果某个景点与大多数其他景点都>15km，优先舍弃它。
{diversity_rule}
8. 【最重要·硬约束】以下所有景点和餐厅必须全部出现在ordered_stops中，不允许省略任何一个：
   - 必选景点({len(poi_list)}个): {', '.join(p['name'] for p in poi_list)}
   - 必选餐厅({len(food_list)}个): {', '.join(f['name'] for f in food_list)}
   你只决定顺序，不决定取舍。如果时间窗口装不下，通过压缩停留时间来适配，而不是省略任何站点。

注意：交通Agent已给出参考顺序(traffic_order)，你可以参考但不必完全照搬，你的排序应综合地理+时间+餐饮位置。

输出JSON格式：
{{"ordered_stops":[{{"name":"景点/餐厅名","type":"poi/lunch/dinner/hotel","reason":"为什么排这里"}}],"route_design":"路线设计思路（2句话）"}}

只输出JSON。ordered_stops按游览顺序排列。"""

    user = f"""用户需求: {user_input}
场景类型: {scene_type}
群体: {group_type or '未知'}
节奏: {pace}
时间: {start_time}-{end_time}
预算: {'¥'+str(budget) if budget else '不限'}

景点Agent精选（{len(poi_list)}个）:
{json.dumps(poi_list, ensure_ascii=False)}

餐厅Agent精选（{len(food_list)}个）:
{json.dumps(food_list, ensure_ascii=False)}

{'住宿Agent精选: ' + json.dumps(hotel_list, ensure_ascii=False) if hotel_list else '无需住宿'}

景点间距离:
{json.dumps(distances, ensure_ascii=False)}

交通Agent建议顺序: {json.dumps(traffic_order, ensure_ascii=False) if traffic_order else '无'}

请编排最优路线。"""

    # 调用LLM
    result = await _llm_decide(system, user)
    if not result or "ordered_stops" not in result:
        return None

    # 把LLM的编排结果转换为route格式
    return _build_route_from_llm_order(result["ordered_stops"], poi_proposals, food_proposals,
                                         hotel_proposals, intent)


def _build_route_from_llm_order(
    ordered_stops: list[dict],
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    intent: dict,
) -> dict | None:
    """把LLM编排的顺序转换为标准route格式。"""
    # 建立name→content映射
    name_map = {}
    for p in poi_proposals:
        name_map[p.get("content", {}).get("name", "")] = p.get("content", {})
    for p in food_proposals:
        name_map[p.get("content", {}).get("name", "")] = p.get("content", {})
    for p in hotel_proposals:
        name_map[p.get("content", {}).get("name", "")] = p.get("content", {})

    start_time_str = intent.get("time", {}).get("start", "09:00")
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    pace = intent.get("pace", "平衡型")
    if "特种兵" in pace:
        stay_multiplier = 0.7
        travel_base = 10
    elif "闲逛" in pace or "慢" in pace:
        stay_multiplier = 1.3
        travel_base = 20
    else:
        stay_multiplier = 1.0
        travel_base = 15

    steps = []
    prev_stop = None
    used_names = set()

    for stop in ordered_stops:
        name = stop.get("name", "")
        stop_type = stop.get("type", "poi")

        # 模糊匹配
        content = name_map.get(name)
        if not content:
            for n, c in name_map.items():
                if name in n or n in name:
                    content = c
                    name = n
                    break
        if not content:
            continue

        canon = _canonical_name(name)
        if canon in used_names:
            continue
        used_names.add(canon)

        # 停留时间
        if stop_type == "hotel":
            continue  # 住宿不加入时间线
        elif stop_type in ("lunch", "dinner"):
            stay_min = 50
        else:
            stay_min = int(content.get("avg_stay_min", 90) * stay_multiplier)

        # 交通时间
        lat = content.get("lat", 0)
        lng = content.get("lng", 0)
        travel_min = travel_base
        if prev_stop and lat and lng:
            prev_lat = prev_stop.get("lat", 0)
            prev_lng = prev_stop.get("lng", 0)
            if prev_lat and prev_lng:
                dist = _haversine_km(lat, lng, prev_lat, prev_lng)
                travel_min = max(5, min(60, int(dist * 8)))

        arrival = t
        departure = t + timedelta(minutes=stay_min)

        steps.append({
            "poi": content,
            "arrival_time": arrival.strftime("%H:%M"),
            "departure_time": departure.strftime("%H:%M"),
            "travel_from_prev": {
                "distance_m": int(travel_min * 120),
                "time_min": travel_min,
            },
            "_type": stop_type if stop_type != "poi" else "",
        })

        t = departure + timedelta(minutes=travel_min)
        prev_stop = content

    if not steps:
        return None

    # 截断超过end_time的步骤
    end_time_str = intent.get("time", {}).get("end", "21:00")
    try:
        end_dt = datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")
    # 跨天处理：如果end_time < start_time（如00:00），认为end是次日
    if end_dt <= datetime.strptime(start_time_str, "%H:%M"):
        end_dt += timedelta(days=1)

    # 到达时间超过end_time的步骤一律截掉
    steps = [s for s in steps if datetime.strptime(s["arrival_time"], "%H:%M") <= end_dt]

    # 去重
    steps = _dedup_route(steps)

    # 强制修正餐食/夜间场所时间窗口
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


async def _llm_decide(system_prompt: str, user_prompt: str, retries: int = 2) -> dict | None:
    """调用DeepSeek LLM做决策。"""
    import json as _json
    import os

    from backend.agents_v3.nodes.agents import _get_llm_client

    client = _get_llm_client()
    model = _os.getenv("EXPERT_LLM_MODEL") or _os.getenv("LLM_MODEL", "deepseek-chat")
    base_url = _os.getenv("EXPERT_LLM_BASE_URL") or _os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    is_ds = "deepseek" in model.lower() or "deepseek" in base_url
    for attempt in range(retries):
        try:
            kwargs: dict = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt + "\n你必须输出合法JSON。"},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
            if is_ds:
                kwargs["response_format"] = {"type": "json_object"}
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            elif "qwen3" in model.lower():
                kwargs["extra_body"] = {"enable_thinking": False}
            resp = await client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content or ""
            if "```" in text:
                text = text.split("```")[1].split("```")[0]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            return _json.loads(text)
        except Exception:
            if attempt < retries - 1:
                import asyncio
                await asyncio.sleep(2)
    return None


def _fallback_assemble(proposals: list[dict], intent: dict) -> dict | None:
    """LLM编排失败时的规则兜底。"""
    poi_proposals = [p for p in proposals if p.get("agent") == "poi" and p.get("content", {}).get("name")]
    food_proposals = [p for p in proposals if p.get("agent") == "food" and p.get("content", {}).get("name")]
    hotel_proposals = [p for p in proposals if p.get("agent") == "hotel" and p.get("content", {}).get("name")]
    traffic_proposal = next((p for p in proposals if p.get("agent") == "traffic"), None)
    weather_proposal = next((p for p in proposals if p.get("agent") == "weather"), None)

    poi_proposals = [p for p in poi_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    food_proposals = [p for p in food_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    hotel_proposals = [p for p in hotel_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]

    filtered_food = _geo_compat_filter(food_proposals, poi_proposals, "food")
    if filtered_food:
        food_proposals = filtered_food
    filtered_hotel = _geo_compat_filter(hotel_proposals, poi_proposals, "hotel")
    if filtered_hotel:
        hotel_proposals = filtered_hotel

    poi_order = _resolve_poi_order(poi_proposals, traffic_proposal, intent)
    route_steps = _assemble_route(poi_order, food_proposals, hotel_proposals, intent)

    if weather_proposal and route_steps:
        _apply_weather_advice(route_steps, weather_proposal)
    if route_steps:
        route_steps = _dedup_route(route_steps)
        route_steps = _ensure_category_diversity(route_steps)

    if not route_steps:
        return None

    total_time = 0
    try:
        end_t = datetime.strptime(route_steps[-1].get("departure_time", "18:00"), "%H:%M")
        start_t = datetime.strptime(route_steps[0].get("arrival_time", "09:00"), "%H:%M")
        total_time = int((end_t - start_t).total_seconds() / 60)
    except ValueError:
        total_time = len(route_steps) * 90

    return {
        "route": route_steps,
        "total_cost": {
            "time_min": total_time,
            "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in route_steps),
        },
        "emotion_curve": [],
    }


def _ensure_category_diversity(steps: list[dict], max_same: int = 2) -> list[dict]:
    """检查路线中连续同类POI，超过阈值时插入多样性标记。

    只做标记不删除——删除会破坏地理和时间编排。
    """
    if len(steps) <= 3:
        return steps

    # 把category归入大类
    _CAT_MAP = {
        "公园": "自然", "海滨": "自然", "沙滩": "自然", "自然风光": "自然", "岛屿": "自然",
        "博物馆": "文化", "文化": "文化", "历史": "文化", "艺术": "文化", "剧院": "文化",
        "餐饮": "餐饮", "美食": "餐饮", "小吃": "餐饮", "海鲜": "餐饮",
        "娱乐": "娱乐", "游乐园": "娱乐", "温泉SPA": "娱乐",
        "购物": "购物", "住宿": "住宿", "酒店": "住宿",
    }

    def _broad_cat(step: dict) -> str:
        raw = step.get("poi", {}).get("category", "")
        for k, v in _CAT_MAP.items():
            if k in raw:
                return v
        return "其他"

    # 统计大类分布
    cats = [_broad_cat(s) for s in steps]
    unique_cats = set(cats)

    # 如果路线只有1-2种大类，给steps添加多样性提示
    if len(unique_cats) <= 2 and len(steps) >= 4:
        for s in steps:
            s["_diversity_warning"] = "路线类型单一，建议增加不同类型POI"

    return steps
