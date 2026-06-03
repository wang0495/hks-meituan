"""涌现式校验节点。

对应架构Layer 5：Agent间矛盾自动探测。
检测：地理矛盾、预算超支、时间冲突、主题矛盾。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.agents_v3.emergence.conflict_detector import (
    detect_conflicts,
    resolve_conflicts,
    should_escalate,
)

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState


async def emergence_check(state: TravelState) -> dict:
    """涌现式校验：检测矛盾，自动解决可解决的。"""
    proposals = state.get("proposals", [])
    intent = state.get("user_intent", {})

    # 检测矛盾
    conflicts = detect_conflicts(proposals, intent)

    # 自动解决
    resolve_conflicts(proposals, conflicts)

    # 是否需要升级
    user_decision_needed = should_escalate(conflicts)

    # 生成协商消息
    negotiation_msgs = []
    for c in conflicts:
        negotiation_msgs.append(
            {
                "type": c.get("type", ""),
                "from": "emergence_check",
                "message": c.get("description", ""),
                "severity": c.get("severity", "low"),
                "auto_resolved": c.get("auto_resolvable", False),
            }
        )

    return {
        "conflicts": conflicts,
        "user_decision_needed": user_decision_needed,
        "negotiation_msgs": negotiation_msgs,
    }
