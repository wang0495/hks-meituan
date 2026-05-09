"""CityFlow 事件系统测试。

覆盖以下模块（当前 0% 覆盖率）：
- backend/services/event_bus.py
- backend/events/types.py
- backend/events/decorators.py
- backend/events/handlers.py
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.events.types import (EventType, RouteAdjustedEvent,
                                  RoutePlannedEvent, SystemErrorEvent,
                                  UserFeedbackEvent)
from backend.services.event_bus import (Event, EventBus, get_event_bus,
                                        reset_event_bus)

# ===========================================================================
# Event
# ===========================================================================


class TestEvent:
    """Event 数据类测试。"""

    def test_default_values(self) -> None:
        e = Event()
        assert e.event_type == ""
        assert e.data == {}
        assert e.source == ""
        assert e.timestamp is not None

    def test_custom_values(self) -> None:
        e = Event(
            event_type="test.event",
            data={"key": "value"},
            source="test",
        )
        assert e.event_type == "test.event"
        assert e.data == {"key": "value"}
        assert e.source == "test"

    def test_data_default_factory(self) -> None:
        e1 = Event()
        e2 = Event()
        assert e1.data is not e2.data


# ===========================================================================
# EventBus
# ===========================================================================


class TestEventBus:
    """EventBus 测试。"""

    def setup_method(self) -> None:
        self.bus = EventBus()

    def test_subscribe_and_publish(self) -> None:
        received: list[Event] = []

        def handler(event: Event) -> None:
            received.append(event)

        self.bus.subscribe("test.event", handler)
        event = Event(event_type="test.event", data={"x": 1})
        self.bus.publish(event)

        assert len(received) == 1
        assert received[0].data == {"x": 1}

    def test_multiple_subscribers(self) -> None:
        results: list[str] = []

        def handler_a(event: Event) -> None:
            results.append("a")

        def handler_b(event: Event) -> None:
            results.append("b")

        self.bus.subscribe("test.event", handler_a)
        self.bus.subscribe("test.event", handler_b)
        self.bus.publish(Event(event_type="test.event"))

        assert results == ["a", "b"]

    def test_publish_no_subscribers(self) -> None:
        # 不应抛异常
        self.bus.publish(Event(event_type="no.handlers"))

    def test_publish_handler_exception_isolated(self) -> None:
        results: list[str] = []

        def bad_handler(event: Event) -> None:
            raise RuntimeError("boom")

        def good_handler(event: Event) -> None:
            results.append("ok")

        self.bus.subscribe("test.event", bad_handler)
        self.bus.subscribe("test.event", good_handler)
        self.bus.publish(Event(event_type="test.event"))

        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_subscribe_async_and_publish(self) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        self.bus.subscribe_async("test.async", handler)
        await self.bus.publish_async(Event(event_type="test.async", data={"y": 2}))

        assert len(received) == 1
        assert received[0].data == {"y": 2}

    @pytest.mark.asyncio
    async def test_publish_async_no_subscribers(self) -> None:
        await self.bus.publish_async(Event(event_type="no.handlers"))

    @pytest.mark.asyncio
    async def test_publish_async_handler_exception_isolated(self) -> None:
        results: list[str] = []

        async def bad_handler(event: Event) -> None:
            raise RuntimeError("async boom")

        async def good_handler(event: Event) -> None:
            results.append("ok")

        self.bus.subscribe_async("test.async", bad_handler)
        self.bus.subscribe_async("test.async", good_handler)
        await self.bus.publish_async(Event(event_type="test.async"))

        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_publish_async_sync_handler_in_async_list(self) -> None:
        """同步处理器注册到异步列表也能正常执行。"""
        results: list[str] = []

        def sync_handler(event: Event) -> None:
            results.append("sync")

        self.bus.subscribe_async("test.mixed", sync_handler)
        await self.bus.publish_async(Event(event_type="test.mixed"))

        assert results == ["sync"]

    def test_unsubscribe(self) -> None:
        results: list[str] = []

        def handler(event: Event) -> None:
            results.append("called")

        self.bus.subscribe("test.event", handler)
        self.bus.publish(Event(event_type="test.event"))
        assert results == ["called"]

        self.bus.unsubscribe("test.event", handler)
        self.bus.publish(Event(event_type="test.event"))
        assert len(results) == 1  # 不再被调用

    def test_unsubscribe_nonexistent(self) -> None:
        # 不应抛异常
        self.bus.unsubscribe("no.event", lambda e: None)

    def test_get_subscribers(self) -> None:
        def h1(e: Event) -> None:
            pass

        async def h2(e: Event) -> None:
            pass

        self.bus.subscribe("test", h1)
        self.bus.subscribe_async("test", h2)
        subs = self.bus.get_subscribers("test")
        assert len(subs) == 2

    def test_event_types(self) -> None:
        self.bus.subscribe("type.a", lambda e: None)
        self.bus.subscribe_async("type.b", lambda e: None)
        types = self.bus.event_types()
        assert set(types) == {"type.a", "type.b"}

    def test_clear(self) -> None:
        self.bus.subscribe("a", lambda e: None)
        self.bus.subscribe_async("b", lambda e: None)
        self.bus.clear()
        assert self.bus.event_types() == []


class TestGlobalEventBus:
    """全局事件总线单例测试。"""

    def setup_method(self) -> None:
        reset_event_bus()

    def teardown_method(self) -> None:
        reset_event_bus()

    def test_get_event_bus_singleton(self) -> None:
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_event_bus(self) -> None:
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2


# ===========================================================================
# Event Types
# ===========================================================================


class TestEventType:
    """EventType 枚举测试。"""

    def test_route_events(self) -> None:
        assert EventType.ROUTE_PLANNED == "route.planned"
        assert EventType.ROUTE_ADJUSTED == "route.adjusted"
        assert EventType.ROUTE_COMPLETED == "route.completed"
        assert EventType.ROUTE_FAILED == "route.failed"

    def test_user_events(self) -> None:
        assert EventType.USER_FEEDBACK == "user.feedback"
        assert EventType.USER_MESSAGE == "user.message"

    def test_system_events(self) -> None:
        assert EventType.SYSTEM_ERROR == "system.error"
        assert EventType.SYSTEM_STARTUP == "system.startup"
        assert EventType.SYSTEM_SHUTDOWN == "system.shutdown"

    def test_is_str(self) -> None:
        assert isinstance(EventType.ROUTE_PLANNED, str)


class TestEventSubclasses:
    """事件子类测试。"""

    def test_route_planned_event(self) -> None:
        e = RoutePlannedEvent(route_id="r-001", user_id="u-42")
        assert e.event_type == EventType.ROUTE_PLANNED
        assert e.route_id == "r-001"
        assert e.user_id == "u-42"

    def test_route_adjusted_event(self) -> None:
        e = RouteAdjustedEvent(route_id="r-002", adjustment_type="add_stop")
        assert e.event_type == EventType.ROUTE_ADJUSTED
        assert e.adjustment_type == "add_stop"

    def test_user_feedback_event(self) -> None:
        e = UserFeedbackEvent(
            user_id="u-10",
            feedback_type="rating",
            content="great route",
        )
        assert e.event_type == EventType.USER_FEEDBACK
        assert e.content == "great route"

    def test_system_error_event(self) -> None:
        e = SystemErrorEvent(
            error_type="TimeoutError",
            message="service timeout",
            stack_trace="traceback...",
        )
        assert e.event_type == EventType.SYSTEM_ERROR
        assert e.error_type == "TimeoutError"

    def test_all_subclasses_inherit_event(self) -> None:
        for cls in [
            RoutePlannedEvent,
            RouteAdjustedEvent,
            UserFeedbackEvent,
            SystemErrorEvent,
        ]:
            e = cls()
            assert isinstance(e, Event)


# ===========================================================================
# Event Decorators
# ===========================================================================


class TestEmitEventDecorator:
    """emit_event 装饰器测试。"""

    def setup_method(self) -> None:
        reset_event_bus()

    def teardown_method(self) -> None:
        reset_event_bus()

    @pytest.mark.asyncio
    async def test_async_emit_default_data(self) -> None:
        from backend.events.decorators import emit_event

        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus = get_event_bus()
        bus.subscribe_async("test.emit", handler)

        @emit_event("test.emit")
        async def my_func(x: int) -> dict:
            return {"result": x * 2}

        result = await my_func(5)
        assert result == {"result": 10}
        assert len(received) == 1
        # 默认 data_fn 包装为 {"result": return_value}
        assert received[0].data == {"result": {"result": 10}}

    def test_sync_emit_default_data(self) -> None:
        from backend.events.decorators import emit_event

        received: list[Event] = []

        def handler(event: Event) -> None:
            received.append(event)

        bus = get_event_bus()
        bus.subscribe("test.emit", handler)

        @emit_event("test.emit")
        def my_func(x: int) -> dict:
            return {"result": x}

        result = my_func(3)
        assert result == {"result": 3}
        assert len(received) == 1
        # 默认 data_fn 包装为 {"result": return_value}
        assert received[0].data == {"result": {"result": 3}}

    @pytest.mark.asyncio
    async def test_async_emit_custom_data_fn(self) -> None:
        from backend.events.decorators import emit_event

        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus = get_event_bus()
        bus.subscribe_async("test.custom", handler)

        def extract(result, *args, **kwargs):
            return {"custom": result, "input": args[0]}

        @emit_event("test.custom", data_fn=extract)
        async def my_func(name: str) -> str:
            return f"hello {name}"

        await my_func("world")
        assert len(received) == 1
        assert received[0].data == {"custom": "hello world", "input": "world"}


# ===========================================================================
# Event Handlers
# ===========================================================================


class TestEventHandlers:
    """事件处理器注册测试。"""

    def setup_method(self) -> None:
        reset_event_bus()

    def teardown_method(self) -> None:
        reset_event_bus()

    def test_setup_event_handlers(self) -> None:
        from backend.events.handlers import setup_event_handlers

        setup_event_handlers()
        bus = get_event_bus()
        types = bus.event_types()
        assert "route.planned" in types
        assert "system.error" in types
        assert "user.feedback" in types

    def test_handle_route_planned_metrics(self) -> None:
        from backend.events.handlers import handle_route_planned_metrics

        event = Event(event_type="route.planned", data={"user_type": "solo"})
        # track_route_planning 通过本地导入使用，mock 在 metrics 模块级别
        import backend.services.metrics as metrics_mod

        original = getattr(metrics_mod, "track_route_planning", None)
        mock_track = MagicMock()
        metrics_mod.track_route_planning = mock_track
        try:
            handle_route_planned_metrics(event)
            mock_track.assert_called_once_with("solo")
        finally:
            if original is not None:
                metrics_mod.track_route_planning = original

    def test_handle_system_error_alert(self) -> None:
        from backend.events.handlers import handle_system_error_alert

        event = Event(
            event_type="system.error",
            data={"error_type": "Timeout", "message": "service X timeout"},
        )
        # 不应抛异常
        handle_system_error_alert(event)

    @pytest.mark.asyncio
    async def test_handle_user_feedback_record(self) -> None:
        from backend.events.handlers import handle_user_feedback_record

        event = Event(
            event_type="user.feedback",
            data={
                "user_id": "u-1",
                "feedback_type": "rating",
                "content": "great!",
            },
        )
        # 不应抛异常
        await handle_user_feedback_record(event)
