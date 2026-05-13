"""C版本LangGraph编排：讨论池架构（带回环）。

用户 → rule_guard(意图+LLM核心景点)
     → [7个Agent并行]（独立提案）
     → review(质疑)
         │
         ├─ 不通过 → rework(按反馈重选) ──→ coordinator
         │                ↑                 ↑
         └─ 通过 ──────────────────────────┘
                        │
                        ↓
                  live_itinerary → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.agents_v3.state import TravelState


def build_graph_c():
    """构建C版本图（讨论池架构）。"""
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
    from backend.agents_v3.nodes.review import review, rework
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
    graph.add_node("review", review)
    graph.add_node("rework", rework)
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

    # 7个Agent → review（fan-in）
    graph.add_edge("poi_agent", "review")
    graph.add_edge("food_agent", "review")
    graph.add_edge("hotel_agent", "review")
    graph.add_edge("traffic_agent", "review")
    graph.add_edge("weather_agent", "review")
    graph.add_edge("local_expert_agent", "review")
    graph.add_edge("insurance_agent", "review")

    # review → 条件边
    graph.add_conditional_edges(
        "review",
        _review_router,
        {
            "approved": "coordinator",
            "rework": "rework",
        },
    )

    # rework → coordinator
    graph.add_edge("rework", "coordinator")

    # coordinator → live_itinerary → END
    graph.add_edge("coordinator", "live_itinerary")
    graph.add_edge("live_itinerary", END)

    return graph.compile()


def _review_router(state: TravelState) -> str:
    """review后的路由：有反馈→rework，没反馈→前进。"""
    feedback = state.get("review_feedback", [])
    round_num = state.get("review_round", 0)

    # 超过2轮强制前进
    if round_num > 2:
        return "approved"

    if not feedback:
        return "approved"

    return "rework"


_graph_c = None


def get_graph_c():
    """获取C版本图（单例）。"""
    global _graph_c
    if _graph_c is None:
        _graph_c = build_graph_c()
    return _graph_c
