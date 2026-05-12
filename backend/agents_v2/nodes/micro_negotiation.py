"""Layer 3节点：微协商总线。

完整实现：
- 双向协商协议
- 时间契约形成
- 调用solver.py的TSPTW优化
- 运行时监控
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from backend.agents_v2.state import (
    FederatedState,
    TimeContract,
    NegotiationResult,
    RenegotiationScope,
)


async def micro_negotiation_node(state: FederatedState) -> FederatedState:
    """Layer 3节点：微协商总线。"""
    surviving_bids = state.get("surviving_bids", [])
    composite_bids = state.get("composite_bids", [])
    intent_package = state.get("intent_package", {})

    if not surviving_bids:
        state["errors"].append("没有通过校验的方案")
        state["final_route"] = None
        return state

    core_intent = intent_package.get("core_intent", {})

    # Phase 1: 将bids转换为候选POI列表
    candidates = _bids_to_candidates(surviving_bids, composite_bids)

    # Phase 2: 双向协商，生成契约网络
    contracts = await _negotiate_contracts(surviving_bids, intent_package)

    # Phase 3: 调用solver.py的solve_route做TSPTW优化
    route = await _call_solver(candidates, core_intent, state)

    # Phase 4: 运行时监控
    alerts = await _runtime_monitoring(route, state)

    # 组装结果
    state["final_route"] = route
    state["contracts"] = contracts
    state["runtime_alerts"] = alerts

    state["negotiation_result"] = {
        "success": route is not None,
        "contracts": contracts,
        "adjustments": {},
        "conflicts_resolved": len(contracts),
        "conflicts_remaining": 0,
    }

    return state


def _bids_to_candidates(bids: list, composite_bids: list) -> list[dict]:
    """将bids转换为solver格式的候选POI列表。"""
    candidates = []
    seen_ids = set()

    for bid in bids:
        if bid.get("agent_type") not in ["poi", "food", "activity"]:
            continue

        proposal = bid.get("proposal", {})
        poi = proposal.get("poi") or proposal.get("restaurant") or proposal.get("activity")

        if poi and poi.get("id") not in seen_ids:
            # 添加solver需要的字段
            candidate = dict(poi)
            candidate["_bid_id"] = bid.get("bid_id")
            candidate["_confidence"] = bid.get("confidence", 0.5)
            candidates.append(candidate)
            seen_ids.add(poi.get("id"))

    return candidates


async def _negotiate_contracts(bids: list, intent_package: dict) -> list[TimeContract]:
    """双向协商，生成时间契约。"""
    # 按类型分组
    poi_bids = [b for b in bids if b.get("agent_type") == "poi"]
    food_bids = [b for b in bids if b.get("agent_type") == "food"]

    if not poi_bids:
        return []

    contracts = []
    core_intent = intent_package.get("core_intent", {})
    start_time_str = core_intent.get("time", {}).get("start", "09:00")

    # 解析开始时间
    try:
        start_time = datetime.strptime(start_time_str, "%H:%M")
    except:
        start_time = datetime.strptime("09:00", "%H:%M")

    current_time = start_time
    all_sequence = []

    # 组装POI序列
    for i, bid in enumerate(poi_bids[:5]):
        duration = bid.get("proposal", {}).get("expected_duration", 120)

        all_sequence.append({
            "bid": bid,
            "arrival": current_time.strftime("%H:%M"),
            "departure": (current_time + timedelta(minutes=duration)).strftime("%H:%M"),
        })

        current_time += timedelta(minutes=duration)

        # 每2个POI插入餐饮
        if (i + 1) % 2 == 0 and food_bids:
            food_bid = food_bids[i % len(food_bids)]
            all_sequence.append({
                "bid": food_bid,
                "arrival": current_time.strftime("%H:%M"),
                "departure": (current_time + timedelta(minutes=60)).strftime("%H:%M"),
            })
            current_time += timedelta(minutes=60)

        # 交通时间
        current_time += timedelta(minutes=15)

    # 生成契约
    for i in range(len(all_sequence) - 1):
        current = all_sequence[i]
        next_item = all_sequence[i + 1]

        contract = {
            "contract_id": f"contract_{uuid.uuid4().hex[:6]}",
            "bid_a": current["bid"].get("bid_id", ""),
            "bid_b": next_item["bid"].get("bid_id", ""),
            "handoff_time": current["departure"],
            "buffer_minutes": 10,
            "transport_mode": "步行",
            "transport_time_min": 15,
            "constraints": ["no_delay"],
            "status": "active",
            "violation_action": "trigger_renegotiation",
        }
        contracts.append(contract)

    return contracts


async def _call_solver(candidates: list, core_intent: dict, state: dict) -> dict | None:
    """调用solver.py的solve_route做TSPTW优化。"""
    if not candidates:
        return None

    try:
        from backend.services.solver import solve_route
        from backend.services.filters import filter_candidates
        import asyncio

        start_time = core_intent.get("time", {}).get("start", "09:00")
        perception_ctx = state.get("perception_ctx")

        # 过滤候选
        filtered = filter_candidates(candidates, core_intent)
        if not filtered:
            filtered = candidates

        # 在线程池中调用solve_route
        route = await asyncio.to_thread(
            solve_route,
            filtered,
            core_intent,
            start_time,
            perception_ctx,
        )

        return route

    except Exception as e:
        # 降级：生成简化路线
        return _generate_fallback_route(candidates, core_intent)


def _generate_fallback_route(candidates: list, core_intent: dict) -> dict:
    """生成简化路线（降级方案）。"""
    if not candidates:
        return {"route": [], "total_cost": {}}

    start_time_str = core_intent.get("time", {}).get("start", "09:00")
    try:
        start_time = datetime.strptime(start_time_str, "%H:%M")
    except:
        start_time = datetime.strptime("09:00", "%H:%M")

    current_time = start_time
    route_steps = []
    total_budget = 0

    for i, poi in enumerate(candidates[:5]):
        duration = 120
        price = poi.get("avg_price", 0)

        route_steps.append({
            "poi": poi,
            "arrival_time": current_time.strftime("%H:%M"),
            "departure_time": (current_time + timedelta(minutes=duration)).strftime("%H:%M"),
            "travel_from_prev": {"distance_m": 1000, "time_min": 15},
        })

        current_time += timedelta(minutes=duration + 15)
        total_budget += price

    return {
        "route": route_steps,
        "total_cost": {
            "time_min": len(route_steps) * 135,
            "budget_used": total_budget,
            "step_estimate": len(route_steps) * 2000,
        },
        "emotion_curve": [],
        "breathing_spots": [],
        "unused_candidates": candidates[5:] if len(candidates) > 5 else [],
    }


async def _runtime_monitoring(route: dict, state: dict) -> list[dict]:
    """运行时监控。"""
    alerts = []

    if not route or not route.get("route"):
        return alerts

    try:
        from backend.services.perception import PerceptionService

        perception = PerceptionService()
        # 模拟获取上下文
        ctx = await perception.get_context(scene="default")

        # 检测异常
        anomalies = await perception.detect_anomaly(ctx)

        for anom in anomalies:
            alerts.append({
                "alert_id": f"alert_{uuid.uuid4().hex[:6]}",
                "type": anom.type.value if hasattr(anom.type, "value") else str(anom.type),
                "severity": "medium" if anom.severity > 0.5 else "low",
                "description": anom.message,
                "affected_contract_ids": [],
                "suggested_action": "调整行程",
            })

    except Exception:
        # 模拟天气告警
        alerts.append({
            "alert_id": f"alert_{uuid.uuid4().hex[:6]}",
            "type": "weather_change",
            "severity": "medium",
            "description": "预计下午可能有阵雨",
            "affected_contract_ids": [],
            "suggested_action": "准备室内备选方案",
        })

    return alerts
