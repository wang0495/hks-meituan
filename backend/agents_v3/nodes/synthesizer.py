"""Synthesizer：MoE提案按权重组装路线。

替代coordinator，简化：
- 删除 _geo_compat_filter（专家内部处理地理）
- 删除 _validate_scene_categories（专家保证品类正确）
- 简化 _llm_assemble_route（感知expert_weights）
- 保留: _enforce_time_windows, _cap_route_stops, _dedup_route
- 保留轻量: _ensure_food_in_route, _ensure_poi_in_route, _ensure_min_food_in_route
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from backend.agents_v3.experts.base import (
    _haversine_km,
    _is_likely_macau,
    _llm_decide,
)
from backend.agents_v3.state import TravelState


# ── 名称去重组 ──
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


# ── 时间窗口强制修正 ──
def _enforce_time_windows(steps: list[dict]) -> list[dict]:
    """后处理：确保餐食和夜间场所在合理时间窗口内。"""
    if len(steps) <= 1:
        return steps

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


# ── 补回遗漏 ──
def _ensure_poi_in_route(route: dict, poi_proposals: list[dict], intent: dict) -> dict:
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
            break

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
    """安全网：确保路线至少含1个餐饮。"""
    if not route or not route.get("route") or not food_proposals:
        return route

    steps = route["route"]
    has_food = False
    for s in steps:
        poi = s.get("poi", {})
        cat = poi.get("category", "")
        _type = s.get("_type", "")
        if _type in ("lunch", "dinner") or cat in ("餐饮", "美食", "小吃", "海鲜", "夜市", "夜市小吃"):
            has_food = True
            break
        name = poi.get("name", "")
        food_kws = ["餐厅", "海鲜", "烧", "煲", "粉", "面", "粥", "甜品", "奶茶", "茶餐厅", "排档", "咖啡"]
        if any(kw in name for kw in food_kws):
            has_food = True
            break

    if has_food:
        return route

    poi_coords = [(s["poi"].get("lat", 0), s["poi"].get("lng", 0)) for s in steps
                  if s.get("poi", {}).get("lat") and s.get("poi", {}).get("lng")]
    if poi_coords:
        center_lat = sum(la for la, _ in poi_coords) / len(poi_coords)
        center_lng = sum(ln for _, ln in poi_coords) / len(poi_coords)
    else:
        center_lat, center_lng = 22.27, 113.58

    best_food = None
    best_score = -1
    for fp in food_proposals:
        content = fp.get("content", {})
        if not content.get("rating"):
            continue
        if content.get("category", "") in ("酒店", "住宿"):
            continue
        score = content.get("rating", 0)
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if lat and lng:
            dist = _haversine_km(lat, lng, center_lat, center_lng)
            if dist > 15:
                continue
            score -= dist * 0.1
        if score > best_score:
            best_score = score
            best_food = content

    if not best_food:
        best_food = food_proposals[0].get("content", {})

    insert_idx = min(2, len(steps))
    if insert_idx > 0 and insert_idx < len(steps):
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


# ── LLM路线编排 ──
async def _llm_assemble_route(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
) -> dict | None:
    """LLM编排路线，感知expert_weights影响推荐优先级。"""
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
            "expert": p.get("agent", "poi"),
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

    # 距离矩阵
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

    # 场景规则
    if scene_type == "美食型":
        diversity_rule = f"""7. 【美食场景规则·最重要·硬约束】
   - 这是一条美食探索路线！餐饮是主角，不是景点配角
   - 最多选4家餐厅：早茶/早点→午餐→下午茶→晚餐，按时间排列
   - 超过4家时，优先选与主题最匹配的（如海鲜主题优先海鲜餐厅）
   - 中间最多穿插1个散步点，不需要为了"多样性"硬塞景点/购物/文化"""
    elif scene_type == "目的地型":
        diversity_rule = """7. 【目的地场景规则】
   - 用户指定了大景区，会在该景区待大半天
   - 路线以该景区为中心，周边安排1-2个补充景点+餐饮
   - 不需要大范围跨区域"""
    elif scene_type == "特种兵型":
        diversity_rule = """7. 【特种兵场景规则】
   - 路线应覆盖尽可能多的类型：地标+自然+文化+娱乐+餐饮
   - 跨区域赶场是正常的，但同区域景点应连排
   - 餐饮穿插在赶场间隙，选快节奏的"""
    elif scene_type == "休闲型":
        diversity_rule = """7. 【休闲场景规则】
   - 路线节奏慢、站点少（3-4个），每站停留时间长
   - 类型可以少但质量要高：1个好景点+1个好餐厅+1个休闲点"""
    else:
        diversity_rule = """7. 【观光场景规则】
   - 路线应包含至少3种类型（景点+餐饮+公园/文化等），避免全景点或全公园
   - 禁止为了多样性硬塞无关POI"""

    # 专家权重摘要（让LLM知道哪些专家权重高）
    weight_desc = ", ".join(f"{k}={v:.1f}" for k, v in sorted(expert_weights.items(), key=lambda x: -x[1]) if v >= 0.3)

    system = f"""你是旅行路线编排专家。你需要把MoE专家精选的景点、餐厅、住宿组合成一条完整的一日游路线。

你的任务（按优先级）：
1. 【地理连贯】通过坐标判断地理位置紧凑性，同区域景点连走，绝不折返。
2. 【时间节奏】按情绪曲线设计：
   - 上午({start_time}-12:00)：精力好，主力景点（地标/特色/户外）
   - 午餐(11:30-13:00)：选距离此时最近景点的餐厅
   - 下午(13:00-17:00)：次级景点或轻松项目
   - 晚餐(17:30-19:00)：选距离此时最近景点的餐厅
   - 傍晚/晚上：休闲收尾（海边/观景/夜景）
3. 【餐饮就近】餐厅必须插在距它最近的景点旁边
4. 【时间硬约束】总行程必须在{start_time}-{end_time}内完成
5. 【场景适配】{'亲子：景点间距要短' if group_type == '亲子' else ''}{'情侣：安排海滨/浪漫路线' if group_type == '情侣' else ''}{'特种兵：紧凑排列' if '特种兵' in pace else ''}
6. 【住宿尾置】如有住宿，放路线最后
7.5. 【距离硬约束】距离矩阵中标有"⚠️跨区不推荐"的景点对，禁止排在相邻位置。
{diversity_rule}
8. 【最重要·硬约束】以下景点必须全部出现在ordered_stops中：
   - 必选景点({len(poi_list)}个): {', '.join(p['name'] for p in poi_list)}
   - 可选餐厅({len(food_list)}个): {', '.join(f['name'] for f in food_list)}
   餐厅规则：午餐最多选1家，晚餐最多选1家，总共不超过2家。从候选餐厅中选地理位置最紧凑的。

专家权重: {weight_desc}

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

    result = await _llm_decide(system, user)
    if not result or "ordered_stops" not in result:
        return None

    return _build_route_from_llm_order(result["ordered_stops"], poi_proposals, food_proposals,
                                         hotel_proposals, intent)


def _build_route_from_llm_order(
    ordered_stops: list[dict],
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    intent: dict,
) -> dict | None:
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

        if stop_type == "hotel":
            continue
        elif stop_type in ("lunch", "dinner"):
            stay_min = 50
        else:
            stay_min = int(content.get("avg_stay_min", 90) * stay_multiplier)

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

    end_time_str = intent.get("time", {}).get("end", "21:00")
    try:
        end_dt = datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")
    if end_dt <= datetime.strptime(start_time_str, "%H:%M"):
        end_dt += timedelta(days=1)

    steps = [s for s in steps if datetime.strptime(s["arrival_time"], "%H:%M") <= end_dt]
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


# ── 规则兜底 ──
def _fallback_assemble(proposals: list[dict], intent: dict) -> dict | None:
    poi_proposals = [p for p in proposals if p.get("agent") in ("poi", "poi_expert") and p.get("content", {}).get("name")]
    food_proposals = [p for p in proposals if p.get("agent") in ("food", "food_expert") and p.get("content", {}).get("name")]
    hotel_proposals = [p for p in proposals if p.get("agent") in ("hotel", "hotel_expert") and p.get("content", {}).get("name")]

    poi_proposals = [p for p in poi_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    food_proposals = [p for p in food_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    hotel_proposals = [p for p in hotel_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]

    if not poi_proposals and not food_proposals:
        return None

    # 简单最近邻排序
    all_contents = []
    for p in poi_proposals:
        c = p.get("content", {})
        all_contents.append(c)
    for p in food_proposals:
        c = p.get("content", {})
        c["_food_flag"] = True
        all_contents.append(c)

    # 最近邻排序
    if all_contents:
        ordered = [all_contents[0]]
        remaining = all_contents[1:]
        while remaining:
            cur = ordered[-1]
            best = None
            best_d = float("inf")
            for r in remaining:
                if cur.get("lat") and r.get("lat"):
                    d = _haversine_km(cur["lat"], cur["lng"], r["lat"], r["lng"])
                else:
                    d = 999
                if d < best_d:
                    best_d = d
                    best = r
            if best:
                ordered.append(best)
                remaining.remove(best)
            else:
                break
        all_contents = ordered

    start_time_str = intent.get("time", {}).get("start", "09:00")
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    steps = []
    prev = None
    for c in all_contents:
        is_food = c.pop("_food_flag", False)
        stay_min = 50 if is_food else int(c.get("avg_stay_min", 90))
        travel_min = 15
        if prev and c.get("lat") and prev.get("lat"):
            dist = _haversine_km(c["lat"], c["lng"], prev["lat"], prev["lng"])
            travel_min = max(5, min(60, int(dist * 8)))

        meal_type = ""
        if is_food:
            meal_type = "dinner" if t >= datetime.strptime("15:00", "%H:%M") else "lunch"

        steps.append({
            "poi": c,
            "arrival_time": t.strftime("%H:%M"),
            "departure_time": (t + timedelta(minutes=stay_min)).strftime("%H:%M"),
            "travel_from_prev": {"distance_m": int(travel_min * 120), "time_min": travel_min},
            "_type": meal_type,
        })
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
async def synthesizer(state: TravelState) -> dict:
    """MoE Synthesizer：按expert_weights组装路线。"""
    proposals = list(state.get("reworked_proposals") or state.get("proposals", []))
    intent = dict(state.get("user_intent", {}))
    scene_type = state.get("scene_type", "观光型")
    expert_weights = state.get("expert_weights", {})
    errors = []

    # 按agent类型分类（兼容新旧agent名）
    _POI_AGENTS = {"poi", "poi_expert"}
    _FOOD_AGENTS = {"food", "food_expert"}
    _HOTEL_AGENTS = {"hotel", "hotel_expert"}

    poi_proposals = [p for p in proposals if p.get("agent") in _POI_AGENTS and p.get("content", {}).get("name")]
    food_proposals = [p for p in proposals if p.get("agent") in _FOOD_AGENTS and p.get("content", {}).get("name")]
    hotel_proposals = [p for p in proposals if p.get("agent") in _HOTEL_AGENTS and p.get("content", {}).get("name")]
    traffic_proposal = next((p for p in proposals if p.get("agent") in ("traffic", "traffic_expert")), None)

    # 过滤澳门
    poi_proposals = [p for p in poi_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    food_proposals = [p for p in food_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]
    hotel_proposals = [p for p in hotel_proposals if not _is_likely_macau(p.get("content", {}).get("name", ""))]

    if not poi_proposals and not food_proposals:
        errors.append("无有效POI提案")
        return {"route": None, "narrative": None, "errors": errors}

    # LLM编排
    route = await _llm_assemble_route(
        poi_proposals, food_proposals, hotel_proposals,
        traffic_proposal, intent, state.get("user_input", ""),
        scene_type, expert_weights,
    )

    if not route or not route.get("route"):
        route = _fallback_assemble(proposals, intent)

    # 补回遗漏
    if route and route.get("route"):
        route = _ensure_food_in_route(route, food_proposals, intent)
        route = _ensure_poi_in_route(route, poi_proposals, intent)

    if route and route.get("route") and food_proposals:
        route = _ensure_min_food_in_route(route, food_proposals, intent)

    # 站数上限
    if route and route.get("route"):
        route = _cap_route_stops(route, scene_type, intent)

    # 文案
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
