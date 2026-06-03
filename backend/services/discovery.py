"""CityFlow 服务发现客户端。

提供服务发现功能，支持从本地注册中心或远程注册中心获取服务实例。
支持负载均衡和故障转移。

使用方式::

    discovery = get_service_discovery()
    service_url = await discovery.discover("user-service")
    if service_url:
        # 使用 service_url 调用服务
        pass
"""

from __future__ import annotations

import logging

import httpx

from backend.services.registry import get_service_registry

logger = logging.getLogger(__name__)

__all__ = [
    "ServiceDiscovery",
    "get_service_discovery",
]


class ServiceDiscovery:
    """服务发现客户端。

    优先从本地注册中心获取服务实例，若本地无可用实例
    则尝试从远程注册中心获取。

    Args:
        registry_url: 远程注册中心的 URL，为 None 时仅使用本地注册中心。
    """

    def __init__(self, registry_url: str | None = None) -> None:
        self._registry_url = registry_url
        self._local_registry = get_service_registry()

    async def discover(self, service_name: str) -> str | None:
        """发现服务，返回服务的基础 URL（如 ``http://host:port``）。

        优先使用本地注册中心，若无可用实例则尝试远程注册中心。
        找不到时返回 None。
        """
        # 优先从本地注册中心获取
        service = await self._local_registry.get_service(service_name)
        if service is not None:
            url = f"http://{service.host}:{service.port}"
            logger.debug("从本地注册中心发现服务: %s -> %s", service_name, url)
            return url

        # 从远程注册中心获取
        if self._registry_url is not None:
            return await self._discover_remote(service_name)

        logger.warning("未找到可用的服务实例: %s", service_name)
        return None

    async def _discover_remote(self, service_name: str) -> str | None:
        """从远程注册中心发现服务。"""
        assert self._registry_url is not None
        url = f"{self._registry_url.rstrip('/')}/api/registry/services/{service_name}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    host = data.get("host")
                    port = data.get("port")
                    if host and port:
                        service_url = f"http://{host}:{port}"
                        logger.debug(
                            "从远程注册中心发现服务: %s -> %s",
                            service_name,
                            service_url,
                        )
                        return service_url
                logger.warning(
                    "远程注册中心未找到服务: %s (status=%d)",
                    service_name,
                    response.status_code,
                )
        except httpx.HTTPError:
            logger.exception("远程注册中心请求失败: %s", service_name)

        return None

    async def get_service_url(self, service_name: str) -> str:
        """获取服务 URL，找不到时抛出异常。

        Raises:
            ServiceNotFoundError: 服务不存在或无可用实例。
        """
        url = await self.discover(service_name)
        if url is None:
            raise ServiceNotFoundError(service_name)
        return url


class ServiceNotFoundError(Exception):
    """服务未找到异常。"""

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        super().__init__(f"服务不存在或无可用实例: {service_name}")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_discovery: ServiceDiscovery | None = None


def get_service_discovery() -> ServiceDiscovery:
    """获取全局服务发现客户端单例。"""
    global _discovery
    if _discovery is None:
        from backend.config import settings

        registry_url: str | None = getattr(settings, "registry_url", None)
        _discovery = ServiceDiscovery(registry_url=registry_url)
    return _discovery
