"""CityFlow 服务基础设施测试。

覆盖以下模块（当前 0% 覆盖率）：
- backend/services/registry.py
- backend/services/discovery.py
- backend/services/websocket.py
- backend/di/container.py
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.di.container import DIContainer
from backend.di.container import \
    ServiceNotFoundError as DIServiceNotFoundError  # noqa: E402
from backend.di.container import get_container, inject, reset_container
from backend.services.discovery import ServiceDiscovery, ServiceNotFoundError
from backend.services.registry import (ServiceInfo, ServiceRegistry,
                                       get_service_registry)
from backend.services.websocket import ConnectionManager, get_websocket_manager

# ===========================================================================
# ServiceInfo
# ===========================================================================


class TestServiceInfo:
    """ServiceInfo 模型测试。"""

    def test_create(self) -> None:
        s = ServiceInfo(
            service_id="s-001",
            service_name="user-service",
            host="127.0.0.1",
            port=8080,
        )
        assert s.service_id == "s-001"
        assert s.service_name == "user-service"
        assert s.host == "127.0.0.1"
        assert s.port == 8080
        assert s.status == "healthy"

    def test_to_dict(self) -> None:
        s = ServiceInfo(
            service_id="s-001",
            service_name="user-service",
            host="127.0.0.1",
            port=8080,
            metadata={"version": "1.0"},
        )
        d = s.to_dict()
        assert d["service_id"] == "s-001"
        assert d["metadata"] == {"version": "1.0"}
        assert "registered_at" in d
        assert "last_heartbeat" in d

    def test_default_metadata(self) -> None:
        s = ServiceInfo(
            service_id="s-001",
            service_name="test",
            host="localhost",
            port=80,
        )
        assert s.metadata == {}


# ===========================================================================
# ServiceRegistry
# ===========================================================================


class TestServiceRegistry:
    """ServiceRegistry 测试。"""

    def setup_method(self) -> None:
        self.registry = ServiceRegistry(
            heartbeat_timeout=60,
            health_check_interval=10,
        )

    @pytest.mark.asyncio
    async def test_register_and_get_service(self) -> None:
        svc = ServiceInfo(
            service_id="s-001",
            service_name="user-service",
            host="127.0.0.1",
            port=8080,
        )
        await self.registry.register(svc)
        found = await self.registry.get_service("user-service")
        assert found is not None
        assert found.service_id == "s-001"

    @pytest.mark.asyncio
    async def test_get_service_not_found(self) -> None:
        found = await self.registry.get_service("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_deregister(self) -> None:
        svc = ServiceInfo(
            service_id="s-001",
            service_name="test",
            host="localhost",
            port=80,
        )
        await self.registry.register(svc)
        result = await self.registry.deregister("s-001")
        assert result is True
        assert await self.registry.get_service("test") is None

    @pytest.mark.asyncio
    async def test_deregister_nonexistent(self) -> None:
        result = await self.registry.deregister("no-such-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_heartbeat(self) -> None:
        svc = ServiceInfo(
            service_id="s-001",
            service_name="test",
            host="localhost",
            port=80,
        )
        await self.registry.register(svc)
        result = await self.registry.heartbeat("s-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_heartbeat_nonexistent(self) -> None:
        result = await self.registry.heartbeat("no-such")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_services(self) -> None:
        svc1 = ServiceInfo(service_id="s1", service_name="a", host="h", port=1)
        svc2 = ServiceInfo(service_id="s2", service_name="b", host="h", port=2)
        await self.registry.register(svc1)
        await self.registry.register(svc2)

        all_svcs = await self.registry.get_all_services()
        assert len(all_svcs) == 2

        filtered = await self.registry.get_all_services("a")
        assert len(filtered) == 1
        assert filtered[0].service_id == "s1"

    @pytest.mark.asyncio
    async def test_remove_unhealthy(self) -> None:
        svc = ServiceInfo(
            service_id="s-001",
            service_name="test",
            host="localhost",
            port=80,
            status="unhealthy",
        )
        await self.registry.register(svc)
        removed = await self.registry.remove_unhealthy()
        assert removed == 1
        assert self.registry.service_count == 0

    @pytest.mark.asyncio
    async def test_remove_unhealthy_filtered(self) -> None:
        svc1 = ServiceInfo(
            service_id="s1", service_name="a", host="h", port=1, status="unhealthy"
        )
        svc2 = ServiceInfo(
            service_id="s2", service_name="b", host="h", port=2, status="unhealthy"
        )
        await self.registry.register(svc1)
        await self.registry.register(svc2)
        removed = await self.registry.remove_unhealthy("a")
        assert removed == 1
        assert self.registry.service_count == 1

    def test_service_count(self) -> None:
        assert self.registry.service_count == 0

    def test_healthy_count(self) -> None:
        assert self.registry.healthy_count == 0

    @pytest.mark.asyncio
    async def test_healthy_count_with_services(self) -> None:
        svc = ServiceInfo(
            service_id="s1", service_name="a", host="h", port=1, status="healthy"
        )
        await self.registry.register(svc)
        assert self.registry.healthy_count == 1

    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        await self.registry.start()
        assert self.registry._running is True
        await self.registry.stop()
        assert self.registry._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self) -> None:
        await self.registry.start()
        await self.registry.start()  # 不应报错
        await self.registry.stop()


class TestGetServiceRegistry:
    """get_service_registry 全局单例测试。"""

    def test_returns_registry(self) -> None:
        reg = get_service_registry()
        assert isinstance(reg, ServiceRegistry)


# ===========================================================================
# ServiceDiscovery
# ===========================================================================


class TestServiceDiscovery:
    """ServiceDiscovery 测试。"""

    @pytest.mark.asyncio
    async def test_discover_from_local_registry(self) -> None:
        registry = ServiceRegistry()
        svc = ServiceInfo(
            service_id="s-001",
            service_name="my-service",
            host="10.0.0.1",
            port=9090,
        )
        await registry.register(svc)

        with patch(
            "backend.services.discovery.get_service_registry",
            return_value=registry,
        ):
            discovery = ServiceDiscovery()
            url = await discovery.discover("my-service")
            assert url == "http://10.0.0.1:9090"

    @pytest.mark.asyncio
    async def test_discover_not_found(self) -> None:
        registry = ServiceRegistry()

        with patch(
            "backend.services.discovery.get_service_registry",
            return_value=registry,
        ):
            discovery = ServiceDiscovery()
            url = await discovery.discover("nonexistent")
            assert url is None

    @pytest.mark.asyncio
    async def test_get_service_url_raises(self) -> None:
        registry = ServiceRegistry()

        with patch(
            "backend.services.discovery.get_service_registry",
            return_value=registry,
        ):
            discovery = ServiceDiscovery()
            with pytest.raises(ServiceNotFoundError):
                await discovery.get_service_url("missing")

    @pytest.mark.asyncio
    async def test_get_service_url_success(self) -> None:
        registry = ServiceRegistry()
        svc = ServiceInfo(service_id="s1", service_name="svc", host="h", port=80)
        await registry.register(svc)

        with patch(
            "backend.services.discovery.get_service_registry",
            return_value=registry,
        ):
            discovery = ServiceDiscovery()
            url = await discovery.get_service_url("svc")
            assert url == "http://h:80"


class TestServiceNotFoundError:
    """ServiceNotFoundError 测试。"""

    def test_attributes(self) -> None:
        err = ServiceNotFoundError("my-service")
        assert err.service_name == "my-service"
        assert "my-service" in str(err)


# ===========================================================================
# ConnectionManager (WebSocket)
# ===========================================================================


class TestConnectionManager:
    """ConnectionManager 测试。"""

    def setup_method(self) -> None:
        self.manager = ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect(self) -> None:
        ws = AsyncMock()
        await self.manager.connect(ws, "session-1")
        assert self.manager.is_connected("session-1")
        assert self.manager.get_connection_count() == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        ws = AsyncMock()
        await self.manager.connect(ws, "session-1")
        await self.manager.disconnect("session-1")
        assert not self.manager.is_connected("session-1")
        assert self.manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_subscriptions(self) -> None:
        ws = AsyncMock()
        await self.manager.connect(ws, "session-1")
        await self.manager.subscribe("session-1", "route-1")
        await self.manager.disconnect("session-1")
        assert self.manager.get_subscription_count() == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self) -> None:
        # 不应抛异常
        await self.manager.disconnect("no-such")

    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self) -> None:
        ws = AsyncMock()
        await self.manager.connect(ws, "s1")
        await self.manager.subscribe("s1", "route-1")
        assert self.manager.get_subscription_count() == 1
        subs = self.manager.get_subscribers("route-1")
        assert "s1" in subs

        await self.manager.unsubscribe("s1", "route-1")
        assert self.manager.get_subscription_count() == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self) -> None:
        # 不应抛异常
        await self.manager.unsubscribe("s1", "no-route")

    @pytest.mark.asyncio
    async def test_send_personal_message(self) -> None:
        ws = AsyncMock()
        await self.manager.connect(ws, "s1")
        await self.manager.send_personal_message("s1", {"type": "test"})
        ws.send_json.assert_awaited_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_send_personal_message_disconnected(self) -> None:
        # 发送给不存在的 session，不应抛异常
        await self.manager.send_personal_message("ghost", {"type": "test"})

    @pytest.mark.asyncio
    async def test_send_personal_message_failure_disconnects(self) -> None:
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("broken pipe")
        await self.manager.connect(ws, "s1")
        await self.manager.send_personal_message("s1", {"type": "test"})
        assert not self.manager.is_connected("s1")

    @pytest.mark.asyncio
    async def test_broadcast_to_route(self) -> None:
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.manager.connect(ws1, "s1")
        await self.manager.connect(ws2, "s2")
        await self.manager.subscribe("s1", "route-1")
        await self.manager.subscribe("s2", "route-1")

        await self.manager.broadcast_to_route("route-1", {"type": "update"})
        ws1.send_json.assert_awaited_once_with({"type": "update"})
        ws2.send_json.assert_awaited_once_with({"type": "update"})

    @pytest.mark.asyncio
    async def test_broadcast_all(self) -> None:
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.manager.connect(ws1, "s1")
        await self.manager.connect(ws2, "s2")

        await self.manager.broadcast_all({"type": "system", "msg": "hi"})
        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()

    def test_get_subscribers_empty(self) -> None:
        subs = self.manager.get_subscribers("no-route")
        assert subs == set()


class TestGetWebsocketManager:
    """get_websocket_manager 全局单例测试。"""

    def test_returns_manager(self) -> None:
        m = get_websocket_manager()
        assert isinstance(m, ConnectionManager)


# ===========================================================================
# DI Container
# ===========================================================================


class TestDIContainer:
    """DIContainer 测试。"""

    def setup_method(self) -> None:
        self.container = DIContainer()

    def test_register_instance(self) -> None:
        self.container.register("svc", "hello")
        assert self.container.resolve("svc") == "hello"

    def test_register_singleton(self) -> None:
        self.container.register("svc", "singleton_val", singleton=True)
        assert self.container.resolve("svc") == "singleton_val"

    def test_register_factory(self) -> None:
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return f"instance-{call_count}"

        self.container.register_factory("svc", factory)
        assert self.container.resolve("svc") == "instance-1"
        assert self.container.resolve("svc") == "instance-2"

    def test_resolve_not_found(self) -> None:
        with pytest.raises(DIServiceNotFoundError):
            self.container.resolve("missing")

    def test_resolve_type(self) -> None:
        self.container.register("str", "hello")
        assert self.container.resolve_type(str) == "hello"

    def test_register_class(self) -> None:
        class MyService:
            def __init__(self) -> None:
                pass

        self.container.register_class("MyService", MyService)
        result = self.container.resolve("MyService")
        assert isinstance(result, MyService)

    def test_register_class_singleton(self) -> None:
        class MyService:
            def __init__(self) -> None:
                pass

        self.container.register_class("MyService", MyService, singleton=True)
        r1 = self.container.resolve("MyService")
        r2 = self.container.resolve("MyService")
        assert r1 is r2

    def test_reset(self) -> None:
        self.container.register("svc", "val")
        self.container.reset()
        with pytest.raises(DIServiceNotFoundError):
            self.container.resolve("svc")

    def test_build_with_dependency(self) -> None:
        # 使用不含 from __future__ import annotations 的类，
        # 使 __init__ 的类型注解是真实的类型对象而非字符串
        class Dep:
            def __init__(self) -> None:
                pass

        class Service:
            def __init__(self, dep: Dep) -> None:
                self.dep = dep

        self.container.register_class("Dep", Dep)
        self.container.register_class("Service", Service)
        svc = self.container.resolve("Service")
        assert isinstance(svc, Service)
        assert isinstance(svc.dep, Dep)

    def test_build_missing_annotation_raises(self) -> None:
        class BadService:
            def __init__(self, x) -> None:  # 没有类型注解
                self.x = x

        self.container.register_class("BadService", BadService)
        with pytest.raises(DIServiceNotFoundError):
            self.container.resolve("BadService")


class TestInjectDecorator:
    """inject 装饰器测试。"""

    def setup_method(self) -> None:
        reset_container()

    def teardown_method(self) -> None:
        reset_container()

    @pytest.mark.asyncio
    async def test_async_inject(self) -> None:
        container = get_container()
        container.register("greeting", "hello")

        @inject("greeting")
        async def my_func(greeting: str, name: str) -> str:
            return f"{greeting} {name}"

        result = await my_func(name="world")
        assert result == "hello world"

    def test_sync_inject(self) -> None:
        container = get_container()
        container.register("greeting", "hello")

        @inject("greeting")
        def my_func(greeting: str, name: str) -> str:
            return f"{greeting} {name}"

        result = my_func(name="world")
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_inject_multiple(self) -> None:
        container = get_container()
        container.register("a", 1)
        container.register("b", 2)

        @inject("a", "b")
        async def my_func(a: int, b: int) -> int:
            return a + b

        assert await my_func() == 3


class TestGlobalContainer:
    """全局容器单例测试。"""

    def setup_method(self) -> None:
        reset_container()

    def teardown_method(self) -> None:
        reset_container()

    def test_singleton(self) -> None:
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2

    def test_reset(self) -> None:
        c1 = get_container()
        reset_container()
        c2 = get_container()
        assert c1 is not c2
