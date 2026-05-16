"""Synthesizer：MoE提案按权重组装路线。

替代coordinator，简化：
- 删除 _geo_compat_filter（专家内部处理地理）
- 删除 _validate_scene_categories（专家保证品类正确）
- 简化 _llm_assemble_route（感知expert_weights）
- 保留: _enforce_time_windows, _cap_route_stops, _dedup_route
- 保留轻量: _ensure_food_in_route, _ensure_poi_in_route, _ensure_min_food_in_route

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
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import datetime, timedelta

from backend.agents_v3.experts.base import (
    _haversine_km,
    _is_likely_macau,
    _llm_decide,
)
from backend.agents_v3.state import TravelState, AGENT_META, sse_emit

# ── 合成器架构模式 ──
# "default": 单次LLM组装（基线）
# "best_of_n": 多候选投票，跑N次取最优
# "geo_cluster": 地理聚类+TSP排序
# "self_refine": 维度导向自精炼
# "tournament": 并行策略锦标赛
# "constraint": 迭代约束满足
SYNTHESIZER_MODE = os.getenv("SYNTHESIZER_MODE", "tournament")


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
    *,
    temperature: float = 0.1,
    strategy_hint: str = "",
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
            "category": c.get("category", ""),
            "price": c.get("avg_price", 0),
            "rating": c.get("rating", 0),
            "tags": c.get("tags", [])[:3],
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
   - 选3-5家餐厅，按时间排列：早茶/早点→午餐→下午茶→晚餐
   - 餐厅类型必须多样：至少覆盖2种不同类型（如海鲜+小吃、正餐+甜品、茶餐厅+夜市）
   - 超过4家时，优先选与主题最匹配的（如海鲜主题只选海鲜餐厅/海鲜市场/海鲜夜市，不要选咖啡馆/甜品店）
   - 海景咖啡馆不是餐厅！除非用户明确要咖啡馆，否则不要放进美食路线
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
   - 禁止为了多样性硬塞无关POI
   - VR馆/密室逃脱/攀岩等室内娱乐只在用户明确提及时才选，否则不选"""

    # 专家权重摘要（让LLM知道哪些专家权重高）
    weight_desc = ", ".join(f"{k}={v:.1f}" for k, v in sorted(expert_weights.items(), key=lambda x: -x[1]) if v >= 0.3)

    system = f"""你是旅行路线编排专家。你需要把MoE专家精选的景点、餐厅、住宿组合成一条完整的一日游路线。

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
   - 禁止为了"多样性"硬塞与用户意图无关的POI类型

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
            # 模糊匹配：name_map的key包含stop名，或stop名包含key
            for n, c in name_map.items():
                if name in n or n in name:
                    content = c
                    name = n
                    break
        if not content:
            # 二次模糊：去掉括号/空格后再匹配
            clean = name.replace("（", "(").replace("）", ")").replace(" ", "")
            for n, c in name_map.items():
                clean_n = n.replace("（", "(").replace("）", ")").replace(" ", "")
                if clean in clean_n or clean_n in clean:
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


# ═══════════════════════════════════════════════════════════
# 启发式路线评分（不调LLM，用于多候选比较）
# ═══════════════════════════════════════════════════════════

def _score_route_heuristic(
    route: dict,
    poi_proposals: list[dict],
    food_proposals: list[dict],
    intent: dict,
) -> float:
    """启发式评分路线质量(0-100)，越高越好。不调LLM，纯规则。

    评分维度（与evaluator对齐）:
    - geo_continuity (权重40): 总距离越短越好
    - diversity (权重25): 唯一类别越多越好
    - coverage (权重20): 覆盖了多少expert提案
    - time_fit (权重15): 时间利用率
    """
    steps = route.get("route", [])
    if not steps:
        return -1.0

    # ── 1. 地理连续性 (0-25) ──
    total_dist = 0.0
    max_segment = 0.0
    for i in range(1, len(steps)):
        prev = steps[i - 1].get("poi", {})
        cur = steps[i].get("poi", {})
        lat1, lng1 = prev.get("lat", 0), prev.get("lng", 0)
        lat2, lng2 = cur.get("lat", 0), cur.get("lng", 0)
        if lat1 and lat2:
            d = _haversine_km(lat1, lng1, lat2, lng2)
            total_dist += d
            max_segment = max(max_segment, d)
    # 0km总距离=25分, 每增加1km扣0.5分; 单段超过15km额外扣分
    geo_score = max(0, 25 - total_dist * 0.5)
    if max_segment > 15:
        geo_score -= (max_segment - 15) * 2  # 跨区大惩罚

    # ── 2. 类别多样性 (0-25) ──
    categories = set()
    for s in steps:
        cat = s.get("poi", {}).get("category", "")
        if cat:
            categories.add(cat)
    # 还检查_type: lunch/dinner也算不同类型
    meal_types = {s.get("_type", "") for s in steps if s.get("_type")}
    unique_types = len(categories) + len(meal_types)
    diversity_score = min(25, unique_types * 5)  # 5种类型=满分

    # ── 3. 覆盖率 (0-20) ──
    route_names = set()
    for s in steps:
        n = s.get("poi", {}).get("name", "")
        route_names.add(n)
        route_names.add(_canonical_name(n))
    covered = 0
    for p in poi_proposals + food_proposals:
        pn = p.get("content", {}).get("name", "")
        if any(pn in rn or rn in pn for rn in route_names):
            covered += 1
    total_proposals = len(poi_proposals) + len(food_proposals)
    coverage_ratio = covered / total_proposals if total_proposals > 0 else 0
    coverage_score = coverage_ratio * 20

    # ── 4. 时间利用率 (0-15) ──
    start_time_str = intent.get("time", {}).get("start", "09:00")
    end_time_str = intent.get("time", {}).get("end", "21:00")
    try:
        first = datetime.strptime(steps[0]["arrival_time"], "%H:%M")
        last = datetime.strptime(steps[-1]["departure_time"], "%H:%M")
        route_min = (last - first).total_seconds() / 60
        available = (
            datetime.strptime(end_time_str, "%H:%M")
            - datetime.strptime(start_time_str, "%H:%M")
        ).total_seconds() / 60
        if available > 0:
            ratio = route_min / available
            # 80-100%利用率最优, <50%或>110%扣分
            if 0.8 <= ratio <= 1.0:
                time_score = 15
            elif 0.5 <= ratio < 0.8:
                time_score = ratio * 15
            elif ratio > 1.0:
                time_score = max(0, 15 - (ratio - 1.0) * 30)
            else:
                time_score = ratio * 10
        else:
            time_score = 7
    except (ValueError, KeyError):
        time_score = 7

    # ── 5. 步数合理性 (0-15) ──
    # 过少(< 3)或过多(> 8)扣分
    n_steps = len(steps)
    if 4 <= n_steps <= 7:
        steps_score = 15
    elif 3 <= n_steps <= 8:
        steps_score = 10
    else:
        steps_score = 5

    total = geo_score + diversity_score + coverage_score + time_score + steps_score
    return total


# ═══════════════════════════════════════════════════════════
# Architecture A1: Best-of-N 多候选投票
# ═══════════════════════════════════════════════════════════
#
# 动机：LLM输出方差大（同一prompt跑2次，overall可能差1-2分）。
#       单次组装的结果是随机的"好"或"坏"。
#       跑3次取最优 = 用计算量换稳定性。
#
# 方法：
#   1. 并行调用 _llm_assemble_route 3次，分别用 temperature=0.1/0.4/0.7
#   2. 用 _score_route_heuristic 对每条路线打分
#   3. 返回分数最高的路线
#
# 预期：
#   - 减少"倒霉"跑次的概率（3次都差的可能性远低于1次差）
#   - overall方差从 ±1.0 降到 ±0.3
#   - LLM调用从7-12次增加到9-14次（多2次assembler）
#
# 风险：
#   - 3次并行 = 3倍assembler token消耗
#   - 启发式评分可能与LLM评分不一致
# ═══════════════════════════════════════════════════════════

_BEST_OF_N = 3


async def _best_of_n_assemble(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
) -> dict | None:
    """并行生成N条候选路线，启发式评分选最优。"""
    temps = [0.1, 0.4, 0.7]

    tasks = [
        _llm_assemble_route(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, user_input, scene_type, expert_weights,
            temperature=t,
        )
        for t in temps[:_BEST_OF_N]
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    scored: list[tuple[float, dict]] = []
    for route in results:
        if route and isinstance(route, dict) and route.get("route"):
            score = _score_route_heuristic(route, poi_proposals, food_proposals, intent)
            scored.append((score, route))

    if not scored:
        # 全失败，返回第一个非异常结果
        for route in results:
            if isinstance(route, dict):
                return route
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


# ═══════════════════════════════════════════════════════════
# Architecture A2: 地理预聚类 + TSP排序
# ═══════════════════════════════════════════════════════════
#
# 动机：美食型路线geo_continuity=5（折返）。
#       LLM在地理推理上不如算法——它能判断"近不近"，但不能精确计算距离。
#       把地理排序交给算法，LLM只负责"选哪些"。
#
# 方法：
#   1. 将所有候选POI按坐标聚类（简单k-means，k=2-3）
#   2. 选择POI数量最多且平均质量最高的簇
#   3. 在该簇内用最近邻TSP确定访问顺序
#   4. 将排序后的POI列表发给LLM，让LLM只做时间分配和餐饮插入
#
# 预期：
#   - geo_continuity 从 5-6 提升到 8-9（算法保证）
#   - 可能牺牲一些POI质量（远距离的好POI被排除）
#
# 风险：
#   - 过度聚类可能排除用户指定的目的地
#   - 对目的地型场景（用户指定了"长隆"）不适用
# ═══════════════════════════════════════════════════════════

async def _geo_cluster_assemble(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
) -> dict | None:
    """地理预聚类：先按区域分簇，选最优簇，再用TSP排序。"""
    # 1. 收集所有候选POI的坐标
    all_items = []  # (name, lat, lng, content, is_food, proposal)
    for p in poi_proposals:
        c = p.get("content", {})
        lat, lng = c.get("lat", 0), c.get("lng", 0)
        if lat and lng:
            all_items.append((c.get("name", ""), lat, lng, c, False, p))
    for p in food_proposals:
        c = p.get("content", {})
        lat, lng = c.get("lat", 0), c.get("lng", 0)
        if lat and lng:
            all_items.append((c.get("name", ""), lat, lng, c, True, p))

    if len(all_items) < 2:
        # 太少无法聚类，回退到普通LLM
        return await _llm_assemble_route(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, user_input, scene_type, expert_weights,
        )

    # 2. 简单距离聚类（不引入sklearn）
    #    策略：选第一个POI为种子，把距离<5km的归为同一簇
    clusters: list[list[int]] = []
    assigned = set()
    items = all_items

    for i, (name, lat, lng, *_) in enumerate(items):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j, (name2, lat2, lng2, *_) in enumerate(items):
            if j in assigned:
                continue
            d = _haversine_km(lat, lng, lat2, lng2)
            if d < 8:  # 8km半径内为同一区域
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)

    # 3. 选择最优簇：POI数 × 平均rating
    best_cluster = None
    best_score = -1
    for cluster in clusters:
        n_items = len(cluster)
        avg_rating = 0
        n_rated = 0
        for idx in cluster:
            content = items[idx][3]
            r = content.get("rating", 0)
            if r:
                avg_rating += r
                n_rated += 1
        avg_rating = avg_rating / n_rated if n_rated > 0 else 3.5
        # 必须：至少有1个景点 + 1个餐厅（如果有的话）
        has_poi = any(not items[idx][4] for idx in cluster)
        has_food = any(items[idx][4] for idx in cluster)
        score = n_items * avg_rating
        if has_poi:
            score *= 1.5
        if has_food or not food_proposals:
            score *= 1.3
        if score > best_score:
            best_score = score
            best_cluster = cluster

    if not best_cluster or len(best_cluster) < 2:
        return await _llm_assemble_route(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, user_input, scene_type, expert_weights,
        )

    # 4. 在簇内用最近邻TSP排序
    cluster_items = [items[idx] for idx in best_cluster]
    ordered = [cluster_items[0]]
    remaining = list(cluster_items[1:])

    while remaining:
        cur = ordered[-1]
        _, cur_lat, cur_lng, *_ = cur
        best_next = None
        best_dist = float("inf")
        for r in remaining:
            _, r_lat, r_lng, *_ = r
            d = _haversine_km(cur_lat, cur_lng, r_lat, r_lng)
            if d < best_dist:
                best_dist = d
                best_next = r
        if best_next:
            ordered.append(best_next)
            remaining.remove(best_next)
        else:
            break

    # 5. 用排序后的POI构建ordered_stops，传给LLM做时间分配
    #    这次LLM的任务更简单：只需分配时间，不需要排顺序
    sorted_poi_list = []
    sorted_food_list = []
    for name, lat, lng, content, is_food, proposal in ordered:
        entry = {
            "name": name,
            "category": content.get("category", ""),
            "lat": round(lat, 3),
            "lng": round(lng, 3),
            "price": content.get("avg_price", 0),
            "rating": content.get("rating", 0),
            "tags": content.get("tags", [])[:3],
        }
        if is_food:
            sorted_food_list.append(entry)
        else:
            sorted_poi_list.append(entry)

    # 构建建议顺序
    suggested_order = [item[0] for item in ordered]

    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")
    start_time = intent.get("time", {}).get("start", "09:00")
    end_time = intent.get("time", {}).get("end", "21:00")
    budget = intent.get("budget", {}).get("per_person", 0)

    system = f"""你是旅行路线编排专家。地理排序已由算法完成，你只需分配时间。

你的任务：
1. 按建议顺序为每个POI分配到达/离开时间
2. 标记餐厅为lunch(11:30-14:00)或dinner(17:30-20:00)
3. 确保总行程在{start_time}-{end_time}内
4. 不要改变POI顺序（已经是最短路径）

时间节奏：
- 上午({start_time}-12:00)：主力景点（停留60-90min）
- 午餐(11:30-13:00)：停留50min
- 下午(13:00-17:00)：次级景点（停留45-75min）
- 晚餐(17:30-19:00)：停留50min
- 傍晚/晚上：休闲收尾

群体: {group_type} 节奏: {pace}
预算: {'¥' + str(budget) if budget else '不限'}

输出JSON格式：
{{"ordered_stops":[{{"name":"景点/餐厅名","type":"poi/lunch/dinner/hotel","reason":"为什么排这里"}}],"route_design":"路线设计思路（2句话）"}}
只输出JSON。"""

    user = f"""用户需求: {user_input}
场景类型: {scene_type}

建议顺序（已按最短路径排序，不要改变）:
{json.dumps(suggested_order, ensure_ascii=False)}

景点:
{json.dumps(sorted_poi_list, ensure_ascii=False)}

餐厅:
{json.dumps(sorted_food_list, ensure_ascii=False)}

请按建议顺序分配时间。"""

    result = await _llm_decide(system, user)
    if not result or "ordered_stops" not in result:
        # 回退：直接用ordered构建route
        return _build_route_from_ordered_items(ordered, intent)

    return _build_route_from_llm_order(result["ordered_stops"], poi_proposals, food_proposals,
                                        hotel_proposals, intent)


def _build_route_from_ordered_items(
    ordered: list[tuple],
    intent: dict,
) -> dict:
    """从地理排序后的items直接构建route（LLM失败时的fallback）。"""
    start_time_str = intent.get("time", {}).get("start", "09:00")
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    steps = []
    prev_lat, prev_lng = 0.0, 0.0
    for name, lat, lng, content, is_food, proposal in ordered:
        stay_min = 50 if is_food else int(content.get("avg_stay_min", 90))
        travel_min = 15
        if prev_lat and lat:
            dist = _haversine_km(prev_lat, prev_lng, lat, lng)
            travel_min = max(5, min(60, int(dist * 8)))

        meal_type = ""
        if is_food:
            meal_type = "dinner" if t >= datetime.strptime("15:00", "%H:%M") else "lunch"

        steps.append({
            "poi": content,
            "arrival_time": t.strftime("%H:%M"),
            "departure_time": (t + timedelta(minutes=stay_min)).strftime("%H:%M"),
            "travel_from_prev": {"distance_m": int(travel_min * 120), "time_min": travel_min},
            "_type": meal_type,
        })
        t = t + timedelta(minutes=stay_min + travel_min)
        prev_lat, prev_lng = lat, lng

    steps = _dedup_route(steps)
    steps = _enforce_time_windows(steps)

    return {
        "route": steps,
        "total_cost": {
            "time_min": 0,
            "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
        },
        "emotion_curve": [],
    }


# ═══════════════════════════════════════════════════════════
# Architecture A3: 维度导向自精炼
# ═══════════════════════════════════════════════════════════
#
# 动机：当前review/rework检查的是"提案质量"，不是"组装后的路线质量"。
#       路线可能在组装阶段引入新问题（如地理折返、时间冲突），
#       但这些只有在组装完成后才能发现。
#
# 方法：
#   1. 先正常组装路线（调用_llm_assemble_route）
#   2. 用启发式评分找出最弱维度
#   3. 将弱项反馈给LLM，让它针对性改进
#   4. 用改进后的路线替换原路线（只在分数更高时）
#
# 预期：
#   - 精准修复特定维度的弱点（如geo折返、类型单一）
#   - 只多1次LLM调用
#
# 风险：
#   - LLM可能"修了A坏了B"（改了geo但破坏了时间）
#   - 启发式评分可能与evaluator不一致
# ═══════════════════════════════════════════════════════════

async def _self_refine_assemble(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
) -> dict | None:
    """自精炼：先组装，再评价，再改进。"""
    # Pass 1: 正常组装
    route = await _llm_assemble_route(
        poi_proposals, food_proposals, hotel_proposals,
        traffic_proposal, intent, user_input, scene_type, expert_weights,
    )
    if not route or not route.get("route"):
        return route

    # 评价：找出具体问题
    critique = _critique_route(route, poi_proposals, food_proposals, intent)
    if not critique["issues"]:
        return route  # 没有问题，直接返回

    # Pass 2: 带反馈的改进组装
    issue_text = "\n".join(f"- {issue}" for issue in critique["issues"])
    strategy_hint = f"""⚠️ 上一版路线有以下问题，必须修复：
{issue_text}

请特别注意以上问题，重新编排路线。"""

    refined = await _llm_assemble_route(
        poi_proposals, food_proposals, hotel_proposals,
        traffic_proposal, intent, user_input, scene_type, expert_weights,
        temperature=0.1,
        strategy_hint=strategy_hint,
    )

    if not refined or not refined.get("route"):
        return route  # 改进失败，返回原路线

    # 比较分数
    orig_score = _score_route_heuristic(route, poi_proposals, food_proposals, intent)
    refined_score = _score_route_heuristic(refined, poi_proposals, food_proposals, intent)

    return refined if refined_score >= orig_score else route


def _critique_route(
    route: dict,
    poi_proposals: list[dict],
    food_proposals: list[dict],
    intent: dict,
) -> dict:
    """纯规则critique：找出路线的具体问题。"""
    issues: list[str] = []
    steps = route.get("route", [])
    if not steps:
        return {"issues": ["路线为空"]}

    # 检查1: 地理折返（相邻站点距离>10km）
    for i in range(1, len(steps)):
        prev = steps[i - 1].get("poi", {})
        cur = steps[i].get("poi", {})
        lat1, lng1 = prev.get("lat", 0), prev.get("lng", 0)
        lat2, lng2 = cur.get("lat", 0), cur.get("lng", 0)
        if lat1 and lat2:
            d = _haversine_km(lat1, lng1, lat2, lng2)
            if d > 10:
                issues.append(
                    f"地理折返：{prev.get('name', '?')}→{cur.get('name', '?')} "
                    f"距离{d:.1f}km，超过10km"
                )

    # 检查2: 类型过于单一（超过60%是同一类别）
    from collections import Counter
    cats = [s.get("poi", {}).get("category", "") for s in steps]
    cat_counts = Counter(cats)
    if cat_counts:
        top_cat, top_count = cat_counts.most_common(1)[0]
        if top_count / len(cats) > 0.6 and len(cats) > 3:
            issues.append(f"类型单一：{top_cat}占{top_count}/{len(cats)}，超过60%")

    # 检查3: 无餐饮
    has_food = any(
        s.get("_type") in ("lunch", "dinner")
        or s.get("poi", {}).get("category", "") in ("餐饮", "美食", "小吃")
        for s in steps
    )
    if not has_food and food_proposals:
        issues.append("路线无餐饮安排，应插入午餐或晚餐")

    # 检查4: 超出时间窗口
    start_str = intent.get("time", {}).get("start", "09:00")
    end_str = intent.get("time", {}).get("end", "21:00")
    try:
        route_start = datetime.strptime(steps[0].get("arrival_time", "09:00"), "%H:%M")
        route_end = datetime.strptime(steps[-1].get("departure_time", "18:00"), "%H:%M")
        limit_start = datetime.strptime(start_str, "%H:%M")
        limit_end = datetime.strptime(end_str, "%H:%M")
        if route_start < limit_start:
            issues.append(f"路线开始时间{steps[0].get('arrival_time')}早于用户要求{start_str}")
        if route_end > limit_end:
            issues.append(f"路线结束时间{steps[-1].get('departure_time')}晚于用户要求{end_str}")
    except ValueError:
        pass

    # 检查5: 步数过多或过少
    n = len(steps)
    if n > 8:
        issues.append(f"路线步数{n}过多，建议不超过8站")
    elif n < 3:
        issues.append(f"路线步数{n}过少，建议至少3站")

    return {"issues": issues}


# ═══════════════════════════════════════════════════════════
# Architecture A4: 并行策略锦标赛
# ═══════════════════════════════════════════════════════════
#
# 动机：不同场景适合不同"策略偏好"。
#       美食型应该"类型优先"，亲子型应该"地理优先"，特种兵应该"体验优先"。
#       与其让LLM自己平衡，不如并行跑3种策略让它们竞争。
#
# 方法：
#   1. 并行运行3个LLM组装，分别注入不同策略提示：
#      - 地理优先："最小化总路程，绝不折返"
#      - 类型优先："最大化类别多样性，4种以上大类"
#      - 体验优先："只选高评分POI(>=4.5)，宁缺毋滥"
#   2. 用启发式评分选最优
#
# 预期：
#   - 每种策略会在某个维度特别强
#   - 最优策略自动适配场景
#   - 3次LLM调用并行，不增加延迟
#
# 风险：
#   - 3倍token消耗
#   - 启发式评分可能偏向某一种策略
# ═══════════════════════════════════════════════════════════

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
        ("🏆 地理优先策略：最小化总路程，同区域景点连走，绝不折返。距离>10km的不要排在同一条路线。",
         0.1),
        ("🎯 类型优先策略：最大化类别多样性，确保覆盖景点+餐饮+文化/运动/购物等至少4种不同类型。宁可路线长一点也要保证多样性。",
         0.3),
        ("⭐ 体验优先策略：只选高评分POI(rating>=4.0)，宁缺毋滥。质量比数量重要，3个优质POI胜过8个平庸的。",
         0.2),
    ]

    tasks = [
        _llm_assemble_route(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, user_input, scene_type, expert_weights,
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


# ═══════════════════════════════════════════════════════════
# Architecture A6: Google PTS — LLM选点 + 算法排序
# ═══════════════════════════════════════════════════════════
#
# 动机：参考Google PTS论文(ACL 2025)的核心发现：
#   - LLM擅长"理解用户想要什么"，但不擅长"满足硬约束"
#   - 约束求解器擅长"满足时间窗、最短路径、不超预算"
#   - PTS通过率96.6% vs GPT-4o直接规划0.4%
#
# 方法：
#   1. LLM只输出"选哪些POI"（无序列表），不排顺序、不分配时间
#   2. 算法做最近邻TSP排序
#   3. 算法分配时间（基于距离+停留时长）
#   4. 用场景规则选择性地插入餐饮
#
# 优势：
#   - LLM只需做"选择"（分类任务），不需要做"排序"（组合优化）
#   - 算法排序是确定性的，消除LLM排序的方差
#   - 时间分配基于实际距离，不会出现LLM瞎编的时间
#
# 风险：
#   - LLM可能选了地理分散的POI（不知道排序后会怎样）
#   - 最近邻TSP可能不是全局最优
# ═══════════════════════════════════════════════════════════


async def _pts_select_pois(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    intent: dict,
    user_input: str,
    scene_type: str,
) -> dict | None:
    """LLM只选POI子集，不排序。返回选中的名称列表。"""
    poi_names = [p.get("content", {}).get("name", "") for p in poi_proposals if p.get("content", {}).get("name")]
    food_names = [p.get("content", {}).get("name", "") for p in food_proposals if p.get("content", {}).get("name")]

    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")
    start_time = intent.get("time", {}).get("start", "09:00")
    end_time = intent.get("time", {}).get("end", "21:00")
    budget = intent.get("budget", {}).get("per_person", 0)

    # 场景目标站数
    target_stops = {"美食型": "3-5家餐厅+0-1个散步点", "目的地型": "1-2个景点+1个餐厅",
                    "特种兵型": "6-8个景点+2家餐厅", "休闲型": "2-3个景点+1个餐厅",
                    "观光型": "4-6个景点+1-2家餐厅"}.get(scene_type, "4-6个景点+1-2家餐厅")

    system = f"""你是旅行POI选择器。你只需要从候选列表中选择合适的POI，不需要排序或分配时间。

选择规则：
1. 根据用户需求选择最匹配的POI
2. 目标数量：{target_stops}
3. 预算限制：{'¥'+str(budget) if budget else '不限'}
4. 美食型场景：以餐厅为主；其他场景：以景点为主，穿插1-2家餐厅
5. 优先选评分高、与用户意图最匹配的
6. 不要选重复类型的POI（如已有海鲜餐厅就不要再选另一家海鲜餐厅）

输出JSON格式：
{{"selected_pois":["名称1","名称2",...],"selected_foods":["餐厅1","餐厅2",...],"reason":"选择理由（1句话）"}}
只输出JSON。"""

    user = f"""用户需求: {user_input}
场景类型: {scene_type}
群体: {group_type or '未知'}
节奏: {pace}
时间: {start_time}-{end_time}

候选景点（{len(poi_names)}个）: {json.dumps(poi_names, ensure_ascii=False)}
候选餐厅（{len(food_names)}个）: {json.dumps(food_names, ensure_ascii=False)}

请选择最合适的POI子集。"""

    return await _llm_decide(system, user, temperature=0.1)


def _nearest_neighbor_tsp(items: list[tuple]) -> list[tuple]:
    """最近邻TSP排序。items = [(name, lat, lng, content, is_food, proposal), ...]"""
    if len(items) <= 1:
        return items

    ordered = [items[0]]
    remaining = list(items[1:])

    while remaining:
        last_lat, last_lng = ordered[-1][1], ordered[-1][2]
        best_idx = 0
        best_dist = float("inf")
        for i, item in enumerate(remaining):
            if item[1] and last_lat:
                d = _haversine_km(last_lat, last_lng, item[1], item[2])
            else:
                d = 99
            if d < best_dist:
                best_dist = d
                best_idx = i
        ordered.append(remaining.pop(best_idx))

    return ordered


def _insert_food_by_geo(
    ordered_pois: list[tuple],
    food_items: list[tuple],
    intent: dict,
) -> list[tuple]:
    """将餐饮按地理位置插入到最近的POI旁边。"""
    if not food_items:
        return ordered_pois
    if not ordered_pois:
        return food_items

    result = list(ordered_pois)
    start_time_str = intent.get("time", {}).get("start", "09:00")
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    # 估算每个POI的到达时间
    poi_times = []
    prev_lat, prev_lng = 0.0, 0.0
    current_t = t
    for name, lat, lng, content, is_food, proposal in result:
        travel_min = 15
        if prev_lat and lat:
            dist = _haversine_km(prev_lat, prev_lng, lat, lng)
            travel_min = max(5, min(60, int(dist * 8)))
        current_t = current_t + timedelta(minutes=travel_min)
        poi_times.append(current_t)
        stay = int(content.get("avg_stay_min", 90))
        current_t = current_t + timedelta(minutes=stay)
        prev_lat, prev_lng = lat, lng

    # 午餐和晚餐时间窗
    lunch_start = datetime.strptime("11:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")
    dinner_start = datetime.strptime("17:00", "%H:%M")
    dinner_end = datetime.strptime("20:00", "%H:%M")

    # 为每个food找最佳插入位置
    inserted = set()
    for food_name, flat, flng, fcontent, _, fproposal in food_items:
        if not flat:
            continue
        best_pos = -1
        best_dist = float("inf")
        for i, (name, lat, lng, content, is_food, proposal) in enumerate(result):
            if lat:
                d = _haversine_km(flat, flng, lat, lng)
            else:
                d = 99
            if d < best_dist:
                best_dist = d
                best_pos = i

        # 决定插在best_pos之后还是之前
        if best_pos >= 0 and best_dist < 15:
            # 插在最近POI之后
            insert_at = best_pos + 1
        else:
            # 找时间合适的位置
            insert_at = len(result)  # 默认末尾
            for i, pt in enumerate(poi_times):
                if lunch_start <= pt <= lunch_end:
                    insert_at = i + 1
                    break
                if dinner_start <= pt <= dinner_end:
                    insert_at = i + 1
                    break

        if insert_at not in inserted:
            result.insert(insert_at, (food_name, flat, flng, fcontent, True, fproposal))
            inserted.add(insert_at)

    return result


async def _pts_assemble(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
) -> dict | None:
    """Google PTS架构：LLM选点 + 算法排序 + 算法分配时间。"""
    # Step 1: LLM选POI子集
    selection = await _pts_select_pois(poi_proposals, food_proposals, intent, user_input, scene_type)
    if not selection:
        return None

    selected_poi_names = selection.get("selected_pois", [])
    selected_food_names = selection.get("selected_foods", [])

    # Step 2: 匹配到proposal数据
    poi_map = {p.get("content", {}).get("name", ""): p for p in poi_proposals}
    food_map = {p.get("content", {}).get("name", ""): p for p in food_proposals}

    # 模糊匹配（LLM可能输出不完全一致的名称）
    def _fuzzy_match(name: str, mapping: dict) -> dict | None:
        if name in mapping:
            return mapping[name]
        for key in mapping:
            if name in key or key in name:
                return mapping[key]
        return None

    poi_items = []  # (name, lat, lng, content, is_food, proposal)
    for name in selected_poi_names:
        prop = _fuzzy_match(name, poi_map)
        if prop:
            c = prop.get("content", {})
            if c.get("lat"):
                poi_items.append((name, c["lat"], c["lng"], c, False, prop))

    food_items = []
    for name in selected_food_names:
        prop = _fuzzy_match(name, food_map)
        if not prop:
            prop = _fuzzy_match(name, poi_map)  # 可能LLM把餐厅放到poi列表
        if prop:
            c = prop.get("content", {})
            if c.get("lat"):
                food_items.append((name, c["lat"], c["lng"], c, True, prop))

    if not poi_items and not food_items:
        return None

    # Step 3: 最近邻TSP排序POI
    ordered_pois = _nearest_neighbor_tsp(poi_items)

    # Step 4: 按地理位置插入餐饮
    all_ordered = _insert_food_by_geo(ordered_pois, food_items, intent)

    # Step 5: 构建路线
    return _build_route_from_ordered_items(all_ordered, intent)


# ═══════════════════════════════════════════════════════════
# Architecture A5: 迭代约束满足
# ═══════════════════════════════════════════════════════════
#
# 动机：当前方法是"LLM一次性编排所有POI"，容易出现：
#   - 选了太多POI导致超时
#   - 选了太少的POI导致路线单薄
#   - 忘记插入餐饮
#   - 地理排序不合理
#
# 方法：把路线构建分解为一系列约束满足步骤：
#   1. 锚定核心目的地（用户明确提到的/最高权重的expert推荐）
#   2. 插入午餐（选离上午最后一个景点最近的餐厅）
#   3. 插入晚餐（选离下午最后一个景点最近的餐厅）
#   4. 填充上午景点（从核心目的地附近选，按距离排序）
#   5. 填充下午景点（剩余景点，按距离排序）
#   6. 验证约束（时间、预算、步数）
#
# 预期：
#   - 路线结构更可预测
#   - 餐饮不会遗漏
#   - 地理顺序由算法保证
#
# 风险：
#   - 不如LLM灵活（无法做"创意"安排）
#   - 对复杂需求（如"先去长隆再去海鲜街再去情侣路"）处理不好
#   - 不使用LLM的"审美判断"
# ═══════════════════════════════════════════════════════════

async def _constraint_assemble(
    poi_proposals: list[dict],
    food_proposals: list[dict],
    hotel_proposals: list[dict],
    traffic_proposal: dict | None,
    intent: dict,
    user_input: str,
    scene_type: str,
    expert_weights: dict,
) -> dict | None:
    """迭代约束满足：按规则逐步填充路线。"""
    start_time_str = intent.get("time", {}).get("start", "09:00")
    end_time_str = intent.get("time", {}).get("end", "21:00")
    try:
        t_start = datetime.strptime(start_time_str, "%H:%M")
        t_end = datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        t_start = datetime.strptime("09:00", "%H:%M")
        t_end = datetime.strptime("21:00", "%H:%M")

    available_min = (t_end - t_start).total_seconds() / 60
    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")

    if "特种兵" in pace:
        stay_mult = 0.7
    elif "闲逛" in pace or "慢" in pace:
        stay_mult = 1.3
    else:
        stay_mult = 1.0

    # Step 1: 选锚点（最高置信度的POI）
    poi_pool = [
        (p, p.get("confidence", 0.5), p.get("content", {}))
        for p in poi_proposals
        if p.get("content", {}).get("name") and p.get("content", {}).get("lat")
    ]
    food_pool = [
        (p, p.get("confidence", 0.5), p.get("content", {}))
        for p in food_proposals
        if p.get("content", {}).get("name") and p.get("content", {}).get("lat")
    ]

    if not poi_pool and not food_pool:
        return await _llm_assemble_route(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, user_input, scene_type, expert_weights,
        )

    # 美食型：餐厅就是锚点
    if scene_type == "美食型" and food_pool:
        anchors = food_pool
    elif poi_pool:
        # 按confidence排序，取最高的
        poi_pool.sort(key=lambda x: x[1], reverse=True)
        anchors = poi_pool
    else:
        anchors = food_pool

    # Step 2: 从锚点开始，最近邻填充
    anchor_content = anchors[0][2]
    anchor_lat = anchor_content.get("lat", 0)
    anchor_lng = anchor_content.get("lng", 0)

    # 所有候选（排除澳门）
    all_candidates = []
    for p, conf, c in poi_pool:
        if not _is_likely_macau(c.get("name", "")):
            all_candidates.append(("poi", c))
    for p, conf, c in food_pool:
        if not _is_likely_macau(c.get("name", "")):
            all_candidates.append(("food", c))

    # 最近邻排序（从锚点开始）
    ordered: list[tuple[str, dict]] = []
    used_names = set()
    cur_lat, cur_lng = anchor_lat, anchor_lng
    remaining = list(all_candidates)

    while remaining:
        best = None
        best_dist = float("inf")
        for item_type, content in remaining:
            name = content.get("name", "")
            canon = _canonical_name(name)
            if canon in used_names:
                continue
            lat, lng = content.get("lat", 0), content.get("lng", 0)
            if not lat:
                continue
            d = _haversine_km(cur_lat, cur_lng, lat, lng)
            if d < best_dist:
                best_dist = d
                best = (item_type, content)
        if best is None:
            break
        ordered.append(best)
        name = best[1].get("name", "")
        used_names.add(_canonical_name(name))
        remaining = [(t, c) for t, c in remaining if _canonical_name(c.get("name", "")) not in used_names]
        cur_lat = best[1].get("lat", cur_lat)
        cur_lng = best[1].get("lng", cur_lng)

    # Step 3: 构建route，自动插入餐食标记
    t = t_start
    steps = []
    prev_lat, prev_lng = 0.0, 0.0
    total_budget = 0
    budget_limit = intent.get("budget", {}).get("per_person", 0)

    for item_type, content in ordered:
        lat = content.get("lat", 0)
        lng = content.get("lng", 0)
        stay_min = 50 if item_type == "food" else int(content.get("avg_stay_min", 90) * stay_mult)
        travel_min = 15
        if prev_lat and lat:
            dist = _haversine_km(prev_lat, prev_lng, lat, lng)
            travel_min = max(5, min(60, int(dist * 8)))

        arrival = t + timedelta(minutes=travel_min)
        if arrival >= t_end:
            break  # 超时，停止

        departure = arrival + timedelta(minutes=stay_min)
        price = content.get("avg_price", 0)
        if budget_limit and total_budget + price > budget_limit * 1.2:
            continue  # 超预算，跳过

        meal_type = ""
        if item_type == "food":
            meal_type = "dinner" if arrival >= datetime.strptime("15:00", "%H:%M") else "lunch"

        steps.append({
            "poi": content,
            "arrival_time": arrival.strftime("%H:%M"),
            "departure_time": departure.strftime("%H:%M"),
            "travel_from_prev": {"distance_m": int(travel_min * 120), "time_min": travel_min},
            "_type": meal_type,
        })
        t = departure
        prev_lat, prev_lng = lat or prev_lat, lng or prev_lng
        total_budget += price

    # 确保有餐饮
    has_food = any(s.get("_type") in ("lunch", "dinner") for s in steps)
    if not has_food and food_pool:
        # 插入最近的餐厅到合适位置
        best_food = None
        best_score = -1
        for _, _, c in food_pool:
            score = c.get("rating", 0)
            if best_food is None or score > best_score:
                best_score = score
                best_food = c
        if best_food:
            insert_idx = min(2, len(steps))
            if insert_idx < len(steps):
                prev = steps[insert_idx - 1]
                try:
                    food_time = datetime.strptime(prev["departure_time"], "%H:%M") + timedelta(minutes=15)
                except ValueError:
                    food_time = datetime.strptime("12:00", "%H:%M")
            else:
                food_time = t + timedelta(minutes=15)

            meal_type = "dinner" if food_time >= datetime.strptime("15:00", "%H:%M") else "lunch"
            steps.insert(insert_idx, {
                "poi": best_food,
                "arrival_time": food_time.strftime("%H:%M"),
                "departure_time": (food_time + timedelta(minutes=50)).strftime("%H:%M"),
                "travel_from_prev": {"distance_m": 1500, "time_min": 15},
                "_type": meal_type,
            })

    if not steps:
        return await _llm_assemble_route(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, user_input, scene_type, expert_weights,
        )

    steps = _dedup_route(steps)
    steps = _enforce_time_windows(steps)

    return {
        "route": steps,
        "total_cost": {
            "time_min": 0,
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
    meta = AGENT_META.get("synthesizer", {})
    await sse_emit(state, "agent_start", {"agent": "synthesizer", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "synthesizer", "text": "收集提案，地理聚类，时间窗校验..."})

    proposals = list(state.get("reworked_proposals") or state.get("proposals", []))
    intent = dict(state.get("user_intent", {}))
    scene_type = state.get("scene_type", "观光型")
    expert_weights = state.get("expert_weights", {})
    errors = []

    # 按agent类型分类（兼容新旧agent名 + budget_hacker/destination/local_expert归入poi）
    _POI_AGENTS = {"poi", "poi_expert", "budget_hacker", "destination", "local_expert"}
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

    # 美食场景：poi_proposals只保留最多2个（散步消食点），不要塞满景点
    if scene_type == "美食型" and len(poi_proposals) > 2:
        # 优先保留评分高的、距离餐厅近的
        poi_proposals = sorted(poi_proposals, key=lambda p: p.get("content", {}).get("rating", 0), reverse=True)[:2]

    if not poi_proposals and not food_proposals:
        errors.append("无有效POI提案")
        return {"route": None, "narrative": None, "errors": errors}

    # LLM编排 —— 根据SYNTHESIZER_MODE选择架构
    if SYNTHESIZER_MODE == "best_of_n":
        route = await _best_of_n_assemble(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, state.get("user_input", ""),
            scene_type, expert_weights,
        )
    elif SYNTHESIZER_MODE == "geo_cluster":
        route = await _geo_cluster_assemble(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, state.get("user_input", ""),
            scene_type, expert_weights,
        )
    elif SYNTHESIZER_MODE == "self_refine":
        route = await _self_refine_assemble(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, state.get("user_input", ""),
            scene_type, expert_weights,
        )
    elif SYNTHESIZER_MODE == "tournament":
        route = await _tournament_assemble(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, state.get("user_input", ""),
            scene_type, expert_weights,
        )
    elif SYNTHESIZER_MODE == "constraint":
        route = await _constraint_assemble(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, state.get("user_input", ""),
            scene_type, expert_weights,
        )
    elif SYNTHESIZER_MODE == "pts":
        route = await _pts_assemble(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, state.get("user_input", ""),
            scene_type, expert_weights,
        )
    else:
        route = await _llm_assemble_route(
            poi_proposals, food_proposals, hotel_proposals,
            traffic_proposal, intent, state.get("user_input", ""),
            scene_type, expert_weights,
        )

    if not route or not route.get("route"):
        route = _fallback_assemble(proposals, intent)

    # 站数上限（在ensure之前，避免截断ensure追加的站点）
    if route and route.get("route"):
        route = _cap_route_stops(route, scene_type, intent)

    # 补回遗漏（在cap之后，追加的不受截断影响）
    if route and route.get("route"):
        route = _ensure_food_in_route(route, food_proposals, intent)
        route = _ensure_poi_in_route(route, poi_proposals, intent)

    if route and route.get("route") and food_proposals:
        route = _ensure_min_food_in_route(route, food_proposals, intent)

    # 文案
    narrative = None
    if route:
        try:
            from backend.services.narrator import generate_narrative
            city = intent.get("city", "珠海")
            narrative = await generate_narrative(route, intent, city=city, enable_llm_polish=False)
        except Exception as e:
            errors.append(f"文案生成失败: {e}")
            narrative = _build_fallback_narrative(route)

    steps_count = len(route.get("route", [])) if route else 0
    await sse_emit(state, "agent_result", {"agent": "synthesizer", "summary": f"组装完成: {steps_count}站路线"})

    return {"route": route, "narrative": narrative, "errors": errors}
