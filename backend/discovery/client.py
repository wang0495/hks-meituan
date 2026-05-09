"""CityFlow 服务发现客户端。

提供服务发现功能，支持从本地注册中心或远程注册中心获取服务实例。
支持负载均衡和故障转移。

此模块为 backend.services.discovery 的便捷重导出入口，
实际实现位于 backend/services/discovery.py。

使用方式::

    from backend.discovery.client import ServiceDiscovery

    discovery = ServiceDiscovery()
    url = await discovery.discover("user-service")
    if url:
        # 使用 url 调用服务
        pass

    # 或使用会抛异常的版本
    url = await discovery.get_service_url("user-service")
"""

from __future__ import annotations

from backend.services.discovery import (
    ServiceDiscovery,
    ServiceNotFoundError,
    get_service_discovery,
)

__all__ = [
    "ServiceDiscovery",
    "ServiceNotFoundError",
    "get_service_discovery",
]
