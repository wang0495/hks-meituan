"""CityFlow GraphQL Resolvers -- 调用已有服务层实现查询与变更。

每个 resolver 对应 schema.py 中的一个字段，内部调用
backend.services 下的 data_service / intent_parser / solver / narrator / dialogue。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.graphql.schema import (
    POI,
    ChangeRecord,
    DialogueResponse,
    EmotionTags,
    NarrativeStep,
    POIConstraints,
    Route,
    RouteStep,
    TotalCost,
    TravelInfo,
)
from backend.services.cache import route_cache
from backend.utils.sse_helpers import with_timeout as _with_timeout

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部转换：dict -> Strawberry type
# ---------------------------------------------------------------------------


def _to_emotion_tags(raw: dict[str, Any] | None) -> EmotionTags | None:
    if not raw:
        return None
    return EmotionTags(
        excitement=raw.get("excitement", 0.0),
        tranquility=raw.get("tranquility", 0.0),
        sociability=raw.get("sociability", 0.0),
        culture_depth=raw.get("culture_depth", 0.0),
        surprise=raw.get("surprise", 0.0),
        physical_demand=raw.get("physical_demand", 0.0),
    )


def _to_constraints(raw: dict[str, Any] | None) -> POIConstraints | None:
    if not raw:
        return None
    return POIConstraints(
        accessible=raw.get("accessible", True),
        pet_friendly=raw.get("pet_friendly", False),
        queue_time_min=raw.get("queue_time_min", 0),
        opening_hours=raw.get("opening_hours", "09:00-17:00"),
        has_restroom=raw.get("has_restroom", True),
    )


def _to_poi(raw: dict[str, Any]) -> POI:
    return POI(
        id=str(raw.get("id", "")),
        name=raw.get("name", ""),
        category=raw.get("category", ""),
        city=raw.get("city", ""),
        rating=float(raw.get("rating", 0)),
        avg_price=float(raw.get("avg_price", 0)),
        avg_stay_min=int(raw.get("avg_stay_min", 60)),
        lat=float(raw.get("lat", 0)),
        lng=float(raw.get("lng", 0)),
        business_hours=raw.get("business_hours", "09:00-17:00"),
        tags=raw.get("tags", []),
        emotion_tags=_to_emotion_tags(raw.get("emotion_tags")),
        constraints=_to_constraints(raw.get("constraints")),
        price_range=raw.get("price_range"),
    )


def _to_travel_info(raw: dict[str, Any] | None) -> TravelInfo | None:
    if not raw:
        return None
    return TravelInfo(
        distance_m=int(raw.get("distance_m", 0)),
        time_min=int(raw.get("time_min", 0)),
    )


def _to_route_step(raw: dict[str, Any]) -> RouteStep:
    return RouteStep(
        poi=_to_poi(raw["poi"]),
        arrival_time=raw.get("arrival_time", ""),
        departure_time=raw.get("departure_time", ""),
        travel_from_prev=_to_travel_info(raw.get("travel_from_prev")),
    )


def _to_narrative(raw: dict[str, Any] | None) -> NarrativeStep | None:
    if not raw:
        return None
    highlights = raw.get("emotion_highlights", [])
    # emotion_highlights 可能是 list[dict]，序列化为 JSON 字符串方便前端处理
    highlight_strs = [str(h) for h in highlights]
    return NarrativeStep(
        opening=raw.get("opening", ""),
        steps=raw.get("steps", []),
        closing=raw.get("closing", ""),
        emotion_highlights=highlight_strs,
    )


def _to_total_cost(raw: dict[str, Any] | None) -> TotalCost | None:
    if not raw:
        return None
    return TotalCost(
        time_min=int(raw.get("time_min", 0)),
        budget_used=float(raw.get("budget_used", 0)),
        step_estimate=int(raw.get("step_estimate", 0)),
    )


def _to_route(route_id: str, raw: dict[str, Any], user_input: str = "") -> Route:
    steps_raw = raw.get("route", [])
    return Route(
        route_id=route_id,
        user_input=user_input or raw.get("user_input", ""),
        steps=[_to_route_step(s) for s in steps_raw],
        narrative=_to_narrative(raw.get("narrative")),
        total_cost=_to_total_cost(raw.get("total_cost")),
        emotion_curve=[str(c) for c in raw.get("emotion_curve", [])],
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# POI resolvers
# ---------------------------------------------------------------------------


async def resolve_pois(
    region: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> list[POI]:
    """查询 POI 列表。"""
    from backend.services.data_service import get_data

    pois_raw: list[dict[str, Any]] = get_data("city_poi_db")

    if region:
        pois_raw = [p for p in pois_raw if p.get("city") == region]

    if category:
        pois_raw = [p for p in pois_raw if p.get("category") == category]

    return [_to_poi(p) for p in pois_raw[:limit]]


async def resolve_poi(id: str) -> POI | None:
    """查询单个 POI。"""
    from backend.services.data_service import get_data

    pois_raw: list[dict[str, Any]] = get_data("city_poi_db")
    match = next((p for p in pois_raw if str(p.get("id")) == id), None)
    return _to_poi(match) if match else None


# ---------------------------------------------------------------------------
# Route resolvers
# ---------------------------------------------------------------------------


async def resolve_routes(limit: int = 10) -> list[Route]:
    """查询已缓存的路线列表（脱敏：不暴露其他用户的输入/意图）。"""
    results: list[Route] = []
    for key, (raw, *_ts) in list(route_cache._cache.items())[:limit]:
        results.append(_to_route(route_id=key, raw=raw, user_input=""))  # 不暴露原始输入
    return results


async def resolve_route(id: str) -> Route | None:
    """查询单条已缓存路线。"""
    raw = route_cache.get(id)
    if raw is None:
        return None
    return _to_route(route_id=id, raw=raw, user_input=raw.get("user_input", ""))


# ---------------------------------------------------------------------------
# Mutation resolvers
# ---------------------------------------------------------------------------


async def resolve_plan_route(user_input: str) -> Route:
    """规划路线 -- 调用 intent_parser -> filters -> solver -> narrator 完整流程。"""
    from backend.services.data_service import get_data
    from backend.services.filters import filter_candidates
    from backend.services.intent_parser import parse_intent
    from backend.services.narrator import generate_narrative
    from backend.services.solver import solve_route

    # 1. 解析意图
    user_intent = await _with_timeout(
        parse_intent(user_input),
        timeout_seconds=8.0,
    )
    if user_intent is None:
        raise ValueError("意图解析超时，请重试")

    # 2. 筛选候选
    all_pois = get_data("city_poi_db")
    candidates = filter_candidates(all_pois, user_intent)
    if not candidates:
        raise ValueError("没有找到符合条件的地点，请放宽条件重试")

    # 3. 求解路线
    start_time = user_intent.get("time", {}).get("start", "09:00")
    route_result = await _with_timeout(
        asyncio.to_thread(solve_route, candidates, user_intent, start_time),
        timeout_seconds=10.0,
    )
    if route_result is None or not route_result.get("route"):
        # 兜底：取评分最高的 3 个
        sorted_pois = sorted(candidates, key=lambda p: p.get("rating", 0), reverse=True)[:3]
        route_result = {
            "route": [
                {
                    "poi": poi,
                    "arrival_time": f"{9 + i}:00",
                    "departure_time": f"{10 + i}:00",
                    "travel_from_prev": {"distance_m": 0, "time_min": 0},
                }
                for i, poi in enumerate(sorted_pois)
            ],
            "emotion_curve": [],
            "total_cost": {"time_min": 180, "budget_used": 0, "step_estimate": 3000},
        }

    # 4. 生成文案
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
    route_result["narrative"] = narrative
    route_result["user_intent"] = user_intent

    # 5. 缓存并返回
    route_id = uuid.uuid4().hex[:8]
    route_cache.set(route_id, route_result)

    return _to_route(route_id=route_id, raw=route_result, user_input=user_input)


async def resolve_adjust_route(route_id: str, instruction: str) -> DialogueResponse:
    """调整路线 -- 调用 dialogue engine。"""
    from backend.services.dialogue import dialogue_engine

    # 检查路线是否存在
    route_data = route_cache.get(route_id)
    if route_data is None:
        raise ValueError(f"路线 {route_id} 不存在")

    user_intent = route_data.get("user_intent", {})

    # 确保有对话会话
    session = dialogue_engine.get_session(route_id)
    if not session:
        dialogue_engine.create_session(route_id, route_data, user_intent)

    result = await dialogue_engine.process_instruction(route_id, instruction)

    # 更新缓存
    updated_route = result.get("route", route_data)
    route_cache.set(route_id, updated_route)

    # 构造响应
    changes = [
        ChangeRecord(type=c.get("type", ""), detail=str(c)) for c in result.get("changes_made", [])
    ]

    return DialogueResponse(
        reply=result.get("reply", ""),
        route=_to_route(route_id=route_id, raw=updated_route, user_input=""),
        changes_made=changes,
    )
