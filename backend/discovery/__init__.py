"""CityFlow 服务发现模块。

提供服务注册中心和服务发现客户端的统一入口。
底层实现位于 backend.services.registry 和 backend.services.discovery。

使用方式::

    from backend.discovery import (
        ServiceInfo,
        ServiceRegistry,
        ServiceDiscovery,
        get_service_registry,
        get_service_discovery,
    )

    # 注册服务
    registry = get_service_registry()
    await registry.start()
    await registry.register(ServiceInfo(
        service_id="svc-1",
        service_name="my-service",
        host="127.0.0.1",
        port=8000,
    ))

    # 发现服务
    discovery = get_service_discovery()
    url = await discovery.discover("my-service")
"""

from __future__ import annotations

from backend.discovery.client import ServiceDiscovery, ServiceNotFoundError
from backend.discovery.registry import (
    ServiceInfo,
    ServiceRegistry,
    get_service_registry,
)

__all__ = [
    "ServiceDiscovery",
    "ServiceInfo",
    "ServiceNotFoundError",
    "ServiceRegistry",
    "get_service_discovery",
    "get_service_registry",
]


def get_service_discovery() -> ServiceDiscovery:
    """获取全局服务发现客户端单例。"""
    from backend.services.discovery import (
        ServiceDiscovery as _ServiceDiscovery,
    )

    return _ServiceDiscovery()
