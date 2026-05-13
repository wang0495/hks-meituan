"""LangGraph 流式事件到 SSE 的转换。

将LangGraph的stream事件转换为前端可消费的SSE事件。
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from backend.agents.state import PlanningState


def sse_event(event_type: str, data: dict) -> str:
    """格式化SSE事件。"""
    import json
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def graph_events_to_sse(
    graph_result: AsyncIterator[dict],
    sse_queue: asyncio.Queue,
) -> None:
    """将LangGraph流式事件转换为SSE事件并推送到队列。

    Args:
        graph_result: LangGraph的stream结果
        sse_queue: SSE事件队列
    """
    # 节点到phase的映射
    phase_map = {
        "parse_intent": "parsing",
        "intent_analyze": "parsing",
        "filter_pois": "searching",
        "solve_route": "solving",
        "time_cop": "validating",
        "fatigue_auditor": "validating",
        "local_expert": "validating",
        "budget_auditor": "validating",
        "arbitrate": "validating",
        "narrate": "narrating",
    }

    async for event in graph_result:
        event_type = event.get("type", "")
        node = event.get("node", "")
        data = event.get("data", {})

        if event_type == "node_start":
            phase = phase_map.get(node, "processing")
            await sse_queue.put(sse_event("phase", {
                "phase": phase,
                "message": f"正在{phase}...",
            }))

        elif event_type == "node_output":
            # Validator完成事件
            if node in ("time_cop", "fatigue_auditor", "local_expert", "budget_auditor"):
                issues = data.get("issues", [])

                # 发送每个issue的详情
                for issue in issues:
                    await sse_queue.put(sse_event("validation_issue", {
                        "agent": data.get("agent"),
                        "severity": issue.get("severity"),
                        "category": issue.get("category"),
                        "description": issue.get("description"),
                        "suggestion": issue.get("suggestion"),
                        "affected_indices": issue.get("affected_indices"),
                    }))

                # 发送validator结果摘要
                await sse_queue.put(sse_event("validation_result", {
                    "agent": data.get("agent"),
                    "issues_count": len(issues),
                    "high_count": sum(1 for i in issues if i.get("severity") == "high"),
                    "medium_count": sum(1 for i in issues if i.get("severity") == "medium"),
                    "low_count": sum(1 for i in issues if i.get("severity") == "low"),
                    "confidence": data.get("confidence"),
                }))

            elif node == "arbitrate":
                # 发送裁决摘要
                await sse_queue.put(sse_event("validation_summary", {
                    "action": data.get("action"),
                    "total_issues": len(data.get("issues", [])),
                    "stats": data.get("stats", {}),
                    "confidence": data.get("confidence"),
                    "summary": data.get("summary", ""),
                }))

                # 发送调整建议
                adjustments = data.get("adjustments", {})
                if adjustments.get("general_suggestions"):
                    for suggestion in adjustments["general_suggestions"]:
                        await sse_queue.put(sse_event("adjustment_suggestion", {
                            "category": suggestion.get("category"),
                            "severity": suggestion.get("severity"),
                            "suggestion": suggestion.get("suggestion"),
                        }))

                # 如果需要重新求解，发送信号
                action = data.get("action")
                if action == "re_solve":
                    await sse_queue.put(sse_event("phase", {
                        "phase": "re_solving",
                        "message": "检测到严重问题，正在重新规划...",
                    }))

            elif node == "narrate":
                narrative = data.get("narrative", {})
                # 发送每个步骤
                steps = narrative.get("steps", [])
                for i, step in enumerate(steps):
                    await sse_queue.put(sse_event("step", {
                        "index": i + 1,
                        "total": len(steps),
                        "poi": step.get("poi"),
                        "arrival_time": step.get("arrival_time"),
                        "departure_time": step.get("departure_time"),
                        "narrative": step.get("narrative"),
                        "emotion_design": step.get("emotion_design"),
                    }))

                # 发送预算信息
                budget = narrative.get("budget", {})
                if budget:
                    await sse_queue.put(sse_event("budget", budget))

            elif node == "solve_route":
                # 发送求解进度
                route = data.get("route", {})
                total_cost = route.get("total_cost", {})
                await sse_queue.put(sse_event("debug_solver", {
                    "route_length": len(route.get("route", [])),
                    "total_time": total_cost.get("time_min"),
                    "total_budget": total_cost.get("budget_used"),
                }))

        elif event_type == "error":
            await sse_queue.put(sse_event("error", {
                "error": event.get("error", "未知错误"),
            }))

    # 发送完成事件
    await sse_queue.put(sse_event("done", {"status": "completed"}))


async def run_graph_with_sse(
    graph,
    initial_state: dict,
    sse_queue: asyncio.Queue,
) -> dict:
    """运行图并转发事件到SSE队列。

    这是一个包装函数，用于在FastAPI路由中调用。

    Args:
        graph: 编译后的StateGraph
        initial_state: 初始状态
        sse_queue: SSE事件队列

    Returns:
        dict: 最终状态
    """
    # 启动图执行
    result = None

    async def run_and_collect():
        nonlocal result
        async for event in graph.astream(initial_state):
            # 将事件放入队列
            await sse_queue.put({"type": "graph_event", "data": event})
        # 获取最终结果
        result = await graph.ainvoke(initial_state)

    # 运行图
    await run_and_collect()

    return result
