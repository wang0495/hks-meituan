"""narrate 节点。

包装原narrator.generate_narrative()服务，作为LangGraph工具节点。
"""

from __future__ import annotations

from backend.agents.state import PlanningState
from backend.services.narrator import generate_narrative as original_generate_narrative


async def node(state: PlanningState) -> dict:
    """生成文案。

    调用原narrator服务，为路线生成描述文案。

    Args:
        state: 当前规划状态，需包含route和user_intent

    Returns:
        dict: 包含narrative的更新片段
    """
    route = state.get("route")
    user_intent = state.get("user_intent", {})

    if not route:
        return {
            "narrative": None,
            "errors": state.get("errors", []) + ["路线为空，无法生成文案"],
        }

    try:
        narrative = await original_generate_narrative(
            route=route,
            user_intent=user_intent,
        )

        return {"narrative": narrative}

    except Exception as e:
        return {
            "narrative": None,
            "errors": state.get("errors", []) + [f"文案生成失败: {e}"],
        }
