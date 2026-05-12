"""A版本LangGraph组装 - 3层联邦架构。"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from backend.agents_v2.state import FederatedState
from backend.agents_v2.layers.layer1_intent import layer1_intent_node
from backend.agents_v2.market.bidding_market import bidding_market
from backend.agents_v2.layers.layer2_validation import layer2_validation_market
from backend.agents_v2.negotiation.micro_bus import layer3_micro_negotiation


# LangGraph条件边
def should_retry(state: FederatedState) -> str:
    """判断是否需要重试。"""
    if state.get("round", 0) >= 2:
        return "end"

    # 如果Layer2发现问题太多，增加轮数
    issues = state.get("validation_issues", [])
    high_count = sum(1 for i in issues if i.get("severity") == "high")

    if high_count > 3:
        state["round"] = state.get("round", 0) + 1
        return "retry"

    return "end"


def build_graph_a() -> StateGraph:
    """构建A版本图（3层联邦架构）。"""
    graph = StateGraph(FederatedState)

    # 注册节点
    graph.add_node("layer1_intent", layer1_intent_node)
    graph.add_node("bidding_market", bidding_market)
    graph.add_node("layer2_validation", layer2_validation_market)
    graph.add_node("layer3_negotiation", layer3_micro_negotiation)

    # 注册边
    graph.add_edge("layer1_intent", "bidding_market")
    graph.add_edge("bidding_market", "layer2_validation")
    graph.add_edge("layer2_validation", "layer3_negotiation")

    # 条件边：如果发现问题太多，回到bidding重新竞标
    graph.add_conditional_edges(
        "layer3_negotiation",
        should_retry,
        {"retry": "bidding_market", "end": END}
    )

    # 设置入口
    graph.set_entry_point("layer1_intent")

    return graph.compile()


# 全局图实例
_graph_a = None


def get_graph_a():
    """获取A版本图实例（单例）。"""
    global _graph_a
    if _graph_a is None:
        _graph_a = build_graph_a()
    return _graph_a
