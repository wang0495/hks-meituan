"""A版本SSE流式事件转换。"""

from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: dict) -> str:
    """格式化SSE事件。"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# A版本节点到phase的映射
A_VERSION_PHASE_MAP = {
    # Layer 1
    "intent_probe": "intent_probing",
    "contradiction_mediation": "contradiction_mediation",

    # 竞标市场
    "bidding_market": "market_opening",
    "individual_bid": "bidding",
    "bid_aggregation": "market_clearing",

    # Layer 2
    "validation_market": "validation",
    "individual_validator": "validating",
    "validation_aggregation": "validation_summary",

    # Layer 3
    "micro_negotiation": "negotiating",
    "contract_formation": "contract_formation",
    "tsptw_optimization": "route_optimizing",
}

# Phase描述
PHASE_DESCRIPTIONS = {
    "intent_probing": "正在深度理解您的需求...",
    "contradiction_mediation": "正在识别和调和需求矛盾...",
    "market_opening": "正在开放竞标市场...",
    "bidding": "正在收集方案建议...",
    "market_clearing": "正在筛选最优方案...",
    "validation": "正在进行多维度校验...",
    "validating": "正在校验方案可行性...",
    "validation_summary": "正在汇总校验结果...",
    "negotiating": "正在协调各方案时间...",
    "contract_formation": "正在形成时间契约...",
    "route_optimizing": "正在优化路线...",
}


def format_probe_question_event(question: dict) -> str:
    """格式化追问问题事件。"""
    return sse_event("probe_question", {
        "question_id": question.get("question_id"),
        "question": question.get("question"),
        "options": question.get("options", []),
        "related_contradiction": question.get("related_contradiction"),
    })


def format_contradiction_event(contradiction: dict) -> str:
    """格式化矛盾识别事件。"""
    return sse_event("contradiction_detected", {
        "type": contradiction.get("type"),
        "description": contradiction.get("description"),
        "severity": contradiction.get("severity"),
        "resolution": contradiction.get("resolution"),
    })


def format_bid_event(bid: dict, round_num: int) -> str:
    """格式化竞标事件。"""
    return sse_event("bid_received", {
        "bid_id": bid.get("bid_id"),
        "agent_type": bid.get("agent_type"),
        "sub_need_id": bid.get("sub_need_id"),
        "confidence": bid.get("confidence"),
        "price": bid.get("dynamic_price"),
        "round": round_num,
    })


def format_market_clearing_event(clearing: dict) -> str:
    """格式化市场出清事件。"""
    return sse_event("market_cleared", {
        "winning_count": len(clearing.get("winning_bids", [])),
        "composite_count": len(clearing.get("winning_composites", [])),
        "budget_used": clearing.get("budget_used"),
        "coverage": clearing.get("coverage"),
    })


def format_validation_issue_event(issue: dict) -> str:
    """格式化校验问题事件。"""
    return sse_event("validation_issue", {
        "validator": issue.get("validator"),
        "severity": issue.get("severity"),
        "category": issue.get("category"),
        "description": issue.get("description"),
        "suggestion": issue.get("suggestion"),
    })


def format_contract_event(contract: dict) -> str:
    """格式化契约事件。"""
    return sse_event("contract_formed", {
        "contract_id": contract.get("contract_id"),
        "from_bid": contract.get("bid_a"),
        "to_bid": contract.get("bid_b"),
        "handoff_time": contract.get("handoff_time"),
        "transport_mode": contract.get("transport_mode"),
    })


def format_runtime_alert_event(alert: dict) -> str:
    """格式化运行时告警事件。"""
    return sse_event("runtime_alert", {
        "type": alert.get("type"),
        "severity": alert.get("severity"),
        "description": alert.get("description"),
        "suggested_action": alert.get("suggested_action"),
    })


def format_done_event(route_id: str, route: dict) -> str:
    """格式化完成事件。"""
    return sse_event("done", {
        "route_id": route_id,
        "version": "a",
        "poi_count": len(route.get("route", [])),
        "total_time": route.get("total_cost", {}).get("time_min", 0),
        "total_budget": route.get("total_cost", {}).get("budget_used", 0),
    })


def format_error_event(error: str) -> str:
    """格式化错误事件。"""
    return sse_event("error", {
        "error": error,
        "version": "a",
    })
