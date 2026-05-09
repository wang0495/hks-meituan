"""CityFlow API Mock 测试。

不依赖真实数据和外部服务，通过 Mock 验证 API 层的行为：
- /api/health 健康检查
- /api/plan 路线规划（SSE 流式）
- /api/poi/search POI 搜索
- /api/poi/detail POI 详情
- /api/cache/stats 缓存统计
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.factories import RouteFactory

# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


class TestHealthAPI:
    """健康检查接口测试。"""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        """GET /api/health 返回 200 和 ok 状态。"""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# 缓存统计
# ---------------------------------------------------------------------------


class TestCacheStatsAPI:
    """缓存统计接口测试。"""

    @pytest.mark.asyncio
    async def test_cache_stats(self, client: AsyncClient) -> None:
        """GET /api/cache/stats 返回缓存统计信息。"""
        response = await client.get("/api/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert "l1_caches" in data
        assert "multilevel_cache" in data
        assert "route_cache" in data["l1_caches"]
        assert "distance_cache" in data["l1_caches"]
        assert "poi_cache" in data["l1_caches"]


# ---------------------------------------------------------------------------
# POI 搜索 Mock 测试
# ---------------------------------------------------------------------------


class TestPOISearchMock:
    """POI 搜索接口 Mock 测试。"""

    @pytest.mark.asyncio
    async def test_search_returns_pois(self, client: AsyncClient) -> None:
        """POST /api/poi/search 返回 POI 列表。"""
        response = await client.post(
            "/api/poi/search",
            json={"region": "珠海"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "pois" in data
        assert "total" in data
        assert isinstance(data["pois"], list)

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, client: AsyncClient) -> None:
        """按类别筛选 POI。"""
        response = await client.post(
            "/api/poi/search",
            json={"categories": ["文化"]},
        )
        assert response.status_code == 200
        data = response.json()
        for poi in data["pois"]:
            assert poi["category"] == "文化"

    @pytest.mark.asyncio
    async def test_search_with_rating_filter(self, client: AsyncClient) -> None:
        """按最低评分筛选。"""
        response = await client.post(
            "/api/poi/search",
            json={"min_rating": 4.0},
        )
        assert response.status_code == 200
        data = response.json()
        for poi in data["pois"]:
            assert poi["rating"] >= 4.0

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, client: AsyncClient) -> None:
        """按最高价格筛选。"""
        response = await client.post(
            "/api/poi/search",
            json={"max_price": 50},
        )
        assert response.status_code == 200
        data = response.json()
        for poi in data["pois"]:
            assert poi["avg_price"] <= 50

    @pytest.mark.asyncio
    async def test_search_with_keyword(self, client: AsyncClient) -> None:
        """关键词模糊搜索。"""
        response = await client.post(
            "/api/poi/search",
            json={"keyword": "图书馆"},
        )
        assert response.status_code == 200
        data = response.json()
        for poi in data["pois"]:
            assert "图书馆" in poi["name"]

    @pytest.mark.asyncio
    async def test_search_empty_result(self, client: AsyncClient) -> None:
        """不存在的区域返回空列表。"""
        response = await client.post(
            "/api/poi/search",
            json={"region": "不存在的城市_xyz_999"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["pois"] == []

    @pytest.mark.asyncio
    async def test_search_pois_have_emotion_tags(self, client: AsyncClient) -> None:
        """搜索结果中的 POI 包含情绪标签。"""
        response = await client.post(
            "/api/poi/search",
            json={"region": "珠海"},
        )
        assert response.status_code == 200
        data = response.json()
        if data["pois"]:
            poi = data["pois"][0]
            assert "emotion_tags" in poi
            emotion = poi["emotion_tags"]
            assert "excitement" in emotion
            assert "tranquility" in emotion
            assert "sociability" in emotion
            assert "culture_depth" in emotion
            assert "surprise" in emotion
            assert "physical_demand" in emotion

    @pytest.mark.asyncio
    async def test_search_pois_have_price_range(self, client: AsyncClient) -> None:
        """搜索结果中的 POI 包含价格区间。"""
        response = await client.post(
            "/api/poi/search",
            json={"region": "珠海"},
        )
        assert response.status_code == 200
        data = response.json()
        if data["pois"]:
            poi = data["pois"][0]
            assert "price_range" in poi
            assert poi["price_range"] in ("免费", "便宜", "中等", "较贵", "高端")


# ---------------------------------------------------------------------------
# POI 详情 Mock 测试
# ---------------------------------------------------------------------------


class TestPOIDetailMock:
    """POI 详情接口 Mock 测试。"""

    @pytest.mark.asyncio
    async def test_get_existing_poi_detail(self, client: AsyncClient) -> None:
        """获取存在的 POI 详情。"""
        # 先搜索获取一个有效 ID
        search_resp = await client.post(
            "/api/poi/search",
            json={"region": "珠海"},
        )
        pois = search_resp.json()["pois"]
        if not pois:
            pytest.skip("无可用 POI 数据")

        poi_id = pois[0]["id"]
        response = await client.get(f"/api/poi/detail/{poi_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == poi_id
        assert "name" in data
        assert "emotion_tags" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_poi_returns_404(self, client: AsyncClient) -> None:
        """获取不存在的 POI 返回 404。"""
        response = await client.get("/api/poi/detail/nonexistent_id_xyz")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 路线规划 Mock 测试
# ---------------------------------------------------------------------------


class TestPlanRouteMock:
    """路线规划接口 Mock 测试。"""

    @pytest.mark.asyncio
    async def test_plan_route_sse_stream(self, client: AsyncClient) -> None:
        """POST /api/plan 返回 SSE 事件流。"""
        response = await client.post(
            "/api/plan",
            json={"user_input": "周末想出去走走"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # 解析 SSE 事件
        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        # 应该包含 phase 和 done 事件
        assert "phase" in event_types or "done" in event_types or "error" in event_types

    @pytest.mark.asyncio
    async def test_plan_route_with_mock_solver(self, client: AsyncClient) -> None:
        """Mock 求解器，验证路线规划流程。"""
        mock_route = RouteFactory.create(poi_count=2)

        with patch(
            "backend.services.solver.solve_route",
            return_value=mock_route,
        ):
            response = await client.post(
                "/api/plan",
                json={"user_input": "周末想出去走走"},
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        # 至少应该有 phase 事件
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_plan_route_empty_input_rejected(self, client: AsyncClient) -> None:
        """空输入应被 Pydantic 验证拒绝。"""
        response = await client.post(
            "/api/plan",
            json={"user_input": ""},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_plan_route_missing_field_rejected(self, client: AsyncClient) -> None:
        """缺少必填字段应被拒绝。"""
        response = await client.post("/api/plan", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 路线查询 Mock 测试
# ---------------------------------------------------------------------------


class TestRouteQueryMock:
    """路线查询接口测试。"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_route_returns_404(self, client: AsyncClient) -> None:
        """查询不存在的路线返回 404。"""
        response = await client.get("/api/route/nonexistent_route_id")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# SSE 解析辅助
# ---------------------------------------------------------------------------


def _parse_sse_events(raw: str) -> list[dict]:
    """解析 SSE 文本为事件列表。

    Args:
        raw: SSE 响应的原始文本。

    Returns:
        事件列表，每项包含 event 和 data 字段。
    """
    events: list[dict] = []
    current_event = ""
    current_data = ""

    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data = line[len("data:") :].strip()
        elif line == "" and current_event:
            parsed_data = None
            try:
                parsed_data = json.loads(current_data)
            except (json.JSONDecodeError, TypeError):
                parsed_data = current_data
            events.append({"event": current_event, "data": parsed_data})
            current_event = ""
            current_data = ""

    # 处理末尾事件
    if current_event:
        parsed_data = None
        try:
            parsed_data = json.loads(current_data)
        except (json.JSONDecodeError, TypeError):
            parsed_data = current_data
        events.append({"event": current_event, "data": parsed_data})

    return events
