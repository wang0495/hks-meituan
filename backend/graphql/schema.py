"""CityFlow GraphQL Schema -- Strawberry 类型定义。

所有类型与 backend/main.py 中的 Pydantic 响应模型保持一致。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import strawberry

# ---------------------------------------------------------------------------
# 标量类型
# ---------------------------------------------------------------------------


@strawberry.type
class EmotionTags:
    """POI 情绪标签（6维，取值 0~1）。"""

    excitement: float
    tranquility: float
    sociability: float
    culture_depth: float
    surprise: float
    physical_demand: float


@strawberry.type
class POIConstraints:
    """POI 约束条件。"""

    accessible: bool = True
    pet_friendly: bool = False
    queue_time_min: int = 0
    opening_hours: str = "09:00-17:00"
    has_restroom: bool = True


@strawberry.type
class TravelInfo:
    """交通信息。"""

    distance_m: int
    time_min: int


# ---------------------------------------------------------------------------
# POI
# ---------------------------------------------------------------------------


@strawberry.type
class POI:
    """兴趣点。"""

    id: str
    name: str
    category: str
    city: str
    rating: float
    avg_price: float
    avg_stay_min: int = 60
    lat: float
    lng: float
    business_hours: str = "09:00-17:00"
    tags: list[str] = strawberry.field(default_factory=list)
    emotion_tags: Optional[EmotionTags] = None
    constraints: Optional[POIConstraints] = None
    price_range: Optional[str] = None


# ---------------------------------------------------------------------------
# 路线
# ---------------------------------------------------------------------------


@strawberry.type
class RouteStep:
    """路线中的单个步骤。"""

    poi: POI
    arrival_time: str
    departure_time: str
    travel_from_prev: Optional[TravelInfo] = None


@strawberry.type
class NarrativeStep:
    """路线文案。"""

    opening: str = ""
    steps: list[str] = strawberry.field(default_factory=list)
    closing: str = ""
    emotion_highlights: list[str] = strawberry.field(default_factory=list)


@strawberry.type
class TotalCost:
    """费用估算。"""

    time_min: int
    budget_used: float
    step_estimate: int


@strawberry.type
class Route:
    """完整路线规划结果。"""

    route_id: str
    user_input: str
    steps: list[RouteStep]
    narrative: Optional[NarrativeStep] = None
    total_cost: Optional[TotalCost] = None
    emotion_curve: list[str] = strawberry.field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# 对话
# ---------------------------------------------------------------------------


@strawberry.type
class ChangeRecord:
    """对话调整的变更记录。"""

    type: str
    detail: str = ""


@strawberry.type
class DialogueResponse:
    """对话调整的响应。"""

    reply: str
    route: Route
    changes_made: list[ChangeRecord] = strawberry.field(default_factory=list)


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------


@strawberry.type
class Query:
    @strawberry.field(description="查询 POI 列表，支持按城市和类别筛选")
    async def pois(
        self,
        region: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[POI]:
        from backend.graphql.resolvers import resolve_pois

        return await resolve_pois(region=region, category=category, limit=limit)

    @strawberry.field(description="查询单个 POI")
    async def poi(self, id: str) -> Optional[POI]:
        from backend.graphql.resolvers import resolve_poi

        return await resolve_poi(id=id)

    @strawberry.field(description="查询路线列表")
    async def routes(self, limit: int = 10) -> list[Route]:
        from backend.graphql.resolvers import resolve_routes

        return await resolve_routes(limit=limit)

    @strawberry.field(description="查询单条路线")
    async def route(self, id: str) -> Optional[Route]:
        from backend.graphql.resolvers import resolve_route

        return await resolve_route(id=id)


# ---------------------------------------------------------------------------
# 变更
# ---------------------------------------------------------------------------


@strawberry.type
class Mutation:
    @strawberry.mutation(description="根据自然语言描述规划路线")
    async def plan_route(self, user_input: str) -> Route:
        from backend.graphql.resolvers import resolve_plan_route

        return await resolve_plan_route(user_input=user_input)

    @strawberry.mutation(description="通过对话指令调整已规划路线")
    async def adjust_route(self, route_id: str, instruction: str) -> DialogueResponse:
        from backend.graphql.resolvers import resolve_adjust_route

        return await resolve_adjust_route(route_id=route_id, instruction=instruction)


# ---------------------------------------------------------------------------
# Schema 实例
# ---------------------------------------------------------------------------

schema = strawberry.Schema(query=Query, mutation=Mutation)
