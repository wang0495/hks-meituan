"""parse_intent 节点。

包装原 intent_parser.parse_intent() 服务，作为LangGraph工具节点。
"""

from __future__ import annotations

from backend.agents.state import PlanningState
from backend.services.intent_parser import parse_intent as original_parse_intent


async def node(state: PlanningState) -> dict:
    """解析用户输入为意图。

    调用原parse_intent服务，将user_input转换为user_intent。

    Args:
        state: 当前规划状态，需包含user_input

    Returns:
        dict: 包含user_intent的更新片段
    """
    user_input = state.get("user_input", "")

    if not user_input:
        return {
            "errors": state.get("errors", []) + ["用户输入为空"],
            "user_intent": {},
        }

    try:
        user_intent = await original_parse_intent(user_input)
        return {"user_intent": user_intent}
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [f"意图解析失败: {e}"],
            "user_intent": {},
        }
