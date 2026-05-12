"""竞标市场节点。

包含:
- bidding_market_node: 竞标市场入口节点
- individual_bid_node: 单个Agent竞标节点（Send()目标）
- bid_aggregation_node: 竞标聚合节点
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.agents_v2.state import (
    FederatedState,
    Bid,
    CompositeBid,
    BiddingRound,
    MarketClearing,
    BidTask,
)


async def bidding_market_node(state: FederatedState) -> FederatedState:
    """竞标市场入口节点。

    职责：
    1. 初始化竞标市场状态
    2. 准备竞标任务列表（供Send()使用）
    3. 如果是多轮竞标，处理前一轮结果
    """
    intent_package = state.get("intent_package")
    if not intent_package:
        state["errors"].append("意图包为空，无法启动竞标")
        return state

    current_round = state.get("current_round", 0)

    # 初始化市场状态
    if current_round == 0:
        state["bidding_rounds"] = []
        state["bids"] = []
        state["composite_bids"] = []
        state["current_round"] = 1
    else:
        # 后续轮次：基于前一轮结果调整
        prev_bids = state.get("bids", [])

        # 第二轮：未中标Agent降价
        if current_round == 1 and prev_bids:
            adjusted_bids = []
            for bid in prev_bids:
                # 降价15%
                new_bid = dict(bid)
                new_bid["bid_id"] = f"bid_r2_{uuid.uuid4().hex[:6]}"
                new_bid["dynamic_price"] = bid.get("dynamic_price", bid.get("base_cost", 0)) * 0.85
                new_bid["created_at_round"] = current_round + 1
                adjusted_bids.append(new_bid)
            state["bids"] = adjusted_bids

        state["current_round"] = current_round + 1

    return state


async def individual_bid_node(state: FederatedState) -> FederatedState:
    """单个Agent竞标节点（Send()的目标）。

    根据_bid_task中的agent_type调用对应的Agent进行投标。
    """
    bid_task = state.get("_bid_task")
    if not bid_task:
        return state

    sub_need = bid_task["sub_need"]
    agent_type = bid_task["agent_type"]
    round_num = bid_task.get("round_number", 1)

    intent_package = state.get("intent_package", {})
    core_intent = intent_package.get("core_intent", {})

    # 根据agent_type调用对应的竞标逻辑
    bids = []

    if agent_type == "poi":
        bids = await _bid_poi(sub_need, core_intent, round_num)
    elif agent_type == "food":
        bids = await _bid_food(sub_need, core_intent, round_num)
    elif agent_type == "activity":
        bids = await _bid_activity(sub_need, core_intent, round_num)
    elif agent_type == "transport":
        bids = await _bid_transport(sub_need, core_intent, round_num)
    elif agent_type == "insurance":
        bids = await _bid_insurance(sub_need, core_intent, round_num)

    # 将bids添加到state
    if bids:
        if "bids" not in state:
            state["bids"] = []
        state["bids"].extend(bids)

    return state


async def _bid_poi(sub_need: dict, core_intent: dict, round_num: int) -> list[Bid]:
    """POI Agent竞标。"""
    from backend.services.data_service import get_data
    from backend.services.filters import filter_candidates

    all_pois = get_data("city_poi_db")
    city = core_intent.get("city", "珠海")
    city_pois = [p for p in all_pois if p.get("city", "").strip() == city]

    # 使用filter_candidates做初步过滤
    filtered = filter_candidates(city_pois, core_intent)

    if not filtered:
        filtered = city_pois[:20]  # 降级：取前20个

    # 按约束评分
    constraints = sub_need.get("constraints", {})
    emotion = constraints.get("emotion", "")
    activity_type = constraints.get("activity_type", "")

    scored = []
    for poi in filtered[:50]:
        score = 0.5

        # 情绪匹配
        emotion_tags = poi.get("emotion_tags", {})
        if emotion and str(emotion).lower() in str(emotion_tags).lower():
            score += 0.3

        # 类别匹配
        category = poi.get("category", "")
        if activity_type == "静态" and category in ["景点", "文化", "博物馆", "餐饮"]:
            score += 0.2
        elif activity_type == "动态" and category in ["娱乐", "运动", "体验"]:
            score += 0.2

        # 评分加成
        rating = poi.get("rating", 0)
        if rating > 4.5:
            score += 0.1

        scored.append((poi, min(score, 1.0)))

    # 排序取前5
    scored.sort(key=lambda x: x[1], reverse=True)
    top5 = scored[:5]

    bids = []
    for i, (poi, score) in enumerate(top5):
        base_cost = poi.get("avg_price", 0)
        bids.append({
            "bid_id": f"bid_poi_{uuid.uuid4().hex[:6]}",
            "agent_type": "poi",
            "agent_id": f"poi_agent_{i}",
            "sub_need_id": sub_need["id"],
            "proposal": {
                "poi": poi,
                "expected_duration": 120,
                "recommended_time": "09:00" if i == 0 else f"{9 + i * 2:02d}:00",
            },
            "confidence": score,
            "base_cost": base_cost,
            "dynamic_price": base_cost,
            "cost_estimate": {"entry_fee": base_cost, "transport": 20},
            "created_at_round": round_num,
        })

    return bids


async def _bid_food(sub_need: dict, core_intent: dict, round_num: int) -> list[Bid]:
    """餐饮Agent竞标。"""
    from backend.services.data_service import get_data

    all_pois = get_data("city_poi_db")
    restaurants = [p for p in all_pois if p.get("category") == "餐饮"]

    if not restaurants:
        return []

    # 按价格排序
    restaurants.sort(key=lambda x: x.get("avg_price", 0))

    bids = []
    for i, rest in enumerate(restaurants[:5]):
        price = rest.get("avg_price", 50)
        bids.append({
            "bid_id": f"bid_food_{uuid.uuid4().hex[:6]}",
            "agent_type": "food",
            "agent_id": f"food_agent_{i}",
            "sub_need_id": sub_need["id"],
            "proposal": {
                "restaurant": rest,
                "meal_type": "午餐" if i < 3 else "晚餐",
                "expected_duration": 60,
            },
            "confidence": 0.7,
            "base_cost": price,
            "dynamic_price": price,
            "cost_estimate": {"meal_cost": price},
            "created_at_round": round_num,
        })

    return bids


async def _bid_activity(sub_need: dict, core_intent: dict, round_num: int) -> list[Bid]:
    """活动Agent竞标。"""
    from backend.services.data_service import get_data

    all_pois = get_data("city_poi_db")
    # 活动类POI
    activities = [p for p in all_pois if p.get("category") in ["娱乐", "体验", "运动"]]

    constraints = sub_need.get("constraints", {})
    emotion = constraints.get("emotion", "")

    bids = []
    for i, act in enumerate(activities[:5]):
        score = 0.6
        if emotion == "兴奋" and act.get("category") == "娱乐":
            score = 0.9
        elif emotion == "宁静" and act.get("category") == "体验":
            score = 0.8

        price = act.get("avg_price", 100)
        bids.append({
            "bid_id": f"bid_act_{uuid.uuid4().hex[:6]}",
            "agent_type": "activity",
            "agent_id": f"activity_agent_{i}",
            "sub_need_id": sub_need["id"],
            "proposal": {
                "activity": act,
                "expected_duration": 90,
            },
            "confidence": score,
            "base_cost": price,
            "dynamic_price": price,
            "cost_estimate": {"activity_fee": price},
            "created_at_round": round_num,
        })

    return bids


async def _bid_transport(sub_need: dict, core_intent: dict, round_num: int) -> list[Bid]:
    """交通Agent竞标。"""
    # 提供多种交通方式
    transport_modes = [
        {"mode": "步行", "time_per_km": 12, "cost": 0},
        {"mode": "公交", "time_per_km": 3, "cost": 2},
        {"mode": "打车", "time_per_km": 2, "cost": 15},
    ]

    bids = []
    for i, tm in enumerate(transport_modes):
        bids.append({
            "bid_id": f"bid_trans_{uuid.uuid4().hex[:6]}",
            "agent_type": "transport",
            "agent_id": f"transport_agent_{i}",
            "sub_need_id": sub_need["id"],
            "proposal": {
                "transport_mode": tm["mode"],
                "time_per_km": tm["time_per_km"],
            },
            "confidence": 0.8 if tm["mode"] == "打车" else 0.7,
            "base_cost": tm["cost"],
            "dynamic_price": tm["cost"],
            "cost_estimate": {"transport": tm["cost"]},
            "created_at_round": round_num,
        })

    return bids


async def _bid_insurance(sub_need: dict, core_intent: dict, round_num: int) -> list[Bid]:
    """保险Agent竞标。"""
    # 提供天气保险和时间保险
    insurances = [
        {
            "type": "天气保险",
            "description": "如遇恶劣天气，自动替换为室内方案",
            "premium_rate": 0.05,  # 预算的5%
        },
        {
            "type": "时间保险",
            "description": "如行程延误，自动调整后续安排",
            "premium_rate": 0.03,
        },
    ]

    budget = core_intent.get("budget", {}).get("per_person", 500)

    bids = []
    for i, ins in enumerate(insurances):
        premium = budget * ins["premium_rate"]
        bids.append({
            "bid_id": f"bid_ins_{uuid.uuid4().hex[:6]}",
            "agent_type": "insurance",
            "agent_id": f"insurance_agent_{i}",
            "sub_need_id": sub_need["id"],
            "proposal": {
                "insurance_type": ins["type"],
                "description": ins["description"],
            },
            "confidence": 0.6,
            "base_cost": premium,
            "dynamic_price": premium,
            "cost_estimate": {"insurance_premium": premium},
            "created_at_round": round_num,
        })

    return bids


async def bid_aggregation_node(state: FederatedState) -> FederatedState:
    """竞标聚合节点。

    职责：
    1. 收集所有Agent的bids
    2. 执行市场出清
    3. 创建组合投标
    """
    bids = state.get("bids", [])
    intent_package = state.get("intent_package", {})
    core_intent = intent_package.get("core_intent", {})
    sub_needs = intent_package.get("decomposed_sub_needs", [])
    budget_limit = core_intent.get("budget", {}).get("per_person", 500)
    current_round = state.get("current_round", 1)

    if not bids:
        state["errors"].append("没有收集到任何竞标方案")
        return state

    # 1. 动态定价
    market_state = _compute_market_state(bids, sub_needs)
    for bid in bids:
        bid["dynamic_price"] = _compute_dynamic_price(bid, market_state)

    # 2. 市场出清
    clearing = _market_clear(bids, sub_needs, budget_limit)
    state["market_clearing"] = clearing

    # 3. 创建组合投标
    composite_bids = _create_composite_bids(clearing["winning_bids"], intent_package)
    state["composite_bids"] = composite_bids

    # 4. 记录本轮竞标
    round_record = {
        "round_number": current_round,
        "bids": bids,
        "composite_bids": composite_bids,
        "market_prices": market_state.get("market_prices", {}),
        "supply_demand_ratio": market_state.get("supply_demand_ratio", {}),
    }

    if "bidding_rounds" not in state:
        state["bidding_rounds"] = []
    state["bidding_rounds"].append(round_record)

    # 5. 保留winning bids
    state["bids"] = clearing["winning_bids"]

    return state


def _compute_market_state(bids: list, sub_needs: list) -> dict:
    """计算市场状态。"""
    # 按sub_need分组
    groups = {}
    for bid in bids:
        sn_id = bid.get("sub_need_id", "unknown")
        if sn_id not in groups:
            groups[sn_id] = []
        groups[sn_id].append(bid)

    # 计算供需比和市场价
    market_prices = {}
    supply_demand_ratio = {}

    for sn_id, group_bids in groups.items():
        count = len(group_bids)
        supply_demand_ratio[sn_id] = count / max(len(sub_needs), 1)

        # 市场价：中位数
        prices = [b.get("base_cost", 0) for b in group_bids]
        prices.sort()
        mid = len(prices) // 2
        market_prices[sn_id] = prices[mid] if prices else 0

    return {
        "groups": groups,
        "market_prices": market_prices,
        "supply_demand_ratio": supply_demand_ratio,
        "competitor_count": {sn_id: len(g) for sn_id, g in groups.items()},
        "type_count": _count_by_type(bids),
    }


def _count_by_type(bids: list) -> dict:
    """按agent_type计数。"""
    counts = {}
    for bid in bids:
        t = bid.get("agent_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


def _compute_dynamic_price(bid: dict, market_state: dict) -> float:
    """计算动态定价。"""
    base_cost = bid.get("base_cost", 0)
    sub_need_id = bid.get("sub_need_id", "")
    agent_type = bid.get("agent_type", "")

    # 竞争因子
    competitors = market_state.get("competitor_count", {}).get(sub_need_id, 1)
    competition_factor = max(0.7, 1.0 - 0.05 * (competitors - 1))

    # 稀缺溢价
    confidence = bid.get("confidence", 0.5)
    scarcity_premium = min(0.3, confidence * 0.1 / max(competitors, 1))

    # 供给过剩折扣
    same_type_count = market_state.get("type_count", {}).get(agent_type, 1)
    oversupply_discount = max(0, 0.05 * (same_type_count - 5))

    return base_cost * competition_factor * (1 + scarcity_premium - oversupply_discount)


def _market_clear(bids: list, sub_needs: list, budget_limit: float) -> MarketClearing:
    """市场出清：背包问题求解。"""
    if not bids:
        return {
            "winning_bids": [],
            "winning_composites": [],
            "budget_used": 0,
            "coverage": 0,
            "clearing_prices": {},
        }

    # 按sub_need分组
    groups = {}
    for bid in bids:
        sn_id = bid.get("sub_need_id", "core")
        if sn_id not in groups:
            groups[sn_id] = []
        groups[sn_id].append(bid)

    # 每组按性价比排序
    for sn_id, group in groups.items():
        group.sort(key=lambda b: b.get("confidence", 0) / max(b.get("dynamic_price", 1), 1), reverse=True)

    # 贪心选择
    selected = []
    remaining_budget = budget_limit
    covered_sub_needs = set()

    # 先保证每个sub_need有一个bid
    for sub_need in sub_needs:
        sn_id = sub_need.get("id", "core")
        group = groups.get(sn_id, [])

        for bid in group:
            cost = bid.get("dynamic_price", 0)
            if cost <= remaining_budget:
                selected.append(bid)
                remaining_budget -= cost
                covered_sub_needs.add(sn_id)
                break

    # 用剩余预算补充高分bid
    all_sorted = sorted(bids, key=lambda b: b.get("confidence", 0), reverse=True)
    for bid in all_sorted:
        if bid.get("bid_id") in [s.get("bid_id") for s in selected]:
            continue
        cost = bid.get("dynamic_price", 0)
        if cost <= remaining_budget:
            selected.append(bid)
            remaining_budget -= cost

    coverage = len(covered_sub_needs) / max(len(sub_needs), 1) if sub_needs else 1.0

    return {
        "winning_bids": selected[:15],  # 最多15个
        "winning_composites": [],
        "budget_used": budget_limit - remaining_budget,
        "coverage": coverage,
        "clearing_prices": {},
    }


def _create_composite_bids(winning_bids: list, intent_package: dict) -> list:
    """创建组合投标。"""
    if len(winning_bids) < 2:
        return []

    # 按类型分组
    poi_bids = [b for b in winning_bids if b.get("agent_type") == "poi"]
    food_bids = [b for b in winning_bids if b.get("agent_type") == "food"]

    if not poi_bids or not food_bids:
        return []

    composites = []
    for i, poi_bid in enumerate(poi_bids[:3]):
        for j, food_bid in enumerate(food_bids[:2]):
            total_cost = poi_bid.get("dynamic_price", 0) + food_bid.get("dynamic_price", 0)
            composites.append({
                "composite_id": f"comp_{uuid.uuid4().hex[:6]}",
                "agent_type": "composite",
                "sub_need_ids": [poi_bid.get("sub_need_id", "")],
                "component_bids": [poi_bid, food_bid],
                "total_cost": total_cost,
                "total_confidence": (poi_bid.get("confidence", 0.5) + food_bid.get("confidence", 0.5)) / 2,
                "synergy_bonus": 0.1,  # 协同奖励
            })

    return composites[:5]
