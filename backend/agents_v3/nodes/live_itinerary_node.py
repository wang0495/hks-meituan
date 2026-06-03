"""Live Itinerary节点：热力图 + 决策溯源。

对应架构Layer 6：动态行程呈现。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.agents_v3.live_itinerary.builder import (
    build_decision_trace,
    build_heatmap,
)

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState


async def live_itinerary(state: TravelState) -> dict:
    """构建动态行程：热力图 + 决策溯源。"""
    proposals = state.get("proposals", [])
    conflicts = state.get("conflicts", [])

    heatmap = build_heatmap(proposals, conflicts)
    decision_trace = build_decision_trace(proposals)

    return {
        "heatmap": heatmap,
        "decision_trace": decision_trace,
    }
