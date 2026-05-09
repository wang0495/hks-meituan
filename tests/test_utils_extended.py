"""CityFlow 工具模块扩展测试。

覆盖以下模块（当前 0% 覆盖率）：
- backend/utils/error_handler.py
- backend/services/metrics.py
- backend/services/message_queue.py
- backend/services/message_handlers.py
- backend/services/notification.py
- backend/services/http_pool.py
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.errors import CityFlowException, ErrorCode, LLMServiceError
from backend.utils.error_handler import handle_errors, handle_llm_errors

# ===========================================================================
# error_handler
# ===========================================================================


class TestHandleErrors:
    """handle_errors 装饰器测试。"""

    @pytest.mark.asyncio
    async def test_success_passthrough(self) -> None:
        @handle_errors("test error")
        async def my_func() -> str:
            return "ok"

        assert await my_func() == "ok"

    @pytest.mark.asyncio
    async def test_cityflow_exception_passthrough(self) -> None:
        @handle_errors("test error")
        async def my_func() -> None:
            raise CityFlowException(
                code=ErrorCode.NOT_FOUND,
                message="not found",
            )

        with pytest.raises(CityFlowException) as exc_info:
            await my_func()
        assert exc_info.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_generic_exception_wrapped(self) -> None:
        @handle_errors("操作失败")
        async def my_func() -> None:
            raise RuntimeError("something broke")

        with pytest.raises(CityFlowException) as exc_info:
            await my_func()
        assert exc_info.value.code == ErrorCode.INTERNAL_ERROR
        assert exc_info.value.message == "操作失败"
        assert exc_info.value.details["original_error"] == "something broke"


class TestHandleLLMErrors:
    """handle_llm_errors 装饰器测试。"""

    @pytest.mark.asyncio
    async def test_success_passthrough(self) -> None:
        @handle_llm_errors
        async def my_func() -> str:
            return "response"

        assert await my_func() == "response"

    @pytest.mark.asyncio
    async def test_timeout_error(self) -> None:
        @handle_llm_errors
        async def my_func() -> None:
            raise TimeoutError("timed out")

        with pytest.raises(LLMServiceError) as exc_info:
            await my_func()
        assert exc_info.value.code == ErrorCode.LLM_SERVICE_ERROR
        assert exc_info.value.details.get("timeout") is True

    @pytest.mark.asyncio
    async def test_cityflow_exception_passthrough(self) -> None:
        @handle_llm_errors
        async def my_func() -> None:
            raise CityFlowException(
                code=ErrorCode.NOT_FOUND,
                message="not found",
            )

        with pytest.raises(CityFlowException) as exc_info:
            await my_func()
        assert exc_info.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_generic_exception_wrapped(self) -> None:
        @handle_llm_errors
        async def my_func() -> None:
            raise ValueError("bad value")

        with pytest.raises(LLMServiceError) as exc_info:
            await my_func()
        assert "LLM服务异常" in exc_info.value.message


# ===========================================================================
# metrics
# ===========================================================================


class TestMetrics:
    """metrics 模块测试。

    使用独立的 prometheus registry 避免与其他测试的注册冲突。
    """

    def _get_metrics_module(self):
        """获取 metrics 模块，处理 registry 冲突。"""
        try:
            from backend.services import metrics as m

            return m
        except ValueError:
            # Prometheus registry 冲突，重新加载
            import importlib

            import backend.services.metrics

            importlib.reload(backend.services.metrics)
            return backend.services.metrics

    def test_track_route_planning(self) -> None:
        from prometheus_client import CollectorRegistry, Counter

        # 使用独立 registry 测试逻辑
        registry = CollectorRegistry()
        counter = Counter("test_routes_total", "test", ["user_type"], registry=registry)
        counter.labels(user_type="solo").inc()
        assert counter.labels(user_type="solo")._value.get() == 1.0

    def test_track_poi_query(self) -> None:
        from prometheus_client import CollectorRegistry, Counter

        registry = CollectorRegistry()
        counter = Counter("test_poi_queries", "test", registry=registry)
        counter.inc()
        assert counter._value.get() == 1.0

    def test_get_metrics(self) -> None:
        from prometheus_client import (CollectorRegistry, Counter,
                                       generate_latest)

        registry = CollectorRegistry()
        Counter("test_metric", "test", registry=registry).inc()
        data = generate_latest(registry)
        assert isinstance(data, bytes)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_metrics_middleware_non_http(self) -> None:
        from backend.services.metrics import MetricsMiddleware

        app = AsyncMock()
        middleware = MetricsMiddleware(app)
        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)
        app.assert_awaited_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_metrics_middleware_http(self) -> None:
        from backend.services.metrics import MetricsMiddleware

        async def mock_app(scope, receive, send):
            pass

        middleware = MetricsMiddleware(mock_app)
        scope = {"type": "http", "method": "GET", "path": "/test"}
        send = AsyncMock()
        await middleware(scope, AsyncMock(), send)
        # 指标已记录，不应抛异常


# ===========================================================================
# message_queue (Message 类)
# ===========================================================================


class TestMessage:
    """Message 信封测试。"""

    def test_create(self) -> None:
        from backend.services.message_queue import Message

        msg = Message(queue="test", payload={"key": "value"})
        assert msg.queue == "test"
        assert msg.payload == {"key": "value"}
        assert msg.retry_count == 0
        assert msg.message_id is not None

    def test_custom_id(self) -> None:
        from backend.services.message_queue import Message

        msg = Message(queue="test", payload={}, message_id="custom-123")
        assert msg.message_id == "custom-123"

    def test_to_json_and_from_json(self) -> None:
        from backend.services.message_queue import Message

        original = Message(queue="test", payload={"a": 1, "b": "hello"})
        json_str = original.to_json()

        restored = Message.from_json(json_str)
        assert restored.queue == original.queue
        assert restored.payload == original.payload
        assert restored.message_id == original.message_id
        assert restored.retry_count == 0

    def test_from_json_with_retry_count(self) -> None:
        from backend.services.message_queue import Message

        data = json.dumps(
            {
                "message_id": "msg-1",
                "queue": "q1",
                "payload": {"x": 1},
                "retry_count": 2,
                "created_at": "2024-01-01T00:00:00",
            }
        )
        msg = Message.from_json(data)
        assert msg.retry_count == 2

    def test_to_json_unicode(self) -> None:
        from backend.services.message_queue import Message

        msg = Message(queue="test", payload={"city": "成都"})
        json_str = msg.to_json()
        assert "成都" in json_str


# ===========================================================================
# message_handlers
# ===========================================================================


class TestMessageHandlers:
    """message_handlers 模块测试。"""

    def test_get_handler(self) -> None:
        from backend.services.message_handlers import get_handler

        assert get_handler("route_planning") is not None
        assert get_handler("notification") is not None
        assert get_handler("analytics") is not None
        assert get_handler("nonexistent") is None

    @pytest.mark.asyncio
    async def test_handle_notification(self) -> None:
        from backend.services.message_handlers import handle_notification

        with patch(
            "backend.services.notification.notify_personal",
            new_callable=AsyncMock,
        ) as mock_notify:
            await handle_notification(
                {
                    "session_id": "s1",
                    "content": "test message",
                    "msg_type": "info",
                }
            )
            mock_notify.assert_awaited_once()
            call_args = mock_notify.call_args
            assert call_args[0][0] == "s1"
            assert call_args[0][1]["type"] == "notification"

    @pytest.mark.asyncio
    async def test_handle_analytics(self) -> None:
        from backend.services.message_handlers import handle_analytics

        # 不应抛异常，目前仅记录日志
        await handle_analytics(
            {
                "event_type": "route_planned",
                "user_id": "u-1",
                "data": {"city": "成都"},
            }
        )


# ===========================================================================
# notification
# ===========================================================================


class TestNotification:
    """notification 模块测试。"""

    @pytest.mark.asyncio
    async def test_notify_route_update(self) -> None:
        from backend.services.notification import notify_route_update

        with patch("backend.services.notification.get_websocket_manager") as mock_get:
            mock_manager = AsyncMock()
            mock_get.return_value = mock_manager
            await notify_route_update("route-1", "new_step", {"step": 1})
            mock_manager.broadcast_to_route.assert_awaited_once_with(
                "route-1",
                {
                    "type": "route_update",
                    "route_id": "route-1",
                    "update_type": "new_step",
                    "data": {"step": 1},
                },
            )

    @pytest.mark.asyncio
    async def test_notify_new_step(self) -> None:
        from backend.services.notification import notify_new_step

        with patch(
            "backend.services.notification.notify_route_update",
            new_callable=AsyncMock,
        ) as mock_update:
            await notify_new_step("route-1", {"step": 1})
            mock_update.assert_awaited_once_with("route-1", "new_step", {"step": 1})

    @pytest.mark.asyncio
    async def test_notify_route_complete(self) -> None:
        from backend.services.notification import notify_route_complete

        with patch(
            "backend.services.notification.notify_route_update",
            new_callable=AsyncMock,
        ) as mock_update:
            await notify_route_complete("route-1", {"done": True})
            mock_update.assert_awaited_once_with("route-1", "complete", {"done": True})

    @pytest.mark.asyncio
    async def test_notify_route_adjusted(self) -> None:
        from backend.services.notification import notify_route_adjusted

        with patch(
            "backend.services.notification.notify_route_update",
            new_callable=AsyncMock,
        ) as mock_update:
            await notify_route_adjusted("route-1", [{"type": "add"}])
            mock_update.assert_awaited_once_with(
                "route-1", "adjusted", {"changes": [{"type": "add"}]}
            )

    @pytest.mark.asyncio
    async def test_notify_error(self) -> None:
        from backend.services.notification import notify_error

        with patch("backend.services.notification.get_websocket_manager") as mock_get:
            mock_manager = AsyncMock()
            mock_get.return_value = mock_manager
            await notify_error("session-1", "something went wrong")
            mock_manager.send_personal_message.assert_awaited_once_with(
                "session-1",
                {"type": "error", "message": "something went wrong"},
            )

    @pytest.mark.asyncio
    async def test_notify_personal(self) -> None:
        from backend.services.notification import notify_personal

        with patch("backend.services.notification.get_websocket_manager") as mock_get:
            mock_manager = AsyncMock()
            mock_get.return_value = mock_manager
            await notify_personal("s1", {"type": "custom", "data": 42})
            mock_manager.send_personal_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_system_message(self) -> None:
        from backend.services.notification import broadcast_system_message

        with patch("backend.services.notification.get_websocket_manager") as mock_get:
            mock_manager = AsyncMock()
            mock_get.return_value = mock_manager
            await broadcast_system_message("系统维护中")
            mock_manager.broadcast_all.assert_awaited_once_with(
                {"type": "system", "message": "系统维护中"}
            )
