"""CityFlow 性能优化测试。

测试目标：
- 批量请求的并发处理能力
- 规则匹配的响应速度
- 大量 POI 的处理性能
- 缓存命中率
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import pytest

from backend.services.intent_parser import _rule_based_parse
from backend.services.narrator import generate_narrative
from backend.services.solver import solve_route
from tests.factories import IntentFactory, POIFactory, RouteFactory

if TYPE_CHECKING:
    from httpx import AsyncClient

# ---------------------------------------------------------------------------
# 规则匹配性能
# ---------------------------------------------------------------------------


class TestRuleParsePerformance:
    """规则匹配性能测试。"""

    def test_rule_parse_latency(self) -> None:
        """单次规则匹配应在 10ms 内完成。"""
        inputs = [
            "周末想一个人安静走走",
            "和女朋友约会，预算300元",
            "带孩子出去玩，不要太累",
            "特种兵打卡，一天去10个地方",
            "带狗子出去转转，想去公园",
        ]

        for text in inputs:
            start = time.perf_counter()
            _rule_based_parse(text)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < 10, f"规则匹配耗时 {elapsed_ms:.1f}ms，超过 10ms: {text}"

    def test_rule_parse_batch_throughput(self) -> None:
        """批量规则匹配吞吐量测试。"""
        inputs = [
            "周末想一个人安静走走",
            "和女朋友约会",
            "带孩子出去玩",
            "特种兵打卡",
            "带狗子出去转转",
            "退休老人散步",
            "和朋友聚会",
            "想去博物馆看展",
            "想找好吃的餐厅",
            "想去公园爬山",
        ] * 10  # 100 次调用

        start = time.perf_counter()
        for text in inputs:
            _rule_based_parse(text)
        elapsed_s = time.perf_counter() - start

        # 100 次规则匹配应该在 1 秒内完成
        assert elapsed_s < 1.0, f"100 次规则匹配耗时 {elapsed_s:.2f}s"
        throughput = len(inputs) / elapsed_s
        assert throughput > 100, f"吞吐量 {throughput:.0f}/s 低于预期"


# ---------------------------------------------------------------------------
# 文案生成性能
# ---------------------------------------------------------------------------


class TestNarrativePerformance:
    """文案生成性能测试。"""

    @pytest.mark.asyncio
    async def test_narrative_generation_speed(self) -> None:
        """文案生成应在 100ms 内完成（无 LLM 润色）。"""
        route = RouteFactory.create(poi_count=5)
        intent = IntentFactory.create_solo_quiet()

        start = time.perf_counter()
        result = await generate_narrative(route, intent, enable_llm_polish=False)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 100, f"文案生成耗时 {elapsed_ms:.1f}ms"
        assert result["opening"]
        assert len(result["steps"]) == 5
        assert result["closing"]

    @pytest.mark.asyncio
    async def test_narrative_batch_generation(self) -> None:
        """批量文案生成性能。"""
        routes = [RouteFactory.create(poi_count=3) for _ in range(10)]
        intent = IntentFactory.create()

        start = time.perf_counter()
        results = await asyncio.gather(
            *(generate_narrative(r, intent, enable_llm_polish=False) for r in routes)
        )
        elapsed_s = time.perf_counter() - start

        assert len(results) == 10
        assert elapsed_s < 1.0, f"10 次文案生成耗时 {elapsed_s:.2f}s"


# ---------------------------------------------------------------------------
# POI 工厂性能
# ---------------------------------------------------------------------------


class TestFactoryPerformance:
    """数据工厂性能测试。"""

    def test_poi_factory_batch_creation(self) -> None:
        """批量创建 1000 个 POI 应在 1 秒内完成。"""
        start = time.perf_counter()
        pois = POIFactory.create_batch(1000)
        elapsed_s = time.perf_counter() - start

        assert len(pois) == 1000
        assert elapsed_s < 1.0, f"创建 1000 个 POI 耗时 {elapsed_s:.2f}s"

    def test_poi_factory_id_uniqueness(self) -> None:
        """批量创建的 POI ID 应该唯一。"""
        POIFactory.reset()
        pois = POIFactory.create_batch(100)
        ids = [p["id"] for p in pois]
        assert len(ids) == len(set(ids)), "存在重复 ID"

    def test_route_factory_creation(self) -> None:
        """路线工厂创建性能。"""
        start = time.perf_counter()
        routes = [RouteFactory.create(poi_count=5) for _ in range(100)]
        elapsed_s = time.perf_counter() - start

        assert len(routes) == 100
        assert elapsed_s < 1.0, f"创建 100 条路线耗时 {elapsed_s:.2f}s"


# ---------------------------------------------------------------------------
# 并发 API 测试
# ---------------------------------------------------------------------------


class TestConcurrentAPI:
    """并发 API 请求测试。"""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, client: AsyncClient) -> None:
        """并发健康检查请求。"""

        async def check_health() -> int:
            response = await client.get("/api/health")
            return response.status_code

        tasks = [check_health() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        assert all(r == 200 for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_poi_search(self, client: AsyncClient) -> None:
        """并发 POI 搜索请求。"""

        async def search_pois() -> int:
            response = await client.post(
                "/api/poi/search",
                json={"region": "珠海"},
            )
            return response.status_code

        tasks = [search_pois() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(r == 200 for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_rule_parse(self) -> None:
        """并发规则匹配。"""
        inputs = [
            "周末想一个人安静走走",
            "和女朋友约会",
            "带孩子出去玩",
            "特种兵打卡",
            "带狗子出去转转",
        ]

        async def parse(text: str) -> dict:
            return _rule_based_parse(text)

        tasks = [parse(text) for text in inputs]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert "time" in result
            assert "group" in result


# ---------------------------------------------------------------------------
# 路线求解性能
# ---------------------------------------------------------------------------


class TestSolverPerformance:
    """路线求解性能测试。"""

    def test_solver_small_pool(self) -> None:
        """小规模 POI 池（5个）求解应在 100ms 内完成。"""
        pois = POIFactory.create_batch(5)
        intent = IntentFactory.create()

        start = time.perf_counter()
        result = solve_route(pois, intent, "09:00")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 100, f"求解耗时 {elapsed_ms:.1f}ms"
        assert result.get("route")

    def test_solver_medium_pool(self) -> None:
        """中等规模 POI 池（20个）求解应在 1 秒内完成。"""
        pois = POIFactory.create_batch(20)
        intent = IntentFactory.create()

        start = time.perf_counter()
        result = solve_route(pois, intent, "09:00")
        elapsed_s = time.perf_counter() - start

        assert elapsed_s < 1.0, f"求解耗时 {elapsed_s:.2f}s"
        assert result.get("route")

    @pytest.mark.slow
    def test_solver_large_pool(self) -> None:
        """大规模 POI 池（50个）求解应在 5 秒内完成。"""
        pois = POIFactory.create_batch(50)
        intent = IntentFactory.create()

        start = time.perf_counter()
        result = solve_route(pois, intent, "09:00")
        elapsed_s = time.perf_counter() - start

        assert elapsed_s < 5.0, f"求解耗时 {elapsed_s:.2f}s"
        assert result.get("route")


# ---------------------------------------------------------------------------
# 混合负载测试
# ---------------------------------------------------------------------------


class TestMixedWorkload:
    """混合负载测试：模拟真实使用场景。"""

    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self, client: AsyncClient) -> None:
        """完整流水线测试（健康检查 + POI 搜索 + 路线规划）。"""

        async def health() -> int:
            resp = await client.get("/api/health")
            return resp.status_code

        async def search() -> int:
            resp = await client.post("/api/poi/search", json={"region": "珠海"})
            return resp.status_code

        async def plan() -> int:
            resp = await client.post("/api/plan", json={"user_input": "周末出去玩"})
            return resp.status_code

        # 并发执行不同类型请求
        tasks = [
            health(),
            health(),
            search(),
            search(),
            plan(),
        ]
        results = await asyncio.gather(*tasks)

        assert all(r == 200 for r in results)
