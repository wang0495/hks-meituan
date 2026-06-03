"""中间件管道和性能监控中间件的单元测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from backend.middleware.performance import PerformanceMiddleware
from backend.middleware.pipeline import ConditionalMiddleware, MiddlewarePipeline, MiddlewareStats

# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _make_middleware(name: str, side_effect=None, response_body: str = "ok"):
    """创建一个简单的 mock 中间件。"""

    async def handler(request: Request, call_next) -> Response:
        if side_effect:
            side_effect(name)
        resp = await call_next(request)
        resp.headers[f"X-{name}"] = "1"
        return resp

    handler.__name__ = name
    return handler


def _make_failing_middleware(name: str, error_msg: str = "boom"):
    """创建一个会抛异常的 mock 中间件。"""

    async def handler(request: Request, call_next) -> Response:
        raise RuntimeError(error_msg)

    handler.__name__ = name
    return handler


def _make_request(path: str = "/api/test", method: str = "GET") -> MagicMock:
    """创建一个 mock Request。"""
    request = MagicMock(spec=Request)
    request.url = MagicMock()
    request.url.path = path
    request.method = method
    request.headers = {}
    request.state = MagicMock()
    return request


# ---------------------------------------------------------------------------
# MiddlewareStats
# ---------------------------------------------------------------------------


class TestMiddlewareStats:
    """MiddlewareStats 数据类测试。"""

    def test_initial_state(self) -> None:
        stats = MiddlewareStats()
        assert stats.count == 0
        assert stats.total_time == 0.0
        assert stats.errors == 0
        assert stats.avg_time == 0.0
        assert stats.error_rate == 0.0
        assert stats.percentile(50) == 0.0

    def test_record_success(self) -> None:
        stats = MiddlewareStats()
        stats.count = 10
        stats.total_time = 2.5
        stats.errors = 1
        for i in range(10):
            stats.latency_samples.append(0.25)

        assert stats.avg_time == pytest.approx(0.25)
        assert stats.error_rate == pytest.approx(0.1)
        assert stats.percentile(50) == pytest.approx(0.25)

    def test_to_dict(self) -> None:
        stats = MiddlewareStats(count=5, total_time=1.0, errors=1)
        for _ in range(5):
            stats.latency_samples.append(0.2)
        d = stats.to_dict()
        assert d["count"] == 5
        assert d["total_time"] == 1.0
        assert d["avg_time"] == 0.2
        assert d["errors"] == 1
        assert d["error_rate"] == 0.2
        assert "p50" in d
        assert "p95" in d
        assert "p99" in d


# ---------------------------------------------------------------------------
# MiddlewarePipeline
# ---------------------------------------------------------------------------


class TestMiddlewarePipeline:
    """MiddlewarePipeline 核心功能测试。"""

    @pytest.mark.asyncio
    async def test_empty_pipeline(self) -> None:
        """空管道应直接调用 call_next。"""
        pipeline = MiddlewarePipeline()
        request = _make_request()
        expected = Response(content="direct")

        async def call_next(req):
            return expected

        response = await pipeline.execute(request, call_next)
        assert response.body == b"direct"

    @pytest.mark.asyncio
    async def test_single_middleware(self) -> None:
        """单个中间件应正确执行。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("mw1"), name="mw1")

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="ok"))

        response = await pipeline.execute(request, call_next)
        assert response.headers.get("X-mw1") == "1"

    @pytest.mark.asyncio
    async def test_execution_order(self) -> None:
        """中间件应按添加顺序从外到内执行。"""
        pipeline = MiddlewarePipeline()
        order: list[str] = []

        def track(name):
            order.append(name)

        pipeline.add(_make_middleware("first", side_effect=track), name="first")
        pipeline.add(_make_middleware("second", side_effect=track), name="second")
        pipeline.add(_make_middleware("third", side_effect=track), name="third")

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="ok"))

        await pipeline.execute(request, call_next)
        assert order == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_stats_recorded(self) -> None:
        """执行后应记录统计信息。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("mw"), name="mw")

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="ok"))

        await pipeline.execute(request, call_next)

        stats = pipeline.get_stats("mw")
        assert stats is not None
        assert stats["count"] == 1
        assert stats["errors"] == 0
        assert stats["total_time"] >= 0

    @pytest.mark.asyncio
    async def test_error_stats_recorded(self) -> None:
        """中间件抛异常时应记录错误统计并重新抛出。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_failing_middleware("bad_mw"), name="bad_mw")

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="ok"))

        with pytest.raises(RuntimeError, match="boom"):
            await pipeline.execute(request, call_next)

        stats = pipeline.get_stats("bad_mw")
        assert stats is not None
        assert stats["count"] == 1
        assert stats["errors"] == 1

    def test_add_returns_self(self) -> None:
        """add 应返回 self 以支持链式调用。"""
        pipeline = MiddlewarePipeline()
        result = pipeline.add(_make_middleware("mw"), name="mw")
        assert result is pipeline

    def test_remove_existing(self) -> None:
        """移除已存在的中间件应返回 True。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("mw"), name="mw")
        assert pipeline.remove("mw") is True
        assert pipeline.names == []

    def test_remove_nonexistent(self) -> None:
        """移除不存在的中间件应返回 False。"""
        pipeline = MiddlewarePipeline()
        assert pipeline.remove("nope") is False

    def test_names(self) -> None:
        """names 应按添加顺序返回。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("a"), name="a")
        pipeline.add(_make_middleware("b"), name="b")
        pipeline.add(_make_middleware("c"), name="c")
        assert pipeline.names == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_get_all_stats(self) -> None:
        """get_all_stats 应返回所有中间件的统计。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("a"), name="a")
        pipeline.add(_make_middleware("b"), name="b")

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="ok"))
        await pipeline.execute(request, call_next)

        all_stats = pipeline.get_all_stats()
        assert "a" in all_stats
        assert "b" in all_stats
        assert all_stats["a"]["count"] == 1
        assert all_stats["b"]["count"] == 1

    @pytest.mark.asyncio
    async def test_reset_stats(self) -> None:
        """reset_stats 应清零所有统计。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("mw"), name="mw")

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="ok"))
        await pipeline.execute(request, call_next)

        pipeline.reset_stats()
        stats = pipeline.get_stats("mw")
        assert stats is not None
        assert stats["count"] == 0
        assert stats["total_time"] == 0.0
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_summary(self) -> None:
        """get_stats_summary 应返回管道整体摘要。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("a"), name="a")
        pipeline.add(_make_middleware("b"), name="b")

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="ok"))
        await pipeline.execute(request, call_next)

        summary = pipeline.get_stats_summary()
        assert summary["pipeline_length"] == 2
        assert summary["middleware_order"] == ["a", "b"]
        assert summary["total_requests"] == 2
        assert summary["total_errors"] == 0
        assert "slowest_middleware" in summary
        assert "per_middleware" in summary

    @pytest.mark.asyncio
    async def test_multiple_executions(self) -> None:
        """多次执行应累加统计。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(_make_middleware("mw"), name="mw")

        call_next = AsyncMock(return_value=Response(content="ok"))

        for _ in range(5):
            await pipeline.execute(_make_request(), call_next)

        stats = pipeline.get_stats("mw")
        assert stats is not None
        assert stats["count"] == 5

    @pytest.mark.asyncio
    async def test_default_name_from_function(self) -> None:
        """不指定 name 时应使用函数名。"""

        async def my_middleware(request, call_next):
            return await call_next(request)

        pipeline = MiddlewarePipeline()
        pipeline.add(my_middleware)
        assert pipeline.names == ["my_middleware"]

    def test_get_stats_nonexistent(self) -> None:
        """查询不存在的中间件统计应返回 None。"""
        pipeline = MiddlewarePipeline()
        assert pipeline.get_stats("nope") is None


# ---------------------------------------------------------------------------
# ConditionalMiddleware
# ---------------------------------------------------------------------------


class TestConditionalMiddleware:
    """ConditionalMiddleware 测试。"""

    @pytest.mark.asyncio
    async def test_condition_true_executes_middleware(self) -> None:
        """条件为 True 时应执行中间件。"""
        executed = False

        async def inner_mw(request, call_next):
            nonlocal executed
            executed = True
            return await call_next(request)

        cm = ConditionalMiddleware(
            condition=lambda req: req.url.path.startswith("/api/"),
            middleware=inner_mw,
        )

        request = _make_request(path="/api/test")
        call_next = AsyncMock(return_value=Response(content="ok"))
        await cm(request, call_next)

        assert executed is True

    @pytest.mark.asyncio
    async def test_condition_false_skips_middleware(self) -> None:
        """条件为 False 时应跳过中间件。"""
        executed = False

        async def inner_mw(request, call_next):
            nonlocal executed
            executed = True
            return await call_next(request)

        cm = ConditionalMiddleware(
            condition=lambda req: req.url.path.startswith("/admin/"),
            middleware=inner_mw,
        )

        request = _make_request(path="/api/test")
        call_next = AsyncMock(return_value=Response(content="ok"))
        await cm(request, call_next)

        assert executed is False

    @pytest.mark.asyncio
    async def test_condition_false_calls_next(self) -> None:
        """条件为 False 时应直接调用 call_next。"""

        async def inner_mw(request, call_next):
            return Response(content="blocked")

        cm = ConditionalMiddleware(
            condition=lambda req: False,
            middleware=inner_mw,
        )

        request = _make_request()
        call_next = AsyncMock(return_value=Response(content="passed"))
        response = await cm(request, call_next)

        assert response.body == b"passed"

    @pytest.mark.asyncio
    async def test_method_based_condition(self) -> None:
        """按 HTTP 方法条件执行。"""

        async def cache_mw(request, call_next):
            return Response(content="cached")

        cm = ConditionalMiddleware(
            condition=lambda req: req.method == "GET",
            middleware=cache_mw,
        )

        # GET 应执行缓存
        get_request = _make_request(method="GET")
        call_next = AsyncMock(return_value=Response(content="ok"))
        response = await cm(get_request, call_next)
        assert response.body == b"cached"

        # POST 不应执行缓存
        post_request = _make_request(method="POST")
        call_next = AsyncMock(return_value=Response(content="created"))
        response = await cm(post_request, call_next)
        assert response.body == b"created"


# ---------------------------------------------------------------------------
# PerformanceMiddleware
# ---------------------------------------------------------------------------


class TestPerformanceMiddleware:
    """PerformanceMiddleware 测试。"""

    @pytest.mark.asyncio
    async def test_injects_request_id(self) -> None:
        """应注入 X-Request-ID 到响应头。"""

        class FakeApp:
            async def __call__(self, scope, receive, send):
                pass

        mw = PerformanceMiddleware(FakeApp(), slow_threshold=10.0)

        # 模拟 call_next
        request = _make_request()
        expected_response = Response(content="ok")

        async def call_next(req):
            return expected_response

        # 直接调用 dispatch
        response = await mw.dispatch(request, call_next)

        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 8

    @pytest.mark.asyncio
    async def test_injects_response_time(self) -> None:
        """应注入 X-Response-Time 到响应头。"""

        class FakeApp:
            async def __call__(self, scope, receive, send):
                pass

        mw = PerformanceMiddleware(FakeApp(), slow_threshold=10.0)

        request = _make_request()
        expected_response = Response(content="ok")

        async def call_next(req):
            return expected_response

        response = await mw.dispatch(request, call_next)

        assert "X-Response-Time" in response.headers
        # 格式应为 "X.XXXs"
        time_str = response.headers["X-Response-Time"]
        assert time_str.endswith("s")
        float(time_str[:-1])  # 应可解析为 float

    @pytest.mark.asyncio
    async def test_request_state_has_id(self) -> None:
        """应将 request_id 写入 request.state。"""

        class FakeApp:
            async def __call__(self, scope, receive, send):
                pass

        mw = PerformanceMiddleware(FakeApp(), slow_threshold=10.0)

        request = _make_request()
        expected_response = Response(content="ok")

        async def call_next(req):
            return expected_response

        await mw.dispatch(request, call_next)

        assert request.state.request_id is not None
        assert len(request.state.request_id) == 8

    @pytest.mark.asyncio
    async def test_custom_header_name(self) -> None:
        """应支持自定义请求 ID 响应头名称。"""

        class FakeApp:
            async def __call__(self, scope, receive, send):
                pass

        mw = PerformanceMiddleware(FakeApp(), slow_threshold=10.0, request_id_header="X-Trace-ID")

        request = _make_request()
        expected_response = Response(content="ok")

        async def call_next(req):
            return expected_response

        response = await mw.dispatch(request, call_next)

        assert "X-Trace-ID" in response.headers
        assert "X-Request-ID" not in response.headers

    @pytest.mark.asyncio
    async def test_slow_request_logged(self, caplog) -> None:
        """超过阈值的请求应记录慢请求日志。"""
        import logging

        class FakeApp:
            async def __call__(self, scope, receive, send):
                pass

        mw = PerformanceMiddleware(FakeApp(), slow_threshold=0.0)

        request = _make_request(path="/api/slow")
        expected_response = Response(content="ok")

        async def call_next(req):
            await asyncio.sleep(0.01)  # 模拟慢请求
            return expected_response

        with caplog.at_level(logging.WARNING):
            await mw.dispatch(request, call_next)

        assert any("慢请求" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_fast_request_not_logged(self, caplog) -> None:
        """未超过阈值的请求不应记录慢请求日志。"""
        import logging

        class FakeApp:
            async def __call__(self, scope, receive, send):
                pass

        mw = PerformanceMiddleware(FakeApp(), slow_threshold=10.0)

        request = _make_request(path="/api/fast")
        expected_response = Response(content="ok")

        async def call_next(req):
            return expected_response

        with caplog.at_level(logging.WARNING):
            await mw.dispatch(request, call_next)

        assert not any("慢请求" in record.message for record in caplog.records)
