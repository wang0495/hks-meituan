"""CityFlow 服务注册中心。

提供服务实例的注册、注销、心跳和健康检查功能。
支持基于心跳超时的自动健康检测和随机负载均衡。

使用方式::

    registry = get_service_registry()
    await registry.start()

    # 注册
    service = ServiceInfo(...)
    await registry.register(service)

    # 发现
    svc = await registry.get_service("my-service")
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = [
    "ServiceInfo",
    "ServiceRegistry",
    "get_service_registry",
]


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class ServiceInfo(BaseModel):
    """服务实例信息。"""

    service_id: str = Field(..., description="服务实例唯一标识")
    service_name: str = Field(..., description="服务名称（同名服务可有多个实例）")
    host: str = Field(..., description="服务主机地址")
    port: int = Field(..., ge=1, le=65535, description="服务端口")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    registered_at: datetime = Field(default_factory=datetime.now, description="注册时间")
    last_heartbeat: datetime = Field(default_factory=datetime.now, description="最后心跳时间")
    status: str = Field("healthy", description="服务状态: healthy / unhealthy")

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 API 响应）。"""
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "metadata": self.metadata,
            "status": self.status,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }


# ---------------------------------------------------------------------------
# 注册中心
# ---------------------------------------------------------------------------


class ServiceRegistry:
    """服务注册中心。

    管理所有已注册服务实例，周期性检查心跳超时，
    自动将超时实例标记为 unhealthy。

    Args:
        heartbeat_timeout: 心跳超时秒数，超过此时间未收到心跳则标记为不健康。
        health_check_interval: 健康检查周期（秒）。
    """

    def __init__(
        self,
        heartbeat_timeout: int = 30,
        health_check_interval: int = 10,
    ) -> None:
        self._services: dict[str, ServiceInfo] = {}
        self._heartbeat_timeout = heartbeat_timeout
        self._health_check_interval = health_check_interval
        self._running = False
        self._health_task: asyncio.Task[None] | None = None

    # ---- 注册 / 注销 ----

    async def register(self, service: ServiceInfo) -> None:
        """注册一个服务实例。"""
        self._services[service.service_id] = service
        logger.info(
            "服务注册: %s (%s) @ %s:%d",
            service.service_id,
            service.service_name,
            service.host,
            service.port,
        )

    async def deregister(self, service_id: str) -> bool:
        """注销一个服务实例。返回是否确实存在并被移除。"""
        if service_id in self._services:
            del self._services[service_id]
            logger.info("服务注销: %s", service_id)
            return True
        logger.warning("注销不存在的服务: %s", service_id)
        return False

    # ---- 心跳 ----

    async def heartbeat(self, service_id: str) -> bool:
        """更新服务心跳。返回服务是否存在。"""
        service = self._services.get(service_id)
        if service is None:
            return False
        service.last_heartbeat = datetime.now()
        service.status = "healthy"
        return True

    # ---- 查询 ----

    async def get_service(self, service_name: str) -> ServiceInfo | None:
        """获取指定服务的一个健康实例（随机负载均衡）。"""
        healthy = [
            s
            for s in self._services.values()
            if s.service_name == service_name and s.status == "healthy"
        ]
        if healthy:
            return random.choice(healthy)
        return None

    async def get_all_services(self, service_name: str | None = None) -> list[ServiceInfo]:
        """获取所有服务实例，可按服务名过滤。"""
        if service_name is not None:
            return [s for s in self._services.values() if s.service_name == service_name]
        return list(self._services.values())

    # ---- 健康检查 ----

    async def _check_health_loop(self) -> None:
        """后台循环：定期检查心跳超时，标记不健康实例。"""
        while self._running:
            now = datetime.now()
            for service_id, service in list(self._services.items()):
                if now - service.last_heartbeat > timedelta(
                    seconds=self._heartbeat_timeout
                ):  # noqa: SIM102
                    if service.status != "unhealthy":
                        service.status = "unhealthy"
                        logger.warning(
                            "服务心跳超时，标记为不健康: %s (%s)",
                            service_id,
                            service.service_name,
                        )
            await asyncio.sleep(self._health_check_interval)

    async def remove_unhealthy(self, service_name: str | None = None) -> int:
        """移除所有不健康的实例。返回移除数量。"""
        to_remove = [
            sid
            for sid, svc in self._services.items()
            if svc.status == "unhealthy"
            and (service_name is None or svc.service_name == service_name)
        ]
        for sid in to_remove:
            del self._services[sid]
        if to_remove:
            logger.info("已移除 %d 个不健康实例", len(to_remove))
        return len(to_remove)

    # ---- 生命周期 ----

    async def start(self) -> None:
        """启动健康检查后台任务。"""
        if self._running:
            return
        self._running = True
        self._health_task = asyncio.create_task(self._check_health_loop())
        logger.info("服务注册中心已启动 (heartbeat_timeout=%ds)", self._heartbeat_timeout)

    async def stop(self) -> None:
        """停止健康检查后台任务。"""
        self._running = False
        if self._health_task is not None:
            self._health_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_task
            self._health_task = None
        logger.info("服务注册中心已停止")

    @property
    def service_count(self) -> int:
        """当前注册的服务实例总数。"""
        return len(self._services)

    @property
    def healthy_count(self) -> int:
        """当前健康的服务实例数。"""
        return sum(1 for s in self._services.values() if s.status == "healthy")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_registry: ServiceRegistry | None = None


def get_service_registry() -> ServiceRegistry:
    """获取全局服务注册中心单例。"""
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry
