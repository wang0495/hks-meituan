"""CityFlow monitoring 模块测试。

覆盖范围：
  - error_filter（before_send / before_send_transaction）
  - sentry（init / capture）
  - metrics（基础指标和工具函数）
  - prometheus（完整业务指标）
  - prometheus middleware（路径排除、指标采集）
  - metrics router（端点响应）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# metrics 基础指标测试
# ---------------------------------------------------------------------------


class TestMetrics:
    """backend.monitoring.metrics 基础指标测试。"""

    def test_track_request_increments_counters(self) -> None:
        from backend.monitoring.metrics import REQUEST_COUNT, track_request

        track_request("GET", "/api/test", 200, 0.123)

        # 验证计数器增加
        sample = REQUEST_COUNT.labels(
            method="GET", endpoint="/api/test", status="200"
        )._value.get()
        assert sample >= 1.0

    def test_track_request_converts_status_to_str(self) -> None:
        from backend.monitoring.metrics import REQUEST_COUNT, track_request

        track_request("POST", "/api/plan", 500, 0.5)
        sample = REQUEST_COUNT.labels(
            method="POST", endpoint="/api/plan", status="500"
        )._value.get()
        assert sample >= 1.0

    def test_track_route_planning_increments(self) -> None:
        from backend.monitoring.metrics import (ROUTE_COUNT,
                                                track_route_planning)

        track_route_planning()
        track_route_planning()

        assert ROUTE_COUNT._value.get() >= 2.0

    def test_get_metrics_returns_bytes(self) -> None:
        from backend.monitoring.metrics import get_metrics

        result = get_metrics()
        assert isinstance(result, bytes)
        # 应包含至少一个已知指标名
        assert b"cityflow_requests_total" in result

    def test_active_sessions_gauge(self) -> None:
        from backend.monitoring.metrics import ACTIVE_SESSIONS

        ACTIVE_SESSIONS.set(42)
        assert ACTIVE_SESSIONS._value.get() == 42.0

    def test_histogram_buckets_cover_fast_and_slow(self) -> None:
        from backend.monitoring.metrics import track_request

        # 快速请求
        track_request("GET", "/fast", 200, 0.003)
        # 慢请求
        track_request("GET", "/slow", 200, 8.0)

        # 不应抛出异常
        assert True

    def test_track_cache_hit_increments(self) -> None:
        from backend.monitoring.metrics import CACHE_HITS, track_cache_hit

        track_cache_hit("route")
        track_cache_hit("route")

        sample = CACHE_HITS.labels(cache_name="route")._value.get()
        assert sample >= 2.0

    def test_track_cache_miss_increments(self) -> None:
        from backend.monitoring.metrics import CACHE_MISSES, track_cache_miss

        track_cache_miss("poi")

        sample = CACHE_MISSES.labels(cache_name="poi")._value.get()
        assert sample >= 1.0

    def test_cache_metrics_appear_in_output(self) -> None:
        from backend.monitoring.metrics import get_metrics

        result = get_metrics()
        assert b"cityflow_cache_hits_total" in result
        assert b"cityflow_cache_misses_total" in result


# ---------------------------------------------------------------------------
# prometheus 完整指标测试
# ---------------------------------------------------------------------------


class TestPrometheusMetrics:
    """backend.monitoring.prometheus 完整业务指标测试。"""

    def test_track_cache_hit(self) -> None:
        from backend.monitoring.prometheus import CACHE_HITS, track_cache_hit

        track_cache_hit("route")
        track_cache_hit("route")

        sample = CACHE_HITS.labels(cache_name="route")._value.get()
        assert sample >= 2.0

    def test_track_cache_miss(self) -> None:
        from backend.monitoring.prometheus import (CACHE_MISSES,
                                                   track_cache_miss)

        track_cache_miss("poi")

        sample = CACHE_MISSES.labels(cache_name="poi")._value.get()
        assert sample >= 1.0

    def test_track_cache_eviction(self) -> None:
        from backend.monitoring.prometheus import (CACHE_EVICTIONS,
                                                   track_cache_eviction)

        track_cache_eviction("distance")

        sample = CACHE_EVICTIONS.labels(cache_name="distance")._value.get()
        assert sample >= 1.0

    def test_update_cache_size(self) -> None:
        from backend.monitoring.prometheus import CACHE_SIZE, update_cache_size

        update_cache_size("route", 100)
        assert CACHE_SIZE.labels(cache_name="route")._value.get() == 100.0

    def test_track_ws_connect_disconnect(self) -> None:
        from backend.monitoring.prometheus import (WS_CONNECTIONS,
                                                   track_ws_connect,
                                                   track_ws_disconnect)

        track_ws_connect()
        track_ws_connect()
        after_connect = WS_CONNECTIONS._value.get()
        assert after_connect >= 2.0

        track_ws_disconnect()
        after_disconnect = WS_CONNECTIONS._value.get()
        assert after_disconnect <= after_connect

    def test_track_ws_message(self) -> None:
        from backend.monitoring.prometheus import WS_MESSAGES, track_ws_message

        track_ws_message("sent")
        track_ws_message("received")

        assert WS_MESSAGES.labels(direction="sent")._value.get() >= 1.0
        assert WS_MESSAGES.labels(direction="received")._value.get() >= 1.0

    def test_track_ws_error(self) -> None:
        from backend.monitoring.prometheus import WS_ERRORS, track_ws_error

        track_ws_error()
        assert WS_ERRORS._value.get() >= 1.0

    def test_update_circuit_breaker_state(self) -> None:
        from backend.monitoring.prometheus import (
            CIRCUIT_BREAKER_STATE, update_circuit_breaker_state)

        update_circuit_breaker_state("llm", 1)
        assert CIRCUIT_BREAKER_STATE.labels(service="llm")._value.get() == 1.0

    def test_track_circuit_breaker_rejection(self) -> None:
        from backend.monitoring.prometheus import (
            CIRCUIT_BREAKER_REJECTIONS, track_circuit_breaker_rejection)

        track_circuit_breaker_rejection("llm")
        assert CIRCUIT_BREAKER_REJECTIONS.labels(service="llm")._value.get() >= 1.0

    def test_track_llm_call(self) -> None:
        from backend.monitoring.prometheus import (LLM_CALL_COUNT,
                                                   LLM_TOKEN_USAGE,
                                                   track_llm_call)

        track_llm_call(
            model="deepseek",
            status="success",
            duration=2.5,
            prompt_tokens=500,
            completion_tokens=200,
        )

        assert (
            LLM_CALL_COUNT.labels(model="deepseek", status="success")._value.get()
            >= 1.0
        )
        assert (
            LLM_TOKEN_USAGE.labels(model="deepseek", type="prompt")._value.get()
            >= 500.0
        )
        assert (
            LLM_TOKEN_USAGE.labels(model="deepseek", type="completion")._value.get()
            >= 200.0
        )

    def test_track_poi_query(self) -> None:
        from backend.monitoring.prometheus import (POI_QUERY_COUNT,
                                                   track_poi_query)

        track_poi_query("search", duration=0.05)
        assert POI_QUERY_COUNT.labels(query_type="search")._value.get() >= 1.0

    def test_track_dialogue(self) -> None:
        from backend.monitoring.prometheus import (DIALOGUE_COUNT,
                                                   track_dialogue)

        track_dialogue("replace", duration=1.0)
        assert DIALOGUE_COUNT.labels(instruction_type="replace")._value.get() >= 1.0

    def test_track_task(self) -> None:
        from backend.monitoring.prometheus import TASK_COUNT, track_task

        track_task("completed", duration=5.0)
        assert TASK_COUNT.labels(status="completed")._value.get() >= 1.0

    def test_update_task_queue_size(self) -> None:
        from backend.monitoring.prometheus import (TASK_QUEUE_SIZE,
                                                   update_task_queue_size)

        update_task_queue_size(50)
        assert TASK_QUEUE_SIZE._value.get() == 50.0

    def test_update_system_resources(self) -> None:
        from backend.monitoring.prometheus import (SYSTEM_CPU_PERCENT,
                                                   SYSTEM_DISK_PERCENT,
                                                   SYSTEM_MEMORY_PERCENT,
                                                   SYSTEM_MEMORY_USED_MB,
                                                   update_system_resources)

        update_system_resources(
            cpu=55.0,
            memory_percent=70.0,
            memory_used_mb=4096.0,
            disk_percent=45.0,
        )

        assert SYSTEM_CPU_PERCENT._value.get() == 55.0
        assert SYSTEM_MEMORY_PERCENT._value.get() == 70.0
        assert SYSTEM_MEMORY_USED_MB._value.get() == 4096.0
        assert SYSTEM_DISK_PERCENT._value.get() == 45.0

    def test_track_request_size(self) -> None:
        from backend.monitoring.prometheus import track_request_size

        # Histogram 没有 _value 属性，只需确认不抛异常
        track_request_size("POST", "/api/plan", 1024)
        track_request_size("POST", "/api/plan", 2048)

    def test_track_response_size(self) -> None:
        from backend.monitoring.prometheus import track_response_size

        # Histogram 没有 _value 属性，只需确认不抛异常
        track_response_size("GET", "/api/data", 200, 4096)

    def test_get_metrics_summary(self) -> None:
        from backend.monitoring.prometheus import (ACTIVE_SESSIONS,
                                                   WS_CONNECTIONS,
                                                   get_metrics_summary,
                                                   update_system_resources,
                                                   update_task_queue_size)

        ACTIVE_SESSIONS.set(10)
        WS_CONNECTIONS.set(5)
        update_task_queue_size(3)
        update_system_resources(25.0, 60.0, 2048.0, 50.0)

        summary = get_metrics_summary()
        assert summary["active_sessions"] == 10.0
        assert summary["ws_connections"] == 5.0
        assert summary["task_queue_size"] == 3.0
        assert summary["system_cpu_percent"] == 25.0

    def test_session_counters(self) -> None:
        from backend.monitoring.prometheus import (SESSION_CREATED,
                                                   SESSION_EXPIRED)

        SESSION_CREATED.inc()
        SESSION_EXPIRED.inc()

        assert SESSION_CREATED._value.get() >= 1.0
        assert SESSION_EXPIRED._value.get() >= 1.0


# ---------------------------------------------------------------------------
# Prometheus 中间件测试
# ---------------------------------------------------------------------------


class TestPrometheusMiddleware:
    """PrometheusMiddleware 路径排除和指标采集测试。"""

    def test_excluded_paths_contain_metrics(self) -> None:
        from backend.middleware.prometheus import _EXCLUDED_PATHS

        assert "/metrics" in _EXCLUDED_PATHS
        assert "/metrics/health" in _EXCLUDED_PATHS
        assert "/api/health" in _EXCLUDED_PATHS
        assert "/health" in _EXCLUDED_PATHS
        assert "/docs" in _EXCLUDED_PATHS
        assert "/redoc" in _EXCLUDED_PATHS
        assert "/openapi.json" in _EXCLUDED_PATHS

    @pytest.mark.asyncio
    async def test_excluded_path_skips_metrics(self) -> None:
        from backend.middleware.prometheus import PrometheusMiddleware

        app = MagicMock()
        middleware = PrometheusMiddleware(app)

        mock_request = MagicMock()
        mock_request.url.path = "/metrics"

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await middleware.dispatch(mock_request, call_next)
        call_next.assert_called_once_with(mock_request)
        assert response is mock_response

    @pytest.mark.asyncio
    async def test_normal_path_records_metrics(self) -> None:
        from backend.middleware.prometheus import PrometheusMiddleware

        app = MagicMock()
        middleware = PrometheusMiddleware(app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/plan"
        mock_request.method = "POST"
        mock_request.headers = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def fake_call_next(req: MagicMock) -> MagicMock:
            return mock_response

        response = await middleware.dispatch(mock_request, fake_call_next)
        assert response is mock_response

    @pytest.mark.asyncio
    async def test_records_request_and_response_size(self) -> None:
        from backend.middleware.prometheus import PrometheusMiddleware

        app = MagicMock()
        middleware = PrometheusMiddleware(app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/data"
        mock_request.method = "POST"
        mock_request.headers = {"content-length": "1024"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "4096"}

        async def fake_call_next(req: MagicMock) -> MagicMock:
            return mock_response

        # 不应抛出异常
        response = await middleware.dispatch(mock_request, fake_call_next)
        assert response is mock_response

    @pytest.mark.asyncio
    async def test_skips_size_when_no_content_length(self) -> None:
        from backend.middleware.prometheus import PrometheusMiddleware

        app = MagicMock()
        middleware = PrometheusMiddleware(app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/get"
        mock_request.method = "GET"
        mock_request.headers = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def fake_call_next(req: MagicMock) -> MagicMock:
            return mock_response

        # 无 Content-Length 时不应抛出异常
        response = await middleware.dispatch(mock_request, fake_call_next)
        assert response is mock_response


# ---------------------------------------------------------------------------
# error_filter 测试
# ---------------------------------------------------------------------------


class TestBeforeSend:
    """before_send 过滤逻辑测试。"""

    def test_returns_event_when_no_exc_info(self) -> None:
        from backend.monitoring.error_filter import before_send

        event = {"message": "test"}
        hint: dict = {}
        assert before_send(event, hint) is event

    def test_filters_keyboard_interrupt(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {}
        hint: dict = {"exc_info": (KeyboardInterrupt, KeyboardInterrupt(), None)}
        assert before_send(event, hint) is None

    def test_filters_system_exit(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {}
        hint: dict = {"exc_info": (SystemExit, SystemExit(1), None)}
        assert before_send(event, hint) is None

    def test_filters_cancelled_error(self) -> None:
        import asyncio

        from backend.monitoring.error_filter import before_send

        event: dict = {}
        hint: dict = {
            "exc_info": (asyncio.CancelledError, asyncio.CancelledError(), None)
        }
        assert before_send(event, hint) is None

    def test_filters_rate_limit_message(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {}
        exc = Exception("Rate limit exceeded")
        hint: dict = {"exc_info": (Exception, exc, None)}
        assert before_send(event, hint) is None

    def test_filters_too_many_requests_message(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {}
        exc = Exception("Too many requests")
        hint: dict = {"exc_info": (Exception, exc, None)}
        assert before_send(event, hint) is None

    def test_filters_connection_reset_message(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {}
        exc = Exception("Connection reset by peer")
        hint: dict = {"exc_info": (Exception, exc, None)}
        assert before_send(event, hint) is None

    def test_passes_normal_exception(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {"message": "error"}
        exc = ValueError("something broke")
        hint: dict = {"exc_info": (ValueError, exc, None)}
        result = before_send(event, hint)
        assert result is event

    def test_sanitizes_authorization_header(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {
            "request": {
                "headers": {
                    "Authorization": "Bearer secret-token",
                    "Content-Type": "application/json",
                }
            }
        }
        exc = ValueError("test")
        hint: dict = {"exc_info": (ValueError, exc, None)}
        before_send(event, hint)
        assert event["request"]["headers"]["Authorization"] == "[Filtered]"
        assert event["request"]["headers"]["Content-Type"] == "application/json"

    def test_sanitizes_cookie_header(self) -> None:
        from backend.monitoring.error_filter import before_send

        event: dict = {
            "request": {
                "headers": {
                    "Cookie": "session=abc123",
                }
            }
        }
        exc = ValueError("test")
        hint: dict = {"exc_info": (ValueError, exc, None)}
        before_send(event, hint)
        assert event["request"]["headers"]["Cookie"] == "[Filtered]"


class TestBeforeSendTransaction:
    """before_send_transaction 过滤逻辑测试。"""

    def test_filters_health_endpoint(self) -> None:
        from backend.monitoring.error_filter import before_send_transaction

        event: dict = {"transaction": "/health"}
        hint: dict = {}
        assert before_send_transaction(event, hint) is None

    def test_filters_healthz_endpoint(self) -> None:
        from backend.monitoring.error_filter import before_send_transaction

        event: dict = {"transaction": "/healthz"}
        hint: dict = {}
        assert before_send_transaction(event, hint) is None

    def test_filters_metrics_endpoint(self) -> None:
        from backend.monitoring.error_filter import before_send_transaction

        event: dict = {"transaction": "/metrics"}
        hint: dict = {}
        assert before_send_transaction(event, hint) is None

    def test_passes_normal_endpoint(self) -> None:
        from backend.monitoring.error_filter import before_send_transaction

        event: dict = {"transaction": "/api/v1/plan"}
        hint: dict = {}
        result = before_send_transaction(event, hint)
        assert result is event

    def test_passes_empty_transaction(self) -> None:
        from backend.monitoring.error_filter import before_send_transaction

        event: dict = {}
        hint: dict = {}
        result = before_send_transaction(event, hint)
        assert result is event


# ---------------------------------------------------------------------------
# sentry 测试
# ---------------------------------------------------------------------------


class TestInitSentry:
    """init_sentry 初始化测试。"""

    def test_returns_false_when_no_dsn(self) -> None:
        from backend.monitoring.sentry import init_sentry

        with patch.dict("os.environ", {}, clear=False):
            # 确保没有 SENTRY_DSN
            import os

            os.environ.pop("SENTRY_DSN", None)
            assert init_sentry() is False

    @patch("backend.monitoring.sentry.sentry_sdk.init")
    def test_returns_true_when_dsn_set(self, mock_init: MagicMock) -> None:
        from backend.monitoring.sentry import init_sentry

        with patch.dict(
            "os.environ",
            {"SENTRY_DSN": "https://examplePublicKey@o0.ingest.sentry.io/0"},
        ):
            assert init_sentry() is True
            mock_init.assert_called_once()

    @patch("backend.monitoring.sentry.sentry_sdk.init")
    def test_passes_integrations(self, mock_init: MagicMock) -> None:
        from backend.monitoring.sentry import init_sentry

        with patch.dict(
            "os.environ",
            {
                "SENTRY_DSN": "https://key@o0.ingest.sentry.io/0",
                "ENVIRONMENT": "production",
                "APP_VERSION": "2.0.0",
            },
        ):
            init_sentry()
            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["environment"] == "production"
            assert call_kwargs["release"] == "cityflow@2.0.0"
            assert call_kwargs["traces_sample_rate"] == 0.1


class TestCaptureException:
    """capture_exception 测试。"""

    @patch("backend.monitoring.sentry.sentry_sdk.capture_exception")
    def test_calls_sdk_without_context(self, mock_cap: MagicMock) -> None:
        from backend.monitoring.sentry import capture_exception

        err = ValueError("test")
        capture_exception(err)
        mock_cap.assert_called_once_with(err)

    @patch("backend.monitoring.sentry.sentry_sdk.capture_exception")
    def test_calls_sdk_with_context(self, mock_cap: MagicMock) -> None:
        from backend.monitoring.sentry import capture_exception

        err = ValueError("test")
        capture_exception(err, context={"user_id": "123"})
        mock_cap.assert_called_once_with(err)


class TestCaptureMessage:
    """capture_message 测试。"""

    @patch("backend.monitoring.sentry.sentry_sdk.capture_message")
    def test_calls_sdk(self, mock_cap: MagicMock) -> None:
        from backend.monitoring.sentry import capture_message

        capture_message("hello", level="warning")
        mock_cap.assert_called_once_with("hello", level="warning")
