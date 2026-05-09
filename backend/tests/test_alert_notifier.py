"""告警通知器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.alert_notifier import (ALERT_EVENT_TYPE, AlertNotifier,
                                             get_alert_notifier,
                                             reset_alert_notifier)
from backend.services.resource_monitor import AlertEvent, AlertSeverity


class TestAlertNotifierHandleAlert:
    """测试 handle_alert 方法（三参数签名）。"""

    @pytest.mark.asyncio
    async def test_handle_alert_increments_count(self) -> None:
        notifier = AlertNotifier()
        with patch.object(notifier, "_publish_event", new_callable=AsyncMock):
            await notifier.handle_alert("high_cpu", 90.0, 80.0)
            await notifier.handle_alert("high_mem", 95.0, 85.0)
        assert notifier.notification_count == 2

    @pytest.mark.asyncio
    async def test_handle_alert_publishes_event(self) -> None:
        notifier = AlertNotifier()
        mock_publish = AsyncMock()
        with patch.object(notifier, "_publish_event", mock_publish):
            await notifier.handle_alert("high_cpu", 90.0, 80.0)

        mock_publish.assert_called_once()
        call_kwargs = mock_publish.call_args
        assert call_kwargs.kwargs["event_type"] == ALERT_EVENT_TYPE
        data = call_kwargs.kwargs["data"]
        assert data["rule_name"] == "high_cpu"
        assert data["current_value"] == 90.0
        assert data["threshold"] == 80.0


class TestAlertNotifierHandleAlertEvent:
    """测试 handle_alert_event 方法（AlertEvent 对象签名）。"""

    @pytest.mark.asyncio
    async def test_handle_alert_event_increments_count(self) -> None:
        notifier = AlertNotifier()
        event = AlertEvent(
            rule_name="high_cpu",
            metric="cpu_percent",
            current_value=90.0,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            message="test",
        )
        with patch.object(notifier, "_publish_event", new_callable=AsyncMock):
            await notifier.handle_alert_event(event)
        assert notifier.notification_count == 1

    @pytest.mark.asyncio
    async def test_handle_critical_event_uses_critical_log(self) -> None:
        notifier = AlertNotifier()
        event = AlertEvent(
            rule_name="critical_cpu",
            metric="cpu_percent",
            current_value=99.0,
            threshold=95.0,
            severity=AlertSeverity.CRITICAL,
            message="critical test",
        )
        with (
            patch.object(notifier, "_publish_event", new_callable=AsyncMock),
            patch("backend.services.alert_notifier.logger") as mock_logger,
        ):
            await notifier.handle_alert_event(event)
            mock_logger.critical.assert_called_once()


class TestConvenienceMethods:
    """测试 send_info / send_warning / send_critical。"""

    @pytest.mark.asyncio
    async def test_send_info(self) -> None:
        notifier = AlertNotifier()
        with patch.object(
            notifier, "_publish_event", new_callable=AsyncMock
        ) as mock_pub:
            await notifier.send_info("info message", extra_key="value")
        mock_pub.assert_called_once()
        data = mock_pub.call_args.kwargs["data"]
        assert data["level"] == "info"
        assert data["message"] == "info message"
        assert data["extra_key"] == "value"

    @pytest.mark.asyncio
    async def test_send_warning(self) -> None:
        notifier = AlertNotifier()
        with patch.object(
            notifier, "_publish_event", new_callable=AsyncMock
        ) as mock_pub:
            await notifier.send_warning("warning message")
        data = mock_pub.call_args.kwargs["data"]
        assert data["level"] == "warning"

    @pytest.mark.asyncio
    async def test_send_critical(self) -> None:
        notifier = AlertNotifier()
        with patch.object(
            notifier, "_publish_event", new_callable=AsyncMock
        ) as mock_pub:
            await notifier.send_critical("critical message")
        data = mock_pub.call_args.kwargs["data"]
        assert data["level"] == "critical"


class TestPublishEvent:
    """测试事件总线发布集成。"""

    @pytest.mark.asyncio
    async def test_publish_event_calls_event_bus(self) -> None:
        notifier = AlertNotifier()
        mock_bus = AsyncMock()
        with patch(
            "backend.services.alert_notifier.get_event_bus", return_value=mock_bus
        ):
            await notifier.send_info("test")

        mock_bus.publish_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_exception_does_not_raise(self) -> None:
        """事件总线异常不应中断通知器。"""
        notifier = AlertNotifier()
        with patch(
            "backend.services.alert_notifier.get_event_bus",
            side_effect=RuntimeError("bus down"),
        ):
            # 不应抛出异常
            await notifier.handle_alert("high_cpu", 90.0, 80.0)

        assert notifier.notification_count == 1


class TestGetStatus:
    def test_initial_status(self) -> None:
        notifier = AlertNotifier()
        status = notifier.get_status()
        assert status["notification_count"] == 0


# ---------------------------------------------------------------------------
# 全局单例测试
# ---------------------------------------------------------------------------


class TestAlertNotifierSingleton:
    def test_singleton(self) -> None:
        reset_alert_notifier()
        try:
            n1 = get_alert_notifier()
            n2 = get_alert_notifier()
            assert n1 is n2
        finally:
            reset_alert_notifier()

    def test_reset_creates_new(self) -> None:
        reset_alert_notifier()
        try:
            n1 = get_alert_notifier()
            reset_alert_notifier()
            n2 = get_alert_notifier()
            assert n1 is not n2
        finally:
            reset_alert_notifier()
