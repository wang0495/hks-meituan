"""V1 路线规划接口。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.services.cache import route_cache
from backend.services.data_service import get_data

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1-plan"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class PlanRequestV1(BaseModel):
    """V1 路线规划请求。"""

    user_input: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="用户出行需求的自然语言描述",
        examples=["周末想一个人安静走走"],
    )


class PlanResponseV1(BaseModel):
    """V1 路线规划响应。"""

    route_id: str = Field(..., description="路线ID")
    route: list[dict] = Field(default_factory=list, description="路线步骤列表")
    narrative: dict = Field(default_factory=dict, description="路线文案")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _with_timeout(coro, timeout_seconds: float = 12.0, fallback=None):
    """给协程加超时，超时返回 fallback。"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning("操作超时 (%.1fs)，使用兜底", timeout_seconds)
        return fallback


def _generate_simplified_route(
    pois: list[dict[str, Any]], count: int = 3
) -> dict[str, Any]:
    """生成简化路线（兜底方案）。"""
    sorted_pois = sorted(pois, key=lambda p: p.get("rating", 0), reverse=True)[:count]
    return {
        "route": [
            {
                "poi": poi,
                "arrival_time": f"{9 + i}:00",
                "departure_time": f"{10 + i}:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            }
            for i, poi in enumerate(sorted_pois)
        ],
        "narrative": {"opening": "", "steps": [""] * len(sorted_pois), "closing": ""},
    }


def _sse(event: str, data_obj: Any) -> str:
    """构造一条 SSE 消息。"""
    return f"event: {event}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# API 实现
# ---------------------------------------------------------------------------


@router.post(
    "/plan",
    summary="[V1] 流式规划路线",
    description="V1版本的路线规划接口，以SSE流式返回结果。",
    tags=["v1-plan"],
)
async def plan_route_v1(request: PlanRequestV1):
    """V1版本的路线规划（SSE流式响应）。"""

    async def event_stream():
        try:
            yield _sse("phase", {"phase": "parsing", "message": "正在理解你的需求..."})

            from backend.services.intent_parser import parse_intent
            from backend.services.user_profiles import USER_PROFILES

            user_intent = await _with_timeout(
                parse_intent(request.user_input, USER_PROFILES),
                timeout_seconds=8.0,
            )
            if user_intent is None:
                yield _sse("error", {"error": "意图解析超时，请重试"})
                return

            yield _sse(
                "phase", {"phase": "searching", "message": "正在为你寻找合适的地方..."}
            )

            from backend.services.filters import filter_candidates

            all_pois = get_data("city_poi_db")
            candidates = filter_candidates(all_pois, user_intent)

            if not candidates:
                yield _sse("error", {"error": "没有找到符合条件的地点，请放宽条件重试"})
                return

            yield _sse("phase", {"phase": "solving", "message": "正在编排最佳路线..."})

            from backend.services.solver import solve_route

            start_time = user_intent.get("time", {}).get("start", "09:00")
            route_result = await _with_timeout(
                asyncio.to_thread(solve_route, candidates, user_intent, start_time),
                timeout_seconds=10.0,
            )

            if route_result is None or not route_result.get("route"):
                logger.warning("路线求解失败/超时，使用简化路线")
                route_result = _generate_simplified_route(candidates)

            yield _sse(
                "phase", {"phase": "narrating", "message": "正在为你写一段行程说明..."}
            )

            from backend.services.narrator import generate_narrative

            narrative = await _with_timeout(
                generate_narrative(route_result, user_intent),
                timeout_seconds=5.0,
                fallback={
                    "opening": "",
                    "steps": [""] * len(route_result.get("route", [])),
                    "closing": "",
                    "emotion_highlights": [],
                },
            )

            steps_list = route_result.get("route", [])
            narrative_steps = narrative.get("steps", [])
            for i, step in enumerate(steps_list):
                step_data = {
                    "index": i + 1,
                    "poi": step["poi"],
                    "arrival_time": step.get("arrival_time"),
                    "departure_time": step.get("departure_time"),
                    "narrative": narrative_steps[i] if i < len(narrative_steps) else "",
                }
                yield _sse("step", step_data)
                await asyncio.sleep(0.05)

            route_id = uuid.uuid4().hex[:8]
            route_result["narrative"] = narrative
            route_result["user_intent"] = user_intent
            route_cache.set(route_id, route_result)

            yield _sse(
                "done",
                {"route_id": route_id, "full_route": route_result},
            )

        except Exception:
            logger.exception("V1 规划路线时出错")
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
