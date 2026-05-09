"""CityFlow 服务注册中心。

提供服务实例的注册、注销、心跳和健康检查功能。
支持基于心跳超时的自动健康检测和随机负载均衡。

此模块为 backend.services.registry 的便捷重导出入口，
实际实现位于 backend/services/registry.py。

使用方式::

    from backend.discovery.registry import ServiceInfo, get_service_registry

    registry = get_service_registry()
    await registry.start()

    service = ServiceInfo(
        service_id="svc-1",
        service_name="user-service",
        host="127.0.0.1",
        port=8001,
    )
    await registry.register(service)

    # 心跳
    await registry.heartbeat("svc-1")

    # 发现
    svc = await registry.get_service("user-service")

    # 停止
    await registry.stop()
"""

from __future__ import annotations

from backend.services.registry import (
    ServiceInfo,
    ServiceRegistry,
    get_service_registry,
)

__all__ = [
    "ServiceInfo",
    "ServiceRegistry",
    "get_service_registry",
]
