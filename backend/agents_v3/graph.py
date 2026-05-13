"""C版本LangGraph编排：分布式智能体网络。

用户 → rule_guard(意图+硬约束)
     → [7个Agent并行]（独立提案）
     → coordinator（LLM路线编排）
     → live_itinerary(热力图+决策溯源)
     → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.agents_v3.state import TravelState


def build_graph_c():
    """构建C版本图。"""
    from backend.agents_v3.nodes.rule_guard import rule_guard
    from backend.agents_v3.nodes.agents import (
        hotel_agent,
        poi_agent,
        food_agent,
        weather_agent,
        local_expert_agent,
        insurance_agent,
        traffic_agent,
    )
    from backend.agents_v3.nodes.coordinator import coordinator
    from backend.agents_v3.nodes.live_itinerary_node import live_itinerary

    graph = StateGraph(TravelState)

    # ── 注册节点 ──
    graph.add_node("rule_guard", rule_guard)
    graph.add_node("poi_agent", poi_agent)
    graph.add_node("food_agent", food_agent)
    graph.add_node("hotel_agent", hotel_agent)
    graph.add_node("traffic_agent", traffic_agent)
    graph.add_node("weather_agent", weather_agent)
    graph.add_node("local_expert_agent", local_expert_agent)
    graph.add_node("insurance_agent", insurance_agent)
    graph.add_node("coordinator", coordinator)
    graph.add_node("live_itinerary", live_itinerary)

    # ── 边 ──
    graph.set_entry_point("rule_guard")

    # rule_guard → 7个Agent并行
    graph.add_edge("rule_guard", "poi_agent")
    graph.add_edge("rule_guard", "food_agent")
    graph.add_edge("rule_guard", "hotel_agent")
    graph.add_edge("rule_guard", "traffic_agent")
    graph.add_edge("rule_guard", "weather_agent")
    graph.add_edge("rule_guard", "local_expert_agent")
    graph.add_edge("rule_guard", "insurance_agent")

    # 7个Agent → coordinator（fan-in）
    graph.add_edge("poi_agent", "coordinator")
    graph.add_edge("food_agent", "coordinator")
    graph.add_edge("hotel_agent", "coordinator")
    graph.add_edge("traffic_agent", "coordinator")
    graph.add_edge("weather_agent", "coordinator")
    graph.add_edge("local_expert_agent", "coordinator")
    graph.add_edge("insurance_agent", "coordinator")

    # coordinator → live_itinerary → END
    graph.add_edge("coordinator", "live_itinerary")
    graph.add_edge("live_itinerary", END)

    return graph.compile()


_graph_c = None


def get_graph_c():
    """获取C版本图（单例）。"""
    global _graph_c
    if _graph_c is None:
        _graph_c = build_graph_c()
    return _graph_c
