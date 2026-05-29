"""MoE版本LangGraph编排：混合专家架构（两波分派）。

用户 → rule_guard(意图+POI加载)
     → expert_router(LLM分类+专家权重)
     → Wave1: [POI, Food, Weather, Destination 并行, 数据独立]
       → Wave2: [Traffic, Hotel, Local, Budget_hacker 并行, 依赖Wave1结果]
     → review(质疑)
         │
         ├─ 不通过 → rework(按反馈重选) → synthesizer
         │                ↑                 ↑
         └─ 通过 ──────────────────────────┘
                        │
                        ↓
                  live_itinerary → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from backend.agents_v3.state import TravelState

# ── 两波分派定义 ──
# Wave 1: 数据独立，可并行
WAVE1_EXPERTS = {"poi", "food", "weather", "destination"}
# Wave 2: 依赖 Wave 1 的 POI/位置结果
WAVE2_EXPERTS = {"traffic", "hotel", "local_expert", "budget_hacker"}

# 专家名 → 对应import路径的映射
_EXPERT_MAP = {
    "poi": ("backend.agents_v3.experts.poi_expert", "poi_expert"),
    "food": ("backend.agents_v3.experts.food_expert", "food_expert"),
    "hotel": ("backend.agents_v3.experts.hotel_expert", "hotel_expert"),
    "traffic": ("backend.agents_v3.experts.traffic_expert", "traffic_expert"),
    "weather": ("backend.agents_v3.experts.weather_expert", "weather_expert"),
    "local_expert": ("backend.agents_v3.experts.local_expert", "local_expert"),
    "destination": ("backend.agents_v3.experts.destination_expert", "destination_expert"),
    "budget_hacker": ("backend.agents_v3.experts.budget_hacker", "budget_hacker"),
}


def _wave1_dispatcher(state: TravelState) -> list[Send]:
    """Wave 1: 数据独立的专家并行执行。

    如果没有 Wave1 专家匹配，直接跳到 wave2_fanin（然后到 review）。
    """
    active = state.get("active_experts", [])
    wave1_active = [name for name in active if name in WAVE1_EXPERTS]
    # POI 永远激活（expert_router 已保证，但防御性检查）
    if "poi" not in wave1_active and "poi" in active:
        wave1_active.append("poi")
    if not wave1_active:
        return [Send("wave2_fanin", state)]
    sends = []
    for name in wave1_active:
        if name in _EXPERT_MAP:
            sends.append(Send(name, state))
    return sends


def _wave2_dispatcher(state: TravelState) -> list[Send]:
    """Wave 2: 依赖 Wave 1 结果的专家并行执行。

    如果没有 Wave2 专家需要执行，直接 Send 到 review。
    """
    active = state.get("active_experts", [])
    wave2_active = [name for name in active if name in WAVE2_EXPERTS]
    if not wave2_active:
        return [Send("review", state)]
    sends = []
    for name in wave2_active:
        if name in _EXPERT_MAP:
            sends.append(Send(name, state))
    return sends


def _wave2_fanin(state: TravelState) -> dict:
    """Wave1 fan-in node: 原样传递 state（不修改），只用于连接条件边。"""
    return {}  # LangGraph merges empty dict into state


def build_graph_c():
    """构建MoE版本图（两波分派）。"""
    from backend.agents_v3.nodes.rule_guard import rule_guard
    from backend.agents_v3.nodes.expert_router import expert_router
    from backend.agents_v3.nodes.review import review, rework
    from backend.agents_v3.nodes.synthesizer import synthesizer
    from backend.agents_v3.nodes.live_itinerary_node import live_itinerary

    graph = StateGraph(TravelState)

    # ── 注册节点 ──
    graph.add_node("rule_guard", rule_guard)
    graph.add_node("expert_router", expert_router)
    graph.add_node("wave2_fanin", _wave2_fanin)

    # 动态注册所有专家节点
    _loaded_experts = {}
    for name, (module_path, func_name) in _EXPERT_MAP.items():
        import importlib
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
        graph.add_node(name, func)
        _loaded_experts[name] = name

    graph.add_node("review", review)
    graph.add_node("rework", rework)
    graph.add_node("synthesizer", synthesizer)
    graph.add_node("live_itinerary", live_itinerary)

    # ── 边 ──
    graph.set_entry_point("rule_guard")

    # rule_guard → expert_router
    graph.add_edge("rule_guard", "expert_router")

    # expert_router → Wave1 fan-out（数据独立的专家）
    graph.add_conditional_edges("expert_router", _wave1_dispatcher)

    # Wave1 experts → wave2_fanin（汇聚点）
    for name in WAVE1_EXPERTS:
        if name in _loaded_experts:
            graph.add_edge(name, "wave2_fanin")

    # wave2_fanin → Wave2 fan-out（条件边分发）
    graph.add_conditional_edges("wave2_fanin", _wave2_dispatcher)

    # Wave2 experts → review（最终 fan-in）
    for name in WAVE2_EXPERTS:
        if name in _loaded_experts:
            graph.add_edge(name, "review")

    # review → 条件边
    graph.add_conditional_edges(
        "review",
        _review_router,
        {
            "approved": "synthesizer",
            "rework": "rework",
        },
    )

    # rework → review（修完二次检查，review_round上限防死循环）
    graph.add_edge("rework", "review")

    # synthesizer → live_itinerary → END
    graph.add_edge("synthesizer", "live_itinerary")
    graph.add_edge("live_itinerary", END)

    return graph.compile()


def _review_router(state: TravelState) -> str:
    """review后的路由：有反馈→rework，没反馈→前进。"""
    feedback = state.get("review_feedback", [])
    round_num = state.get("review_round", 0)

    if round_num > 2:
        return "approved"

    if not feedback:
        return "approved"

    return "rework"


_graph_c = None


def get_graph_c():
    """获取MoE版本图（单例）。"""
    global _graph_c
    if _graph_c is None:
        _graph_c = build_graph_c()
    return _graph_c
