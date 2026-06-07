"""V2 路线规划接口（增强版）。"""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.services.cache import route_cache
from backend.services.data_service import get_data
from backend.utils.sse_helpers import (
    generate_simplified_route as _generate_simplified_route,
)
from backend.utils.sse_helpers import (
    sse as _sse,
)
from backend.utils.sse_helpers import (
    with_timeout as _with_timeout,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v2-plan"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class PlanRequestV2(BaseModel):
    """V2 路线规划请求（增强版，支持约束和节奏）。"""

    user_input: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="用户出行需求的自然语言描述",
        examples=["周末想一个人安静走走"],
    )
    preferences: dict | None = Field(
        None,
        description="偏好设置，如 {culture: 0.8, food: 0.6}",
    )
    constraints: list[str] | None = Field(
        None,
        description="约束条件列表，如 ['文化深度', '无障碍通行']",
        examples=[["文化深度", "无障碍通行"]],
    )
    pace: str | None = Field(
        "平衡型",
        description="节奏模式：闲逛型 / 平衡型 / 特种兵型",
        examples=["平衡型"],
    )
    city: str | None = Field(
        None,
        description="目标城市，如 '珠海'、'广州'、'深圳'",
        examples=["珠海"],
    )
    start_point: dict | None = Field(
        None,
        description="起点位置，坐标 {lat, lng} 或地名字符串",
        examples=[{"lat": 22.270, "lng": 113.543}],
    )
    end_point: dict | None = Field(
        None,
        description="终点位置，坐标 {lat, lng} 或地名字符串",
        examples=[{"lat": 22.217, "lng": 113.553}],
    )


class EmotionCurvePoint(BaseModel):
    """情绪曲线数据点。"""

    poi_id: str = Field(..., description="POI ID")
    poi_name: str = Field(..., description="POI名称")
    excitement: float = Field(..., ge=0, le=1, description="兴奋度")
    tranquility: float = Field(..., ge=0, le=1, description="宁静度")
    sociability: float = Field(..., ge=0, le=1, description="社交性")
    culture_depth: float = Field(..., ge=0, le=1, description="文化深度")
    surprise: float = Field(..., ge=0, le=1, description="惊喜度")


class RouteMetadata(BaseModel):
    """路线元数据。"""

    total_distance_m: int = Field(0, ge=0, description="总距离（米）")
    total_time_min: int = Field(0, ge=0, description="总时长（分钟）")
    estimated_budget: float = Field(0, ge=0, description="预估预算（元）")
    poi_count: int = Field(0, ge=0, description="POI数量")
    pace: str = Field("平衡型", description="节奏模式")
    constraints_applied: list[str] = Field(default_factory=list, description="已应用的约束条件")


class PlanResponseV2(BaseModel):
    """V2 路线规划响应（增强版，包含情绪曲线和元数据）。"""

    route_id: str = Field(..., description="路线ID")
    route: list[dict] = Field(default_factory=list, description="路线步骤列表")
    narrative: dict = Field(default_factory=dict, description="路线文案")
    emotion_curve: list[dict] = Field(default_factory=list, description="情绪曲线数据")
    metadata: dict = Field(default_factory=dict, description="路线元数据")


# ---------------------------------------------------------------------------
# 辅助函数 — _with_timeout / _generate_simplified_route / _sse 从 sse_helpers 导入
# ---------------------------------------------------------------------------


def _build_emotion_curve(route_result: dict) -> list[dict]:
    """从路线结果构建情绪曲线。"""
    curve = []
    for step in route_result.get("route", []):
        poi = step.get("poi", {})
        emotion = poi.get("emotion_tags", {})
        curve.append(
            {
                "poi_id": poi.get("id", ""),
                "poi_name": poi.get("name", ""),
                "excitement": emotion.get("excitement", 0.5),
                "tranquility": emotion.get("tranquility", 0.5),
                "sociability": emotion.get("sociability", 0.5),
                "culture_depth": emotion.get("culture_depth", 0.5),
                "surprise": emotion.get("surprise", 0.5),
            }
        )
    return curve


def _build_metadata(route_result: dict, request: PlanRequestV2) -> dict:
    """构建路线元数据。"""
    total_distance = 0
    total_time = 0
    estimated_budget = 0.0
    steps = route_result.get("route", [])

    for step in steps:
        travel = step.get("travel_from_prev", {})
        if travel:
            total_distance += travel.get("distance_m", 0)
            total_time += travel.get("time_min", 0)
        poi = step.get("poi", {})
        estimated_budget += poi.get("avg_price", 0)
        total_time += poi.get("avg_stay_min", 60)

    # 计算实际POI数量（排除起终点）
    poi_count = sum(1 for s in steps if not s.get("poi", {}).get("_is_point", False))

    metadata = {
        "total_distance_m": total_distance,
        "total_time_min": total_time,
        "estimated_budget": estimated_budget,
        "poi_count": poi_count,
        "pace": request.pace or "平衡型",
        "constraints_applied": request.constraints or [],
    }

    # 添加城市信息
    if request.city:
        metadata["city"] = request.city

    # 添加起终点信息
    if request.start_point:
        metadata["start_point"] = request.start_point
    if request.end_point:
        metadata["end_point"] = request.end_point

    return metadata


# ---------------------------------------------------------------------------
# API 实现
# ---------------------------------------------------------------------------


def _merge_v2_request_params(user_intent: dict, request: PlanRequestV2) -> None:
    """合并V2请求参数到user_intent。"""
    if request.constraints:
        user_intent.setdefault("constraints", []).extend(request.constraints)
    if request.pace:
        user_intent["pace"] = request.pace
    if request.preferences:
        user_intent.setdefault("preferences", {}).update(request.preferences)
    if request.city:
        user_intent["city"] = request.city
    if request.start_point:
        user_intent["start_point"] = request.start_point
    if request.end_point:
        user_intent["end_point"] = request.end_point


async def _v2_event_stream(request: PlanRequestV2):
    """V2路线规划SSE事件流。"""
    try:
        yield _sse("phase", {"phase": "parsing", "message": "正在理解你的需求..."})

        from backend.services.intent_parser import parse_intent

        user_intent = await _with_timeout(parse_intent(request.user_input), timeout_seconds=8.0)
        if user_intent is None:
            yield _sse("error", {"error": "意图解析超时，请重试"})
            return

        _merge_v2_request_params(user_intent, request)

        yield _sse("phase", {"phase": "searching", "message": "正在为你寻找合适的地方..."})

        from backend.services.filters import filter_candidates

        city = request.city or user_intent.get("city", "珠海")
        candidates = filter_candidates(get_data("city_poi_db", city=city), user_intent)
        if not candidates:
            yield _sse("error", {"error": "没有找到符合条件的地点，请放宽条件重试"})
            return

        yield _sse("phase", {"phase": "solving", "message": "正在编排最佳路线..."})

        from backend.services.solver import solve_route

        route_result = await _with_timeout(
            asyncio.to_thread(
                solve_route,
                candidates,
                user_intent,
                user_intent.get("time", {}).get("start", "09:00"),
                start_point=request.start_point,
                end_point=request.end_point,
            ),
            timeout_seconds=10.0,
        )
        if route_result is None or not route_result.get("route"):
            logger.warning("路线求解失败/超时，使用简化路线")
            route_result = _generate_simplified_route(candidates)

        yield _sse("phase", {"phase": "narrating", "message": "正在为你写一段行程说明..."})

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

        for i, step in enumerate(route_result.get("route", [])):
            yield _sse(
                "step",
                {
                    "index": i + 1,
                    "poi": step["poi"],
                    "arrival_time": step.get("arrival_time"),
                    "departure_time": step.get("departure_time"),
                    "narrative": (
                        narrative.get("steps", [])[i] if i < len(narrative.get("steps", [])) else ""
                    ),
                },
            )
            await asyncio.sleep(0.05)

        route_id = uuid.uuid4().hex[:8]
        route_result["narrative"] = narrative
        route_result["user_intent"] = user_intent
        route_cache.set(route_id, route_result)

        yield _sse(
            "done",
            {
                "route_id": route_id,
                "full_route": route_result,
                "emotion_curve": _build_emotion_curve(route_result),
                "metadata": _build_metadata(route_result, request),
            },
        )

    except Exception:
        logger.exception("V2 规划路线时出错")
        yield _sse("error", {"error": "服务器内部错误，请稍后重试"})


@router.post(
    "/plan",
    summary="[V2] 流式规划路线（增强版）",
    description=(
        "V2版本的路线规划接口，增加了约束条件、节奏模式和情绪曲线支持。\n\n"
        "相比V1新增功能：\n"
        "- **constraints** - 支持传入约束条件（如'文化深度'、'无障碍通行'）\n"
        "- **pace** - 支持指定节奏模式（闲逛型/平衡型/特种兵型）\n"
        "- **emotion_curve** - 返回完整的情绪曲线数据\n"
        "- **metadata** - 返回路线元数据（总距离、时长、预算等）"
    ),
    tags=["v2-plan"],
)
async def plan_route_v2(request: PlanRequestV2) -> StreamingResponse:
    """V2版本的路线规划（SSE流式响应，增强版）。"""
    return StreamingResponse(
        _v2_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
