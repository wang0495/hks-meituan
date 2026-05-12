"""A版本LangGraph组装 - 3层联邦架构完整实现。

使用Send()实现fan-out并行执行：
- 竞标市场：多个Agent并行投标
- 校验市场：多个Validator并行校验
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from backend.agents_v2.state import FederatedState, BidTask, ValidationTask


def build_graph_a() -> StateGraph:
    """构建A版本图（3层联邦架构）。"""
    from backend.agents_v2.nodes.intent_probe import intent_probe_node
    from backend.agents_v2.nodes.bidding_market import (
        bidding_market_node,
        individual_bid_node,
        bid_aggregation_node,
    )
    from backend.agents_v2.nodes.validation_market import (
        validation_market_node,
        individual_validator_node,
        validation_aggregation_node,
    )
    from backend.agents_v2.nodes.micro_negotiation import micro_negotiation_node

    graph = StateGraph(FederatedState)

    # ========================================================================
    # 注册节点
    # ========================================================================

    # Layer 1
    graph.add_node("intent_probe", intent_probe_node)

    # 竞标市场
    graph.add_node("bidding_market", bidding_market_node)
    graph.add_node("individual_bid", individual_bid_node)
    graph.add_node("bid_aggregation", bid_aggregation_node)

    # Layer 2
    graph.add_node("validation_market", validation_market_node)
    graph.add_node("individual_validator", individual_validator_node)
    graph.add_node("validation_aggregation", validation_aggregation_node)

    # Layer 3
    graph.add_node("micro_negotiation", micro_negotiation_node)

    # ========================================================================
    # 注册边
    # ========================================================================

    # 入口
    graph.set_entry_point("intent_probe")

    # Layer 1 → 竞标市场
    graph.add_edge("intent_probe", "bidding_market")

    # 竞标市场 → fan-out到各Agent
    def fan_out_bidders(state: FederatedState) -> list[Send]:
        """并行派出竞标任务。"""
        intent_package = state.get("intent_package")
        if not intent_package:
            return [Send("bid_aggregation", state)]  # 降级：直接聚合

        sub_needs = intent_package.get("decomposed_sub_needs", [])
        if not sub_needs:
            sub_needs = [{
                "id": "core",
                "description": "核心需求",
                "constraints": intent_package.get("core_intent", {}),
                "priority": 10,
                "time_window": None,
            }]

        # 每个sub_need × 每个Agent类型 = 一个竞标任务
        agent_types = ["poi", "food", "activity", "transport", "insurance"]
        current_round = state.get("current_round", 1)

        sends = []
        for sub_need in sub_needs:
            for agent_type in agent_types:
                task_state = dict(state)
                task_state["_bid_task"] = {
                    "sub_need": sub_need,
                    "agent_type": agent_type,
                    "round_number": current_round,
                }
                sends.append(Send("individual_bid", task_state))

        return sends if sends else [Send("bid_aggregation", state)]

    graph.add_conditional_edges("bidding_market", fan_out_bidders)

    # 各Agent → 聚合
    graph.add_edge("individual_bid", "bid_aggregation")

    # 聚合 → Layer 2
    graph.add_edge("bid_aggregation", "validation_market")

    # Layer 2 → fan-out到各Validator
    def fan_out_validators(state: FederatedState) -> list[Send]:
        """并行派出校验任务。"""
        bids = state.get("bids", [])
        intent_package = state.get("intent_package")

        if not bids:
            return [Send("validation_aggregation", state)]

        validators = ["time_cop", "fatigue_auditor", "budget_auditor", "local_expert", "critic", "realtime"]

        sends = []
        for validator_name in validators:
            task_state = dict(state)
            task_state["_validation_task"] = {
                "validator_name": validator_name,
                "bids": bids,
                "composite_bids": state.get("composite_bids", []),
                "intent_package": intent_package,
            }
            sends.append(Send("individual_validator", task_state))

        return sends

    graph.add_conditional_edges("validation_market", fan_out_validators)

    # 各Validator → 聚合
    graph.add_edge("individual_validator", "validation_aggregation")

    # 校验聚合 → 条件边
    def after_validation(state: FederatedState) -> str:
        """判断校验后是否需要重试。"""
        issues = state.get("validation_issues", [])
        surviving = state.get("surviving_bids", [])
        round_num = state.get("round", 0)

        high_count = sum(1 for i in issues if i.get("severity") == "high")

        # 条件1: high问题太多
        if high_count > 3 and round_num < 2:
            state["round"] = round_num + 1
            return "retry"

        # 条件2: surviving太少
        if len(surviving) < 2 and round_num < 2:
            state["round"] = round_num + 1
            return "retry"

        return "proceed"

    graph.add_conditional_edges(
        "validation_aggregation",
        after_validation,
        {
            "retry": "bidding_market",
            "proceed": "micro_negotiation",
        }
    )

    # Layer 3 → 条件边
    def after_negotiation(state: FederatedState) -> str:
        """判断是否需要重协商。"""
        if state.get("renegotiation_scope"):
            return "renegotiate"
        return "end"

    graph.add_conditional_edges(
        "micro_negotiation",
        after_negotiation,
        {
            "renegotiate": "micro_negotiation",
            "end": END,
        }
    )

    return graph.compile()


# 全局图实例
_graph_a = None


def get_graph_a():
    """获取A版本图实例（单例）。"""
    global _graph_a
    if _graph_a is None:
        _graph_a = build_graph_a()
    return _graph_a
