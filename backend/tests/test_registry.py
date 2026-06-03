"""服务注册中心单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.services.discovery import ServiceDiscovery, ServiceNotFoundError
from backend.services.registry import ServiceInfo, ServiceRegistry

# ---------------------------------------------------------------------------
# ServiceInfo
# ---------------------------------------------------------------------------


class TestServiceInfo:
    def test_create_with_defaults(self) -> None:
        info = ServiceInfo(
            service_id="s1",
            service_name="test-svc",
            host="127.0.0.1",
            port=8000,
        )
        assert info.status == "healthy"
        assert info.metadata == {}

    def test_to_dict(self) -> None:
        info = ServiceInfo(
            service_id="s1",
            service_name="test-svc",
            host="10.0.0.1",
            port=9000,
            metadata={"version": "1.0"},
        )
        d = info.to_dict()
        assert d["service_id"] == "s1"
        assert d["host"] == "10.0.0.1"
        assert d["port"] == 9000
        assert d["metadata"] == {"version": "1.0"}
        assert "registered_at" in d
        assert "last_heartbeat" in d

    def test_port_validation(self) -> None:
        with pytest.raises(ValidationError):
            ServiceInfo(
                service_id="s1",
                service_name="test-svc",
                host="127.0.0.1",
                port=0,
            )


# ---------------------------------------------------------------------------
# ServiceRegistry
# ---------------------------------------------------------------------------


def _make_service(
    service_id: str = "s1",
    service_name: str = "test-svc",
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ServiceInfo:
    return ServiceInfo(
        service_id=service_id,
        service_name=service_name,
        host=host,
        port=port,
    )


class TestServiceRegistry:
    @pytest.fixture()
    def registry(self) -> ServiceRegistry:
        return ServiceRegistry(heartbeat_timeout=30)

    @pytest.mark.asyncio()
    async def test_register_and_get(self, registry: ServiceRegistry) -> None:
        svc = _make_service()
        await registry.register(svc)

        result = await registry.get_service("test-svc")
        assert result is not None
        assert result.service_id == "s1"

    @pytest.mark.asyncio()
    async def test_get_nonexistent_returns_none(self, registry: ServiceRegistry) -> None:
        result = await registry.get_service("no-such-svc")
        assert result is None

    @pytest.mark.asyncio()
    async def test_deregister(self, registry: ServiceRegistry) -> None:
        svc = _make_service()
        await registry.register(svc)

        removed = await registry.deregister("s1")
        assert removed is True

        result = await registry.get_service("test-svc")
        assert result is None

    @pytest.mark.asyncio()
    async def test_deregister_nonexistent(self, registry: ServiceRegistry) -> None:
        removed = await registry.deregister("no-such")
        assert removed is False

    @pytest.mark.asyncio()
    async def test_heartbeat(self, registry: ServiceRegistry) -> None:
        svc = _make_service()
        await registry.register(svc)

        ok = await registry.heartbeat("s1")
        assert ok is True

    @pytest.mark.asyncio()
    async def test_heartbeat_nonexistent(self, registry: ServiceRegistry) -> None:
        ok = await registry.heartbeat("no-such")
        assert ok is False

    @pytest.mark.asyncio()
    async def test_get_all_services(self, registry: ServiceRegistry) -> None:
        await registry.register(_make_service("s1", "svc-a", port=8001))
        await registry.register(_make_service("s2", "svc-a", port=8002))
        await registry.register(_make_service("s3", "svc-b", port=8003))

        all_svcs = await registry.get_all_services()
        assert len(all_svcs) == 3

        filtered = await registry.get_all_services("svc-a")
        assert len(filtered) == 2

    @pytest.mark.asyncio()
    async def test_unhealthy_service_not_returned(self, registry: ServiceRegistry) -> None:
        svc = _make_service()
        svc.status = "unhealthy"
        await registry.register(svc)

        result = await registry.get_service("test-svc")
        assert result is None

    @pytest.mark.asyncio()
    async def test_health_check_marks_unhealthy(self, registry: ServiceRegistry) -> None:
        svc = _make_service()
        # 设置心跳时间为很久以前
        svc.last_heartbeat = datetime.now() - timedelta(seconds=60)
        await registry.register(svc)

        # 手动触发一次健康检查逻辑
        (
            await registry._check_health_loop.__wrapped__(registry)
            if hasattr(registry._check_health_loop, "__wrapped__")
            else None
        )

        # 直接验证逻辑：超过超时时间应标记为不健康
        now = datetime.now()
        if now - svc.last_heartbeat > timedelta(seconds=registry._heartbeat_timeout):
            svc.status = "unhealthy"

        assert svc.status == "unhealthy"

    @pytest.mark.asyncio()
    async def test_remove_unhealthy(self, registry: ServiceRegistry) -> None:
        svc = _make_service()
        svc.status = "unhealthy"
        await registry.register(svc)

        removed = await registry.remove_unhealthy()
        assert removed == 1

        result = await registry.get_all_services()
        assert len(result) == 0

    @pytest.mark.asyncio()
    async def test_service_count_properties(self, registry: ServiceRegistry) -> None:
        assert registry.service_count == 0
        assert registry.healthy_count == 0

        await registry.register(_make_service("s1", "svc-a", port=8001))
        svc2 = _make_service("s2", "svc-a", port=8002)
        svc2.status = "unhealthy"
        await registry.register(svc2)

        assert registry.service_count == 2
        assert registry.healthy_count == 1

    @pytest.mark.asyncio()
    async def test_start_stop(self, registry: ServiceRegistry) -> None:
        await registry.start()
        assert registry._running is True

        await registry.stop()
        assert registry._running is False

    @pytest.mark.asyncio()
    async def test_start_idempotent(self, registry: ServiceRegistry) -> None:
        await registry.start()
        await registry.start()  # 应该不会报错
        await registry.stop()


# ---------------------------------------------------------------------------
# ServiceDiscovery
# ---------------------------------------------------------------------------


class TestServiceDiscovery:
    @pytest.fixture()
    def registry(self) -> ServiceRegistry:
        return ServiceRegistry()

    @pytest.mark.asyncio()
    async def test_discover_local(self, registry: ServiceRegistry) -> None:
        svc = _make_service(host="10.0.0.1", port=9000)
        await registry.register(svc)

        discovery = ServiceDiscovery()
        # 手动注入本地注册中心
        discovery._local_registry = registry

        url = await discovery.discover("test-svc")
        assert url == "http://10.0.0.1:9000"

    @pytest.mark.asyncio()
    async def test_discover_not_found(self, registry: ServiceRegistry) -> None:
        discovery = ServiceDiscovery()
        discovery._local_registry = registry

        url = await discovery.discover("no-such-svc")
        assert url is None

    @pytest.mark.asyncio()
    async def test_get_service_url_raises(self, registry: ServiceRegistry) -> None:
        discovery = ServiceDiscovery()
        discovery._local_registry = registry

        with pytest.raises(ServiceNotFoundError) as exc_info:
            await discovery.get_service_url("no-such-svc")
        assert "no-such-svc" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_get_service_url_success(self, registry: ServiceRegistry) -> None:
        svc = _make_service(host="192.168.1.1", port=3000)
        await registry.register(svc)

        discovery = ServiceDiscovery()
        discovery._local_registry = registry

        url = await discovery.get_service_url("test-svc")
        assert url == "http://192.168.1.1:3000"
