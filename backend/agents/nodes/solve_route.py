"""solve_route 节点。

包装原solver.solve_route()服务，作为LangGraph工具节点。
支持重求解循环（当arbitrate要求re_solve时）。
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.agents.state import PlanningState
from backend.services.solver import solve_route as original_solve_route
from backend.services.data_service import get_data


def node(state: PlanningState) -> dict:
    """求解路线。

    调用原solver.solve_route，基于candidates和user_intent生成最优路线。
    支持多轮求解（round>0表示这是重求解）。

    Args:
        state: 当前规划状态，需包含candidates, user_intent

    Returns:
        dict: 包含route的更新片段
    """
    user_intent = state.get("user_intent", {})
    candidates = state.get("candidates", [])
    round_num = state.get("round", 0)
    arbitration = state.get("arbitration")

    if not candidates:
        return {
            "route": None,
            "errors": state.get("errors", []) + ["POI候选池为空"],
        }

    # 如果有arbitration的调整建议，应用它们
    if arbitration and arbitration.get("adjustments"):
        adjustments = arbitration["adjustments"]
        # 例如：移除有问题的POI
        if "excluded_poi_ids" in adjustments:
            excluded = set(adjustments["excluded_poi_ids"])
            candidates = [c for c in candidates if c.get("id") not in excluded]

    try:
        # 在线程池中运行同步solver（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        route = loop.run_in_executor(
            None,  # 使用默认线程池
            lambda: original_solve_route(
                candidates=candidates,
                user_intent=user_intent,
                start_time=user_intent.get("time", {}).get("start", "09:00"),
            )
        )
        route = asyncio.run(route) if asyncio.iscoroutine(route) else route

        # 增加轮数
        return {
            "route": route,
            "round": round_num + 1,
        }

    except Exception as e:
        return {
            "route": None,
            "errors": state.get("errors", []) + [f"路线求解失败: {e}"],
        }
