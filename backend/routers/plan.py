"""CityFlow 核心路线规划路由。

包含路线规划（plan）、路线查询（route）、路线调整（adjust）、
对话式调整（dialogue）、健康检查（health）、缓存统计（cache_stats）。
"""

from __future__ import annotations

import asyncio
import copy
import logging
import uuid
from contextlib import suppress

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.errors import CityFlowException, ErrorCode
from backend.schemas import AdjustRequest, HealthResponse, PlanRequest
from backend.services.cache import (
    feedback_state_cache,
    general_cache,
    get_multilevel_cache,
    poi_cache,
    profile_cache,
    route_cache,
    distance_cache,
)
from backend.utils.sse_helpers import sse as _sse

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# SSE 并发连接限制（Semaphore，线程安全、asyncio-safe）
# ---------------------------------------------------------------------------
_plan_semaphore = asyncio.Semaphore(20)


# ---------------------------------------------------------------------------
# UX 增强：快速首 token + 周期性进度播报
# ---------------------------------------------------------------------------
_quick_client = None


async def _quick_llm(prompt: str, max_tokens: int = 50) -> str:
    """快速调一次 LLM，用于生成用户可见的进度文案。失败返回空字符串。"""
    global _quick_client
    try:
        if _quick_client is None:
            from openai import AsyncOpenAI

            _quick_client = AsyncOpenAI(
                base_url=settings.llm.base_url,
                api_key=settings.llm.api_key,
            )
        resp = await asyncio.wait_for(
            _quick_client.chat.completions.create(
                model=settings.llm.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            ),
            timeout=10.0,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.debug("_quick_llm failed", exc_info=True)
        return ""


async def _generate_greeting(user_input: str) -> str:
    """生成个性化开场白（即时，规则匹配），作为用户看到的第一个有意义文字。"""
    keywords = {
        "海边": "🌊",
        "散步": "🚶",
        "美食": "🍜",
        "咖啡": "☕",
        "亲子": "👨‍👩‍👧",
        "约会": "💕",
        "购物": "🛍",
        "文化": "🏛",
        "公园": "🌿",
        "夜景": "🌃",
        "登山": "⛰",
        "海岛": "🏝",
        "浪漫": "💕",
        "历史": "🏛",
        "艺术": "🎨",
        "自然": "🌿",
    }
    emoji = "✈️"
    for kw, em in keywords.items():
        if kw in user_input:
            emoji = em
            break
    short = user_input[:20]
    return f"好的，让我帮你规划一次「{short}」之旅 {emoji} 正在启动智能体..."


async def _generate_progress(current_phase: str, agent_summary: str) -> str:
    """生成进度播报（~2s），告诉用户当前在干嘛。"""
    text = await _quick_llm(
        f"你是旅行规划助手。当前正在：{current_phase}。{agent_summary}\n"
        f"用简短口语（不超过30字）告诉用户你正在做什么，语气活泼。",
        max_tokens=40,
    )
    return text or f"正在{current_phase}..."


# ---------------------------------------------------------------------------
# SSE 辅助函数
# ---------------------------------------------------------------------------


async def _drain_sse_queue(
    sse_queue: asyncio.Queue, graph_task: asyncio.Task, agent_summary_ref: list[str]
):
    """从SSE队列中读取事件并yield。"""
    while not graph_task.done():
        try:
            event_type, event_data = await asyncio.wait_for(sse_queue.get(), timeout=0.3)
            yield _sse(event_type, event_data)
            if event_type == "agent_start":
                agent_summary_ref[
                    0
                ] += f"启动{event_data.get('name', event_data.get('agent', ''))}、"
            elif event_type == "agent_result":
                agent_summary_ref[0] += f"完成{event_data.get('summary', '')}、"
            await asyncio.sleep(0)
        except TimeoutError:
            pass


async def _stream_single_day_route(
    c_route: dict, c_narrative: dict, c_steps: list, user_intent: dict, c_result: dict
):
    """流式输出单日路线。"""
    if settings.debug:
        proposals = c_result.get("proposals", [])
        agent_types = list(set(p.get("agent", "?") for p in proposals))
        yield _sse(
            "debug_agents",
            {
                "version": "C",
                "agent_count": len(proposals),
                "agents": agent_types,
                "conflicts": len(c_result.get("conflicts", [])),
            },
        )

    n_steps = c_narrative.get("steps", []) if c_narrative else []
    for i, step in enumerate(c_steps):
        ns = n_steps[i] if i < len(n_steps) else {}
        yield _sse(
            "step",
            {
                "index": i + 1,
                "poi": step.get("poi", {}),
                "arrival_time": step.get("arrival_time"),
                "departure_time": step.get("departure_time"),
                "narrative": ns.get("description", "") if isinstance(ns, dict) else str(ns),
                "emotion_design": ns.get("emotion_design", "") if isinstance(ns, dict) else "",
                "scene_tags": step.get("poi", {}).get("_scene_tags", []),
            },
        )
        await asyncio.sleep(0.05)

    route_id = uuid.uuid4().hex[:8]
    yield _sse("done", {"route_id": route_id, "full_route": c_route, "version": "C-分布式智能体"})
    c_route["narrative"] = c_narrative
    c_route["user_intent"] = user_intent
    route_cache.set(route_id, c_route)
    feedback_state_cache.set(route_id, {
        "proposals": c_result.get("proposals", []),
        "expert_weights": c_result.get("expert_weights", {}),
        "active_experts": c_result.get("active_experts", []),
        "candidates": c_result.get("candidates", []),
        "scene_type": c_result.get("scene_type", "观光型"),
        "destination_name": c_result.get("destination_name", ""),
        "destination_center": c_result.get("destination_center", ()),
        "user_intent": user_intent,
        "user_input": c_result.get("user_input", ""),
    })


async def _run_agent_graph(user_input: str, sse_queue: asyncio.Queue):
    """运行智能体图并返回结果。"""
    from backend.agents_v3 import TravelState, get_graph_c

    c_graph = get_graph_c()
    c_state: TravelState = {
        "user_input": user_input,
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
        "sse_queue": sse_queue,
    }
    return await asyncio.wait_for(c_graph.ainvoke(c_state), timeout=120)


async def _run_and_drain_graph(
    sse_queue: asyncio.Queue, graph_task: asyncio.Task, agent_summary_ref: list[str]
):
    """运行图并排空SSE队列。"""
    progress_task = asyncio.create_task(
        _progress_broadcaster_agent(graph_task, agent_summary_ref, sse_queue)
    )

    async for event in _drain_sse_queue(sse_queue, graph_task, agent_summary_ref):
        yield event

    progress_task.cancel()
    with suppress(asyncio.CancelledError):
        await progress_task

    while not sse_queue.empty():
        event_type, event_data = sse_queue.get_nowait()
        yield _sse(event_type, event_data)
        await asyncio.sleep(0)


async def _progress_broadcaster_agent(
    graph_task: asyncio.Task, agent_summary_ref: list[str], sse_queue: asyncio.Queue
):
    """后台进度播报。"""
    while not graph_task.done():
        await asyncio.sleep(8.0)
        if graph_task.done():
            break
        summary = agent_summary_ref[0]
        if summary:
            agent_summary_ref[0] = ""
            try:
                progress = await _generate_progress("智能体协作规划中", summary[-80:])
                if progress:
                    await sse_queue.put(("chat", {"text": progress}))
            except Exception:
                logger.debug("进度播报失败", exc_info=True)


async def _handle_graph_result(c_result: dict):
    """处理图执行结果。"""
    user_intent = c_result.get("user_intent", {})
    c_route = c_result.get("route", {})
    c_narrative = c_result.get("narrative", {})
    c_steps = c_route.get("route", []) if c_route else []

    if c_result.get("_steps_streamed"):
        route_id = uuid.uuid4().hex[:8]
        if not c_steps:
            raise RuntimeError("C版本空路线")
        yield _sse(
            "done", {"route_id": route_id, "full_route": c_route, "version": "C-分布式智能体"}
        )
        c_route["narrative"] = c_narrative
        c_route["user_intent"] = user_intent
        route_cache.set(route_id, c_route)
        feedback_state_cache.set(route_id, {
            "proposals": c_result.get("proposals", []),
            "expert_weights": c_result.get("expert_weights", {}),
            "active_experts": c_result.get("active_experts", []),
            "candidates": c_result.get("candidates", []),
            "scene_type": c_result.get("scene_type", "观光型"),
            "destination_name": c_result.get("destination_name", ""),
            "destination_center": c_result.get("destination_center", ()),
            "user_intent": user_intent,
            "user_input": c_result.get("user_input", ""),
        })
        return

    if not c_steps:
        raise RuntimeError("C版本空路线")

    async for event in _stream_single_day_route(
        c_route, c_narrative, c_steps, user_intent, c_result
    ):
        yield event


# ---------------------------------------------------------------------------
# 路线调整辅助
# ---------------------------------------------------------------------------


def _deep_copy_route(route: dict) -> dict:
    """深拷贝路线数据（用于保存调整前快照）。"""
    return copy.deepcopy(route)


def _generate_changes_summary(previous_route: dict, new_route: dict, changes_made: list) -> str:
    """生成变更摘要。"""
    summaries = []
    for change in changes_made:
        change_type = change.get("type", "")
        if change_type == "replace":
            old_name = change.get("original", change.get("old_poi", {}).get("name", "未知"))
            new_name = change.get("replacement", change.get("new_poi", {}).get("name", "未知"))
            summaries.append(f"已将 {old_name} 替换为 {new_name}")
        elif change_type == "pace":
            new_pace = change.get("new_pace", "")
            summaries.append(f"节奏已调整为 {new_pace}")
        elif change_type == "budget":
            new_budget = change.get("new_budget", 0)
            summaries.append(f"预算已调整为每人{new_budget}元")
        elif change_type == "time":
            new_start = change.get("new_start", "")
            summaries.append(f"出发时间已调整为 {new_start}")
        elif change_type == "mood_adjust":
            emotion_need = change.get("emotion_need", "")
            summaries.append(f"已调整为{emotion_need}型路线")
        elif change_type == "emotion_weight":
            summaries.append("已调整路线强度")
        elif change_type == "retry":
            summaries.append("路线已重新规划")

    return "；".join(summaries) if summaries else "路线已调整"


def _get_all_steps_from_route(route: dict) -> list:
    """从路线中提取所有步骤（兼容单日/多日）。"""
    if "days" in route:
        steps = []
        for day in route["days"]:
            steps.extend(day.get("route", {}).get("route", []))
        return steps
    return route.get("route", [])


# ---------------------------------------------------------------------------
# 路由：POST /api/plan
# ---------------------------------------------------------------------------


@router.post(
    "/api/plan",
    summary="流式规划路线",
    description=(
        "根据用户自然语言描述，以SSE（Server-Sent Events）流式返回规划结果。\n\n"
        "## 处理流程\n\n"
        "1. **解析意图** (`phase: parsing`) - 理解用户需求，匹配用户画像\n"
        "2. **搜索候选** (`phase: searching`) - 根据意图筛选合适POI\n"
        "3. **求解路线** (`phase: solving`) - TSPTW算法优化路线顺序与时间\n"
        "4. **生成文案** (`phase: narrating`) - 为每个站点生成描述文案\n"
        "5. **逐步返回** (`step`) - 逐个返回路线步骤\n"
        "6. **完成** (`done`) - 返回路线ID和完整数据\n\n"
        "## SSE 事件类型\n\n"
        "| 事件 | data 字段 | 说明 |\n"
        "|------|-----------|------|\n"
        "| `phase` | `{phase, message}` | 当前处理阶段 |\n"
        "| `step` | `{index, poi, arrival_time, departure_time, narrative}` | 单个路线步骤 |\n"
        "| `done` | `{route_id, full_route}` | 规划完成，route_id 可用于后续对话 |\n"
        "| `error` | `{error}` | 错误信息 |"
    ),
    tags=["路线规划"],
)
async def plan_route(request: PlanRequest):
    """流式规划路线。"""

    async def event_stream():
        acquired = False
        try:
            acquired = _plan_semaphore.locked() is False
            if not acquired:
                if _plan_semaphore._value <= 0:  # type: ignore[attr-defined]
                    yield _sse("error", {"error": "服务繁忙，请稍后再试"})
                    return
            async with _plan_semaphore:
                acquired = True
                greeting = await _generate_greeting(request.user_input)
                yield _sse("chat", {"text": greeting})
                yield _sse("phase", {"phase": "parsing", "message": "正在理解你的需求..."})

                try:
                    yield _sse("phase", {"phase": "agents", "message": "7个智能体正在并行规划..."})

                    user_input = request.user_input
                    if request.start_location:
                        user_input = f"从{request.start_location}出发，{user_input}"

                    sse_queue: asyncio.Queue = asyncio.Queue()
                    graph_task = asyncio.create_task(_run_agent_graph(user_input, sse_queue))
                    _agent_summary_ref = [""]

                    async for event in _run_and_drain_graph(sse_queue, graph_task, _agent_summary_ref):
                        yield event

                    c_result = await graph_task
                    async for event in _handle_graph_result(c_result):
                        yield event

                except Exception as c_err:
                    logger.error("C版本执行失败: %s", c_err)
                    yield _sse("error", {"error": "路线规划失败，请重试"})
                    return

        except Exception:
            logger.exception("规划路线时出错")
            yield _sse("error", {"error": "服务器内部错误，请稍后重试"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# 路由：GET /api/route/{route_id}
# ---------------------------------------------------------------------------


@router.get(
    "/api/route/{route_id}",
    summary="获取路线详情",
    description="根据路线ID获取已规划路线的完整数据。",
    tags=["路线管理"],
)
async def get_route(route_id: str):
    """获取已规划路线的完整数据。"""
    route_data = route_cache.get(route_id)
    if route_data is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="Route not found",
            details={"route_id": route_id},
        )
    return route_data


# ---------------------------------------------------------------------------
# 路由：GET /api/route/{route_id}/adjust
# ---------------------------------------------------------------------------


@router.get(
    "/api/route/{route_id}/adjust",
    summary="通过指令调整路线（SSE 流式）",
    description=(
        "通过GET请求的query参数传入指令来调整已规划的路线。\n\n"
        "以 SSE 流式返回调整进度和结果。"
    ),
    tags=["对话"],
)
async def adjust_route(route_id: str, instruction: str):
    """通过对话指令调整路线（SSE 流式）。"""
    route = route_cache.get(route_id)
    if route is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="Route not found",
            details={"route_id": route_id},
        )
    user_intent = route.get("user_intent", {})

    from backend.services.feedback_adjust import run_feedback_adjust, rebuild_minimal_state

    cached_state = feedback_state_cache.get(route_id)
    if cached_state is None:
        logger.warning("[adjust] route %s 无中间状态，降级重建", route_id)
        cached_state = await rebuild_minimal_state(route)

    previous_route = _deep_copy_route(route)

    async def adjust_stream():
        yield _sse("phase", {"message": "正在分析调整指令..."})

        result_holder: dict = {}
        error_holder: dict = {}

        async def _run_adjust():
            try:
                result_holder["result"] = await run_feedback_adjust(
                    route_id, instruction, route, cached_state,
                )
            except Exception as exc:
                error_holder["error"] = exc

        adjust_task = asyncio.create_task(_run_adjust())

        elapsed = 0
        while not adjust_task.done():
            await asyncio.sleep(5)
            elapsed += 5
            yield _sse("phase", {"message": f"正在重新规划路线...（已耗时 {elapsed}s）"})

        await adjust_task

        if "error" in error_holder:
            logger.error("[adjust] feedback graph 失败: %s", error_holder["error"])
            yield _sse("error", {"error": "路线调整失败，请重试"})
            return

        result = result_holder["result"]

        if result.get("changes_made"):
            result["previous_route"] = previous_route
            result["route_id"] = route_id
            result["changes_summary"] = _generate_changes_summary(
                previous_route, result.get("route", {}), result["changes_made"]
            )

        if result.get("changes_made") and user_intent.get("_user_id"):
            try:
                from backend.services.preference_manager import PreferenceManager

                pref_mgr = PreferenceManager.from_user_id(user_intent["_user_id"])
                await pref_mgr._ensure_init()
                await pref_mgr.record_feedback(
                    demand_vector=user_intent.get("_demand_vector", {}),
                    applied_weights=user_intent.get("_dynamic_weights", {}),
                    feedback="modified",
                    modification_hint=instruction,
                )
            except Exception as fb_err:
                logger.warning("反馈记录失败（不影响主流程）: %s", fb_err)

        yield _sse("result", result)
        yield _sse("done", {})

    return StreamingResponse(
        adjust_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# 路由：POST /api/dialogue/{session_id}
# ---------------------------------------------------------------------------


@router.post(
    "/api/dialogue/{session_id}",
    summary="对话式路线调整",
    description="通过多轮对话对已规划路线进行调整。",
    tags=["对话"],
)
async def dialogue(session_id: str, request: AdjustRequest):
    """对话式路线调整。"""
    route = route_cache.get(session_id)
    if route is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="Session route not found",
            details={"session_id": session_id},
        )
    user_intent = route.get("user_intent", {})

    from backend.services.feedback_adjust import run_feedback_adjust, rebuild_minimal_state

    cached_state = feedback_state_cache.get(session_id)
    if cached_state is None:
        cached_state = await rebuild_minimal_state(route)

    result = await run_feedback_adjust(
        session_id, request.instruction, route, cached_state,
    )

    if result.get("changes_made") and user_intent.get("_user_id"):
        try:
            from backend.services.preference_manager import PreferenceManager

            pref_mgr = PreferenceManager.from_user_id(user_intent["_user_id"])
            await pref_mgr._ensure_init()
            await pref_mgr.record_feedback(
                demand_vector=user_intent.get("_demand_vector", {}),
                applied_weights=user_intent.get("_dynamic_weights", {}),
                feedback="modified",
                modification_hint=request.instruction,
            )
        except Exception as fb_err:
            logger.warning("反馈记录失败（不影响主流程）: %s", fb_err)

    return result


# ---------------------------------------------------------------------------
# 路由：GET /api/health
# ---------------------------------------------------------------------------


@router.get(
    "/api/health",
    summary="健康检查",
    description="返回服务运行状态，可用于负载均衡器探活。",
    response_model=HealthResponse,
    tags=["系统"],
)
async def health():
    """健康检查接口。"""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 路由：GET /api/cache/stats
# ---------------------------------------------------------------------------


@router.get(
    "/api/cache/stats",
    summary="缓存统计",
    description="返回各缓存实例的命中率和使用情况。",
    tags=["系统"],
)
async def cache_stats():
    """返回缓存命中率统计。"""
    ml_cache = get_multilevel_cache()
    return {
        "l1_caches": {
            "route_cache": route_cache.stats,
            "distance_cache": distance_cache.stats,
            "poi_cache": poi_cache.stats,
            "profile_cache": profile_cache.stats,
            "general_cache": general_cache.stats,
        },
        "multilevel_cache": ml_cache.stats,
    }
