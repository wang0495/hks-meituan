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
from backend.agents_v3.state import TravelState, AGENT_META, sse_emit


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


# ── 按类别的默认停留时间 ──
_CATEGORY_STAY: dict[str, int] = {
    "景点": 90, "文化": 90, "运动": 80, "自然风光": 75,
    "餐饮": 50, "美食": 50, "小吃": 35, "夜市小吃": 50,
    "咖啡馆": 35, "海景咖啡馆": 40, "甜品": 30,
    "酒吧": 75, "娱乐": 90, "购物": 60,
    "温泉SPA": 120, "水上运动场所": 90,
    "住宿": 0, "酒店": 0, "民宿": 0,
}


def _category_stay_min(category: str) -> int:
    """Return default stay minutes for a POI category."""
    return _CATEGORY_STAY.get(category, 60)


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


# ── DPP多样性重排 (参考 github.com/laming-chen/fast-map-dpp) ──

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
        # 自然/海滨类（组内相似度高）
        "自然风光": 0.0, "海滨景点": 0.05, "水上运动场所": 0.1,
        # 文化/地标类
        "文化景点": 0.2, "文化": 0.2, "地标景点": 0.25, "夜景地标": 0.3,
        # 运动/亲子类
        "运动": 0.4, "亲子游乐": 0.45,
        # 餐饮类（子类也要区分）
        "正餐": 0.55, "海鲜餐饮": 0.6, "地方小吃": 0.65, "夜市小吃": 0.7,
        "甜品饮品": 0.75, "茶餐厅": 0.8,
        # 休闲/购物类
        "购物": 0.85, "海景咖啡馆": 0.9, "温泉SPA": 0.92,
        "休闲娱乐": 0.95, "密室逃脱": 0.95, "攀岩": 0.95,
    }
    # _display_category优先
    return _GROUPS.get(cat, 0.5)


def _dpp_rerank_route(route: dict, scene_type: str) -> dict:
    """用DPP对路线步骤做多样性重排。

    核心思路：构建核矩阵L，对角线=POI质量分，非对角线=类型相似度。
    DPP贪心选择最大化det(L_S)的子集 → 天然平衡质量和多样性。
    """
    steps = route.get("route", [])
    if len(steps) <= 3:
        return route  # 太少不重排

    n = len(steps)

    # 构建核矩阵
    kernel = np.zeros((n, n))
    for i in range(n):
        poi_i = steps[i].get("poi", {})
        # 对角线：质量分（rating或固定值）
        rating = poi_i.get("rating", 4.0)
        price = poi_i.get("avg_price", 0)
        # 价格>0说明是消费场所，权重稍低
        quality = rating / 5.0
        if price == 0:
            quality = min(quality * 1.1, 1.0)  # 免费景点加分
        kernel[i, i] = quality

    for i in range(n):
        cat_i = steps[i].get("poi", {}).get("_display_category") or steps[i].get("poi", {}).get("category", "")
        val_i = _build_category_vector(cat_i)
        for j in range(i + 1, n):
            cat_j = steps[j].get("poi", {}).get("_display_category") or steps[j].get("poi", {}).get("category", "")
            val_j = _build_category_vector(cat_j)
            # 同类型→相似度高→DPP倾向于只选一个
            # 不同类型→相似度低→DPP倾向于都选
            similarity = max(0, 1.0 - abs(val_i - val_j) * 2)  # 0~1
            # 同category额外惩罚
            if cat_i == cat_j:
                similarity = 0.9
            quality_avg = (kernel[i, i] + kernel[j, j]) / 2
            kernel[i, j] = similarity * quality_avg
            kernel[j, i] = kernel[i, j]

    # DPP选择（保留全部步骤，只是重排序）
    selected = _dpp_select(kernel, n)

    # 按DPP选择顺序重排
    reordered = [steps[i] for i in selected]

    # 重新计算到达/离开时间
    start_time_str = reordered[0].get("arrival_time", "09:00") if reordered else "09:00"
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    prev_lat, prev_lng = 0.0, 0.0
    for step in reordered:
        poi = step.get("poi", {})
        lat, lng = poi.get("lat", 0), poi.get("lng", 0)
        # 旅行时间
        if prev_lat and lat:
            dist = _haversine_km(prev_lat, prev_lng, lat, lng)
            travel = max(5, min(60, int(dist * 8)))
        else:
            travel = 15

        t = t + timedelta(minutes=travel)
        stay = int(poi.get("avg_stay_min", 90))
        # 餐饮停留50分钟
        if step.get("_type") in ("lunch", "dinner"):
            stay = 50
        step["arrival_time"] = t.strftime("%H:%M")
        step["departure_time"] = (t + timedelta(minutes=stay)).strftime("%H:%M")
        step["travel_from_prev"] = {"distance_m": travel * 120, "time_min": travel}
        t = t + timedelta(minutes=stay)
        prev_lat, prev_lng = lat, lng

    reordered = _dedup_route(reordered)
    reordered = _enforce_time_windows(reordered)

    route["route"] = reordered
    return route


# ── 补回遗漏 ──
def _must_keep_core_pois(
    route: dict,
    prev_round_context: dict,
    all_proposals: list[dict],
) -> dict:
    """反馈重入时，确保上一轮的核心POI保留在路线中。

    prev_round_context.last_stops 中的 POI 如果在当前 proposals 里能找到，
    但不在锦标赛产出的 route 中，则强制插入到合适位置。
    """
    if not prev_round_context or not route or not route.get("route"):
        return route

    last_stops = prev_round_context.get("last_stops", [])
    if not last_stops:
        return route

    steps = route["route"]
    route_names = set()
    for s in steps:
        n = s.get("poi", {}).get("name", "")
        route_names.add(n)
        c = _canonical_name(n)
        if c != n:
            route_names.add(c)

    # 构建 proposal name → proposal 映射
    proposal_map = {}
    for p in all_proposals:
        name = p.get("content", {}).get("name", "")
        if name:
            proposal_map[name] = p

    # 找出必须保留但被遗漏的核心 POI
    must_keep = []
    for stop_name in last_stops:
        # 检查是否已在路线中
        if any(stop_name in rn or rn in stop_name for rn in route_names):
            continue
        # 检查是否在当前 proposals 中
        matched_proposal = proposal_map.get(stop_name)
        if not matched_proposal:
            for name, p in proposal_map.items():
                if stop_name in name or name in stop_name:
                    matched_proposal = p
                    break
        if matched_proposal:
            must_keep.append(matched_proposal)

    if not must_keep:
        return route

    # 将遗漏的核心 POI 插入到路线中（按地理就近原则插入）
    for mk in must_keep:
        content = mk.get("content", {})
        mk_lat = content.get("lat", 0)
        mk_lng = content.get("lng", 0)
        best_idx = len(steps)  # 默认追加到末尾
        best_dist = float("inf")

        for i, s in enumerate(steps):
            poi = s.get("poi", {})
            lat = poi.get("lat", 0)
            lng = poi.get("lng", 0)
            if mk_lat and mk_lng and lat and lng:
                d = _haversine_km(mk_lat, mk_lng, lat, lng)
                if d < best_dist:
                    best_dist = d
                    best_idx = i + 1

        prev_dep = "10:00"
        if steps and best_idx > 0:
            prev_dep = steps[best_idx - 1].get("departure_time", "10:00")
        try:
            arr_t = datetime.strptime(prev_dep, "%H:%M") + timedelta(minutes=15)
        except ValueError:
            arr_t = datetime.strptime("10:15", "%H:%M")
        dep_t = arr_t + timedelta(minutes=60)

        new_step = {
            "poi": content,
            "arrival_time": arr_t.strftime("%H:%M"),
            "departure_time": dep_t.strftime("%H:%M"),
            "travel_from_prev": {"distance_m": int(best_dist * 1000) if best_dist < float("inf") else 2000, "time_min": 15},
            "_type": "must_keep",
        }
        steps.insert(best_idx, new_step)

    route["route"] = _dedup_route(steps)
    return route


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


def _ensure_food_scene_food_count(
    route: dict, food_proposals: list[dict], scene_type: str,
) -> dict:
    """美食型专用：确保路线至少含2个不同子类型的餐饮。"""
    if not route or not route.get("route") or not food_proposals:
        return route
    if scene_type != "美食型":
        return route

    _FOOD_SUBCATS_LOCAL = {
        "海鲜": ["海鲜", "蚝", "鱼排", "渔港"],
        "正餐": ["餐厅", "烧", "煲", "火锅", "烧烤"],
        "小吃": ["粉", "面", "粥", "小吃", "排档"],
        "茶餐厅/甜品": ["茶餐厅", "甜品", "奶茶", "冰", "柠檬", "饮品"],
        "综合美食街": ["夜市", "美食街", "海鲜街", "老街"],
    }

    def _is_food_stop(s: dict) -> bool:
        cat = s.get("poi", {}).get("category", "")
        if cat in ("餐饮", "美食", "小吃", "海鲜", "夜市", "夜市小吃"):
            return True
        name = s.get("poi", {}).get("name", "")
        return any(kw in name for kw in [
            "餐厅", "海鲜", "粉", "面", "粥", "甜品", "茶餐厅",
            "烧烤", "火锅", "夜市", "小吃", "排档", "肠粉",
        ])

    def _get_subcat(name: str) -> str:
        for sub, kws in _FOOD_SUBCATS_LOCAL.items():
            if any(kw in name for kw in kws):
                return sub
        return "其他"

    steps = route["route"]
    food_steps = [s for s in steps if _is_food_stop(s)]
    food_subcats = set(_get_subcat(s.get("poi", {}).get("name", "")) for s in food_steps)

    # 美食型需要 >=2 个餐饮 + >=2 种子类型
    if len(food_steps) >= 2 and len(food_subcats) >= 2:
        return route

    # 找出路线中已有的名字（避免重复插入）
    route_names = set()
    for s in steps:
        n = s.get("poi", {}).get("name", "")
        route_names.add(n)
        cn = _canonical_name(n)
        if cn != n:
            route_names.add(cn)

    # 从 food_proposals 中找未占用的、不同子类型的候选
    needed_subcats = [s for s in _FOOD_SUBCATS_LOCAL if s not in food_subcats]
    extra = []
    for fp in food_proposals:
        if len(extra) >= 3:
            break
        name = fp.get("content", {}).get("name", "")
        if name in route_names:
            continue
        sub = _get_subcat(name)
        if sub in food_subcats and len(extra) >= max(0, 2 - len(food_steps)):
            continue  # 已有该子类，只在数量不够时补充
        extra.append(fp)
        food_subcats.add(sub)

    if not extra:
        return route

    # 插入到路线中合适的位置
    end_time_str = "21:00"
    try:
        end_dt = datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")

    # 找最后一个站点的离开时间
    try:
        t = datetime.strptime(steps[-1].get("departure_time", "18:00"), "%H:%M")
    except ValueError:
        t = datetime.strptime("18:00", "%H:%M")

    for fp in extra:
        content = fp.get("content", {})
        arrival = t + timedelta(minutes=15)
        departure = arrival + timedelta(minutes=50)
        if departure > end_dt:
            break
        meal_type = "dinner" if arrival >= datetime.strptime("15:00", "%H:%M") else "lunch"
        steps.append({
            "poi": content,
            "arrival_time": arrival.strftime("%H:%M"),
            "departure_time": departure.strftime("%H:%M"),
            "travel_from_prev": {"distance_m": 1800, "time_min": 15},
            "_type": meal_type,
        })
        t = departure

    route["route"] = steps
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

    # ── 短途/位置感知 ──
    try:
        _start_dt = datetime.strptime(start_time, "%H:%M")
        _end_dt = datetime.strptime(end_time, "%H:%M")
        _avail_min = (_end_dt - _start_dt).total_seconds() / 60
    except ValueError:
        _avail_min = 720  # 默认12小时

    _short_trip = _avail_min < 240  # <4小时 = 短途
    _max_stops_hint = ""
    if _short_trip:
        _max_stops_for_short = min(3, max(2, int(_avail_min / 90)))
        _max_stops_hint = f"\n9. 【短途硬约束】可用时间仅{int(_avail_min/60)}小时，最多选{_max_stops_for_short}站，不要凑数！"

    # 位置感知：如果用户指定了区域，按坐标过滤/优先
    _location = intent.get("location") or ""
    _location_coords: tuple[float, float] | None = None
    _LOCATION_COORDS = {
        "横琴": (22.12, 113.53), "金湾": (22.08, 113.38), "金湾机场": (22.05, 113.38),
        "斗门": (22.22, 113.29), "唐家湾": (22.36, 113.58), "拱北": (22.23, 113.55),
        "香洲": (22.27, 113.57), "吉大": (22.25, 113.57), "湾仔": (22.20, 113.53),
        "华发": (22.24, 113.53), "井岸": (22.20, 113.30), "三灶": (22.08, 113.37),
    }
    for loc_name, loc_coords in _LOCATION_COORDS.items():
        if loc_name in _location:
            _location_coords = loc_coords
            break
    _location_hint = ""
    if _location_coords:
        _location_hint = f"\n10. 【区域约束】用户在{_location}附近（坐标{_location_coords[0]:.2f},{_location_coords[1]:.2f}），只选该区域5km内的POI，远距离的不要选"

    # 场景规则
    if scene_type == "美食型":
        diversity_rule = f"""7. 【美食场景规则·最重要·硬约束】
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
        # 目的地中心坐标（从 expert_router 传入）
        dest_center = state.get("destination_center")
        dest_name = state.get("destination_name", "")
        geo_rule = ""
        if dest_center:
            geo_rule = f"\n   - 所有站点必须在目的地坐标({dest_center[0]:.2f},{dest_center[1]:.2f})10km范围内，超出范围的POI直接排除"
        diversity_rule = f"""7. 【目的地场景规则】
   - 用户指定了{dest_name or '大景区'}，会在该景区待大半天（通常3-6小时）
   - 路线以该景区为中心，周边安排1-2个补充景点+1家餐饮即可
   - 不需要大范围跨区域{geo_rule}
   - 【时间节奏】核心景区上午到达，先游览景区主体
   - 餐饮安排在景区游览之后（午餐12:00或晚餐18:00），不要在景区前安排远距离用餐
   - 如果只有半天（如下午场），路线精简为核心景点+附近一餐，不硬凑"""
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

    route = _build_route_from_llm_order(result["ordered_stops"], poi_proposals, food_proposals,
                                         hotel_proposals, intent)
    return route


# ═══════════════════════════════════════════════════════════
# LLM 时间修正：替代纯算法的机械累加
# ═══════════════════════════════════════════════════════════

_TIME_FIX_SYSTEM = """你是行程时间分配专家。你需要为一日游路线的每个站点分配合理的到达/离开时间。

规则：
1. 午餐对齐 11:30-13:00，晚餐对齐 17:30-19:00
2. 停留时长按类型区分：
   - 大型主题公园/游乐园: 4-6小时
   - 博物馆/展览馆: 1.5-2.5小时
   - 公园/自然风光: 1-2小时
   - 拍照打卡点/地标: 20-40分钟
   - 普通景点: 1-1.5小时
   - 正餐餐厅: 50-70分钟
   - 小吃/快餐/粉面: 25-40分钟
   - 茶餐厅/早茶: 45-70分钟
   - 咖啡馆/甜品店: 30-45分钟
   - 夜市/美食街: 45-70分钟
   - 酒吧: 60-90分钟
3. 站间交通：市区内5-15分钟，跨区15-30分钟
4. 总行程不超过起止时间范围
5. 节奏{pace_desc}
6. 站点顺序已确定，不要改变顺序，只分配时间
7. 餐前饭后节奏：先游览景点，再安排用餐。不要出现"先吃完饭再去景点"的倒置安排

输出JSON：
{{"stops":[{{"name":"站点名","arrival":"HH:MM","departure":"HH:MM","stay_min":int}}]}}
只输出JSON。"""


async def _llm_fix_times(
    route: dict,
    intent: dict,
    user_input: str,
    scene_type: str,
    pace: str = "平衡型",
) -> dict:
    """用LLM修正路线时间分配。失败则返回原始route（纯算法兜底）。"""
    steps = route.get("route", [])
    if not steps:
        return route

    start_time = intent.get("time", {}).get("start", "09:00")
    end_time = intent.get("time", {}).get("end", "21:00")

    if "特种兵" in pace:
        pace_desc = "紧凑高效，减少停留时间"
    elif "闲逛" in pace or "慢" in pace:
        pace_desc = "悠闲放松，延长停留时间"
    else:
        pace_desc = "适中平衡"

    # 构建站点摘要给LLM
    stops_summary = []
    for s in steps:
        poi = s.get("poi", s)
        stops_summary.append({
            "name": poi.get("name", ""),
            "category": poi.get("category", ""),
            "type": s.get("_type", "poi"),
            "avg_stay_min": poi.get("avg_stay_min", 0),
            "rating": poi.get("rating", 0),
            "tags": poi.get("tags", [])[:3],
            "old_arrival": s.get("arrival_time", ""),
            "old_departure": s.get("departure_time", ""),
        })

    user_prompt = f"""用户需求: {user_input}
场景类型: {scene_type}
节奏: {pace}
时间范围: {start_time} - {end_time}

当前站点顺序（{len(stops_summary)}站）:
{json.dumps(stops_summary, ensure_ascii=False)}

请为每个站点分配合理的到达/离开时间和停留时长。"""

    system_prompt = _TIME_FIX_SYSTEM.format(pace_desc=pace_desc)

    result = await _llm_decide(system_prompt, user_prompt, temperature=0.1)
    if not result or "stops" not in result:
        return route  # LLM失败，返回原始纯算法结果

    llm_stops = result["stops"]
    if not isinstance(llm_stops, list) or len(llm_stops) != len(steps):
        return route  # 站数不匹配，返回原始

    # 用LLM结果覆盖时间
    new_steps = []
    for i, s in enumerate(steps):
        llm = llm_stops[i]
        new_step = dict(s)
        new_step["arrival_time"] = llm.get("arrival", s.get("arrival_time", ""))
        new_step["departure_time"] = llm.get("departure", s.get("departure_time", ""))
        new_step["stay_min"] = llm.get("stay_min", 0)
        new_steps.append(new_step)

    # 重新计算 travel_from_prev
    for i, s in enumerate(new_steps):
        if i == 0:
            s["travel_from_prev"] = {"distance_m": 0, "time_min": 0}
            continue
        try:
            dep_prev = datetime.strptime(new_steps[i - 1]["departure_time"], "%H:%M")
            arr_curr = datetime.strptime(s["arrival_time"], "%H:%M")
            gap = max(0, int((arr_curr - dep_prev).total_seconds() / 60))
        except ValueError:
            gap = s.get("travel_from_prev", {}).get("time_min", 15)
        s["travel_from_prev"] = {"distance_m": gap * 120, "time_min": gap}

    # 重新计算 total_time
    try:
        end_t = datetime.strptime(new_steps[-1].get("departure_time", "18:00"), "%H:%M")
        start_t = datetime.strptime(new_steps[0].get("arrival_time", "09:00"), "%H:%M")
        total_time = int((end_t - start_t).total_seconds() / 60)
    except ValueError:
        total_time = len(new_steps) * 90

    return {
        "route": new_steps,
        "total_cost": {
            "time_min": total_time,
            "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in new_steps),
        },
        "emotion_curve": route.get("emotion_curve", []),
    }


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

    # 额外惩罚：美食子类重复（同一子类餐厅>1个扣分）
    from collections import Counter as _Counter
    _FOOD_SUBCATS_LOCAL = {
        "海鲜": ["海鲜", "蚝", "鱼排", "渔港"],
        "正餐": ["餐厅", "烧", "煲", "火锅", "烧烤"],
        "小吃": ["粉", "面", "粥", "小吃", "排档"],
        "茶餐厅/甜品": ["茶餐厅", "甜品", "奶茶", "冰", "柠檬", "饮品"],
        "综合美食街": ["夜市", "美食街", "海鲜街", "老街"],
    }
    food_subcats = []
    for s in steps:
        name = s.get("poi", {}).get("name", "")
        cat = s.get("poi", {}).get("category", "")
        is_food = cat in {"餐饮", "美食", "小吃", "夜市"} or any(
            kw in name for kw in ["餐厅", "海鲜", "粉", "面", "粥", "甜品", "茶餐厅", "烧烤", "火锅", "夜市"]
        )
        if is_food:
            for sub, kws in _FOOD_SUBCATS_LOCAL.items():
                if any(kw in name for kw in kws):
                    food_subcats.append(sub)
                    break
            else:
                food_subcats.append("其他餐饮")
    if food_subcats:
        subcat_counts = _Counter(food_subcats)
        # 每个重复的子类扣2分
        for sub, cnt in subcat_counts.items():
            if cnt > 1:
                diversity_score -= (cnt - 1) * 2

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
# 锦标赛：并行3策略竞争，启发式评分选最优
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
        if is_food:
            stay_min = 50
        else:
            stay_min = int(c.get("avg_stay_min", 0)) or _category_stay_min(c.get("category", ""))
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
    await sse_emit(state, "agent_thinking", {"agent": "synthesizer", "text": "收集提案，锦标赛并行3策略竞争..."})

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

    # 锦标赛：并行3策略竞争选最优
    route = await _tournament_assemble(
        poi_proposals, food_proposals, hotel_proposals,
        traffic_proposal, intent, state.get("user_input", ""),
        scene_type, expert_weights,
    )

    if not route or not route.get("route"):
        route = _fallback_assemble(proposals, intent)

    # LLM修正时间分配（tournament和fallback都需要）
    pace = intent.get("pace", "平衡型")
    if route and route.get("route"):
        route = await _llm_fix_times(route, intent, state.get("user_input", ""), scene_type, pace)

    # BUG-1 fix: 反馈重入时保留上一轮核心POI
    prev_ctx = state.get("prev_round_context", {})
    if prev_ctx and route and route.get("route"):
        route = _must_keep_core_pois(route, prev_ctx, proposals)

    # 站数上限（在ensure之前，避免截断ensure追加的站点）
    if route and route.get("route"):
        route = _cap_route_stops(route, scene_type, intent)
        # 短途场景额外截断
        try:
            _st = datetime.strptime(intent.get("time", {}).get("start", "09:00"), "%H:%M")
            _et = datetime.strptime(intent.get("time", {}).get("end", "21:00"), "%H:%M")
            _avail = (_et - _st).total_seconds() / 60
        except ValueError:
            _avail = 720
        if _avail < 240:
            _short_max = min(3, max(2, int(_avail / 90)))
            steps = route.get("route", [])
            if len(steps) > _short_max:
                route["route"] = steps[:_short_max]

    # 补回遗漏（在cap之后，追加的不受截断影响）
    if route and route.get("route"):
        route = _ensure_food_in_route(route, food_proposals, intent)
        route = _ensure_poi_in_route(route, poi_proposals, intent)

    if route and route.get("route") and food_proposals:
        route = _ensure_min_food_in_route(route, food_proposals, intent)
        route = _ensure_food_scene_food_count(route, food_proposals, scene_type)

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
