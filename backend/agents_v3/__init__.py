"""C版本：分布式智能体网络架构。

用户 → 元规则防火墙 → 事件总线 → [7Agent并行，全DeepSeek LLM]
→ 涌现式校验 → 协商 → 提案组装（不调用solver） → Live Itinerary
"""

from backend.agents_v3.graph import (
    build_feedback_graph_c,
    build_graph_c,
    get_feedback_graph_c,
    get_graph_c,
)
from backend.agents_v3.state import TravelState

__all__ = [
    "TravelState",
    "build_feedback_graph_c",
    "build_graph_c",
    "get_feedback_graph_c",
    "get_graph_c",
]
