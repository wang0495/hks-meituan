"""LangGraph StateGraph 构建。

构建多智能体路线规划图：
- parse_intent → intent_analyze → filter_pois → solve_route
- fan-out (Send) 到4个validator并行校验
- fan-in 到arbitrate汇总裁决
- 条件边: pass→narrate / re_solve→solve_route(循环)
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.types import Send

from backend.agents.state import PlanningState


def build_graph() -> StateGraph:
    """构建路线规划StateGraph。

    返回可执行的StateGraph，支持：
    - 串行节点: parse → intent → filter → solve
    - fan-out: 并行派出4个validator
    - fan-in: 汇总所有validator结果
    - 条件边: 根据arbitrate结果选择pass或re_solve

    Returns:
        StateGraph: 可编译执行的图
    """
    from backend.agents.nodes import (
        parse_intent,
        intent_analyst,
        filter_pois,
        solve_route,
        time_cop,
        fatigue_auditor,
        local_expert,
        budget_auditor,
        arbitrate,
        narrate,
    )

    # 创建图
    graph = StateGraph(PlanningState)

    # 注册节点
    graph.add_node("parse_intent", parse_intent.node)
    graph.add_node("intent_analyze", intent_analyst.node)
    graph.add_node("filter_pois", filter_pois.node)
    graph.add_node("solve_route", solve_route.node)

    # validator节点
    graph.add_node("time_cop", time_cop.node)
    graph.add_node("fatigue_auditor", fatigue_auditor.node)
    graph.add_node("local_expert", local_expert.node)
    graph.add_node("budget_auditor", budget_auditor.node)

    graph.add_node("arbitrate", arbitrate.node)
    graph.add_node("narrate", narrate.node)

    # 设置入口点
    graph.set_entry_point("parse_intent")

    # 串行边: parse → intent → filter → solve
    graph.add_edge("parse_intent", "intent_analyze")
    graph.add_edge("intent_analyze", "filter_pois")
    graph.add_edge("filter_pois", "solve_route")

    # fan-out: solve → 并行派发到所有validator
    def fan_out_validators(state: PlanningState) -> list[Send]:
        """并行派出所有validator节点。"""
        # 确保有route才派validator
        if not state.get("route"):
            return []

        validators = ["time_cop", "fatigue_auditor", "local_expert", "budget_auditor"]
        return [Send(v, state) for v in validators]

    graph.add_conditional_edges("solve_route", fan_out_validators)

    # fan-in: 所有validator → arbitrate
    for validator in ["time_cop", "fatigue_auditor", "local_expert", "budget_auditor"]:
        graph.add_edge(validator, "arbitrate")

    # 条件边: arbitrate结果决定pass或re_solve
    def route_decision(state: PlanningState) -> str:
        """根据arbitrate决策选择下一步。"""
        arbitration = state.get("arbitration")
        if not arbitration:
            return "pass"

        action = arbitration.get("action", "pass")
        round_num = state.get("round", 0)

        # re_solve最多2轮，超过直接pass
        if action == "re_solve" and round_num < 2:
            return "re_solve"
        return "pass"

    graph.add_conditional_edges(
        "arbitrate",
        route_decision,
        {
            "pass": "narrate",
            "re_solve": "solve_route",  # 循环回solver
        },
    )

    graph.add_edge("narrate", END)

    return graph.compile()


# 全局单例图实例
_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    """获取全局图实例。"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
