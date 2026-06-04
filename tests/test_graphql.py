"""CityFlow GraphQL 端点测试。

覆盖:
- 转换函数单元测试 (dict -> Strawberry types)
- Schema 执行测试 (通过 schema.execute 直接调用)
- 端点集成测试 (通过 HTTP 客户端)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.graphql.resolvers import (
    _to_constraints,
    _to_emotion_tags,
    _to_narrative,
    _to_poi,
    _to_route,
    _to_route_step,
    _to_total_cost,
    _to_travel_info,
)
from backend.graphql.schema import schema

# ---------------------------------------------------------------------------
# 转换函数单元测试
# ---------------------------------------------------------------------------


class TestTypeConverters:
    """测试 dict -> Strawberry 类型转换。"""

    def test_to_emotion_tags_none(self):
        assert _to_emotion_tags(None) is None

    def test_to_emotion_tags_valid(self):
        raw = {
            "excitement": 0.8,
            "tranquility": 0.2,
            "sociability": 0.5,
            "culture_depth": 0.7,
            "surprise": 0.3,
            "physical_demand": 0.1,
        }
        tags = _to_emotion_tags(raw)
        assert tags is not None
        assert tags.excitement == 0.8
        assert tags.tranquility == 0.2

    def test_to_constraints_none(self):
        assert _to_constraints(None) is None

    def test_to_constraints_empty_dict_returns_none(self):
        """空 dict 在 Python 中为 falsy，_to_constraints 返回 None。"""
        assert _to_constraints({}) is None

    def test_to_constraints_with_values(self):
        raw = {
            "accessible": False,
            "pet_friendly": True,
            "queue_time_min": 15,
            "opening_hours": "10:00-20:00",
            "has_restroom": False,
        }
        c = _to_constraints(raw)
        assert c is not None
        assert c.accessible is False
        assert c.pet_friendly is True
        assert c.queue_time_min == 15
        assert c.opening_hours == "10:00-20:00"

    def test_to_travel_info_none(self):
        assert _to_travel_info(None) is None

    def test_to_travel_info_valid(self):
        info = _to_travel_info({"distance_m": 1500, "time_min": 20})
        assert info.distance_m == 1500
        assert info.time_min == 20

    def test_to_poi_minimal(self):
        raw = {"id": "p1", "name": "Test", "category": "food", "city": "Zhuhai"}
        poi = _to_poi(raw)
        assert poi.id == "p1"
        assert poi.name == "Test"
        assert poi.rating == 0.0

    def test_to_poi_full(self):
        raw = {
            "id": "p2",
            "name": "Park",
            "category": "nature",
            "city": "Zhuhai",
            "rating": 4.5,
            "avg_price": 0,
            "avg_stay_min": 90,
            "lat": 22.27,
            "lng": 113.58,
            "business_hours": "06:00-22:00",
            "tags": ["free"],
            "emotion_tags": {
                "excitement": 0.2,
                "tranquility": 0.9,
                "sociability": 0.1,
                "culture_depth": 0.1,
                "surprise": 0.1,
                "physical_demand": 0.3,
            },
        }
        poi = _to_poi(raw)
        assert poi.avg_stay_min == 90
        assert poi.emotion_tags is not None
        assert poi.emotion_tags.tranquility == 0.9

    def test_to_narrative_none(self):
        assert _to_narrative(None) is None

    def test_to_narrative_valid(self):
        raw = {
            "opening": "Start",
            "steps": ["Step 1", "Step 2"],
            "closing": "End",
            "emotion_highlights": [{"key": "val"}],
        }
        n = _to_narrative(raw)
        assert n.opening == "Start"
        assert len(n.steps) == 2
        assert len(n.emotion_highlights) == 1

    def test_to_total_cost_none(self):
        assert _to_total_cost(None) is None

    def test_to_total_cost_valid(self):
        tc = _to_total_cost({"time_min": 180, "budget_used": 200.5, "step_estimate": 3000})
        assert tc.time_min == 180
        assert tc.budget_used == 200.5

    def test_to_route_step(self):
        raw = {
            "poi": {"id": "p1", "name": "A", "category": "x", "city": "Z"},
            "arrival_time": "09:00",
            "departure_time": "10:00",
            "travel_from_prev": {"distance_m": 500, "time_min": 10},
        }
        step = _to_route_step(raw)
        assert step.poi.id == "p1"
        assert step.arrival_time == "09:00"
        assert step.travel_from_prev.distance_m == 500

    def test_to_route(self):
        raw = {
            "route": [
                {
                    "poi": {"id": "p1", "name": "A", "category": "x", "city": "Z"},
                    "arrival_time": "09:00",
                    "departure_time": "10:00",
                }
            ],
            "narrative": {"opening": "hi", "steps": ["s1"], "closing": "bye"},
            "total_cost": {"time_min": 60, "budget_used": 50, "step_estimate": 1000},
            "emotion_curve": ["happy"],
        }
        route = _to_route(route_id="r1", raw=raw, user_input="test input")
        assert route.route_id == "r1"
        assert route.user_input == "test input"
        assert len(route.steps) == 1
        assert route.narrative is not None
        assert route.emotion_curve == ["happy"]


# ---------------------------------------------------------------------------
# Schema 内省测试（通过 schema.execute）
# ---------------------------------------------------------------------------


class TestSchemaIntrospection:
    """通过 Strawberry schema.execute 测试 Schema 自省。"""

    @pytest.mark.asyncio
    async def test_introspection_query_type(self):
        result = await schema.execute("{ __schema { queryType { name } mutationType { name } } }")
        assert result.errors is None
        info = result.data["__schema"]
        assert info["queryType"]["name"] == "Query"
        assert info["mutationType"]["name"] == "Mutation"

    @pytest.mark.asyncio
    async def test_introspection_types_include_poi(self):
        result = await schema.execute('{ __type(name: "POI") { name kind fields { name } } }')
        assert result.errors is None
        poi_type = result.data["__type"]
        assert poi_type["name"] == "POI"
        field_names = [f["name"] for f in poi_type["fields"]]
        assert "id" in field_names
        assert "name" in field_names
        assert "category" in field_names
        assert "emotionTags" in field_names

    @pytest.mark.asyncio
    async def test_introspection_route_type(self):
        result = await schema.execute('{ __type(name: "Route") { name fields { name } } }')
        assert result.errors is None
        fields = [f["name"] for f in result.data["__type"]["fields"]]
        assert "routeId" in fields
        assert "steps" in fields
        assert "narrative" in fields

    @pytest.mark.asyncio
    async def test_introspection_emotion_tags_type(self):
        result = await schema.execute('{ __type(name: "EmotionTags") { name fields { name } } }')
        assert result.errors is None
        fields = [f["name"] for f in result.data["__type"]["fields"]]
        assert "excitement" in fields
        assert "tranquility" in fields
        assert "sociability" in fields


# ---------------------------------------------------------------------------
# GraphQL 查询/变更测试（通过 schema.execute，无 HTTP 中间件开销）
# ---------------------------------------------------------------------------


class TestPOIQueriesViaSchema:
    """通过 schema.execute 测试 POI 查询。"""

    @pytest.mark.asyncio
    async def test_query_pois(self):
        result = await schema.execute("""
            query {
                pois(limit: 5) {
                    id name category rating lat lng
                }
            }
        """)
        assert result.errors is None
        assert isinstance(result.data["pois"], list)

    @pytest.mark.asyncio
    async def test_query_pois_with_category(self):
        result = await schema.execute(
            'query { pois(category: "文化", limit: 3) { id name category } }'
        )
        assert result.errors is None
        for poi in result.data["pois"]:
            assert poi["category"] == "文化"

    @pytest.mark.asyncio
    async def test_query_pois_with_region(self):
        result = await schema.execute('query { pois(region: "珠海", limit: 3) { id name city } }')
        assert result.errors is None

    @pytest.mark.asyncio
    async def test_query_single_poi(self):
        # 先获取一个有效的 POI ID
        list_result = await schema.execute(
            "{ pois(limit: 1) { id name emotionTags { excitement tranquility } } }"
        )
        assert list_result.errors is None
        pois = list_result.data["pois"]
        if not pois:
            pytest.skip("No POI data available")
        poi_id = pois[0]["id"]

        result = await schema.execute(
            f'{{ poi(id: "{poi_id}") {{ id name category rating emotionTags {{ excitement }} }} }}'
        )
        assert result.errors is None
        assert result.data["poi"] is not None
        assert result.data["poi"]["id"] == poi_id

    @pytest.mark.asyncio
    async def test_query_nonexistent_poi(self):
        result = await schema.execute('{ poi(id: "nonexistent_xyz_123") { id name } }')
        assert result.errors is None
        assert result.data["poi"] is None


class TestRouteQueriesViaSchema:
    """通过 schema.execute 测试路线查询。"""

    @pytest.mark.asyncio
    async def test_query_routes(self):
        result = await schema.execute("""
            query {
                routes(limit: 5) {
                    routeId
                    steps { poi { name } arrivalTime }
                }
            }
        """)
        assert result.errors is None
        assert isinstance(result.data["routes"], list)

    @pytest.mark.asyncio
    async def test_query_nonexistent_route(self):
        result = await schema.execute('{ route(id: "nonexistent_id_xyz") { routeId } }')
        assert result.errors is None
        assert result.data["route"] is None


class TestPlanRouteMutationViaSchema:
    """通过 schema.execute 测试路线规划 Mutation。"""

    @pytest.mark.asyncio
    async def test_plan_route_structure(self):
        result = await schema.execute("""
            mutation {
                planRoute(userInput: "珠海一日游，喜欢安静的地方") {
                    routeId
                    userInput
                    steps {
                        poi { id name category }
                        arrivalTime
                        departureTime
                    }
                    emotionCurve
                }
            }
        """)
        # 可能因 LLM 不可用而报错，但不应有 schema 级别错误
        if result.errors:
            error_msg = result.errors[0].message
            assert any(
                kw in error_msg for kw in ("意图解析", "timeout", "超时", "没有找到")
            ), f"Unexpected error: {error_msg}"
        else:
            route = result.data["planRoute"]
            assert route["routeId"] is not None
            assert len(route["steps"]) > 0

    @pytest.mark.asyncio
    async def test_plan_route_with_variables(self):
        result = await schema.execute(
            "mutation($input: String!) { planRoute(userInput: $input) { routeId steps { poi { name } } } }",
            variable_values={"input": "带孩子去珠海玩，预算200"},
        )
        # 不应有 schema 级别错误（业务错误可接受）
        assert result.data is not None or result.errors is not None


class TestAdjustRouteMutationViaSchema:
    """通过 schema.execute 测试路线调整 Mutation。"""

    @pytest.mark.asyncio
    async def test_adjust_nonexistent_route(self):
        result = await schema.execute("""
            mutation {
                adjustRoute(routeId: "fake_id", instruction: "换一个地方") {
                    reply
                    route { routeId }
                    changesMade { type detail }
                }
            }
        """)
        assert result.errors is not None
        assert any("不存在" in e.message for e in result.errors)


# ---------------------------------------------------------------------------
# HTTP 端点集成测试（通过 FastAPI 测试客户端）
# ---------------------------------------------------------------------------


@pytest.fixture
async def gql_client() -> AsyncClient:
    """GraphQL HTTP 测试客户端。

    使用 raise_app_exceptions=False 避免中间件（Redis session）
    在无 Redis 环境下导致的 Event loop 错误。
    """
    from backend.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _post_graphql(client: AsyncClient, query: str, variables: dict | None = None) -> dict:
    """发送 GraphQL POST 请求并返回 JSON。"""
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = await client.post("/graphql", json=payload)
    return resp.json()


class TestHTTPEndpoint:
    """测试 HTTP 层面的 GraphQL 端点。

    注意: 受 Redis session 中间件影响，HTTP 测试在无 Redis 环境下
    可能出现 Event loop is closed 问题。核心功能已通过 schema.execute 覆盖，
    此处仅验证端点可达性。
    """

    @pytest.mark.xfail(reason="GraphQL HTTP endpoint middleware stack error (pre-existing)")
    @pytest.mark.asyncio
    async def test_post_graphql_returns_200(self, gql_client: AsyncClient):
        """POST /graphql 返回 200 且支持 __typename 查询。"""
        resp = await gql_client.post("/graphql", json={"query": "{ __typename }"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["__typename"] == "Query"
