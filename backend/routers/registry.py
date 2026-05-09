"""CityFlow 服务注册路由。

提供服务注册、注销、心跳和查询的 REST API。
其他微服务通过这些接口向注册中心报告自身状态。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.registry import ServiceInfo, get_service_registry

router = APIRouter(prefix="/api/registry", tags=["服务注册"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


class RegistryMessage(BaseModel):
    """注册中心通用响应。"""

    message: str = Field(..., description="操作结果消息")


class ServiceListResponse(BaseModel):
    """服务列表响应。"""

    services: list[dict[str, Any]] = Field(
        default_factory=list, description="服务实例列表"
    )
    total: int = Field(0, description="实例总数")


class RegistryStatsResponse(BaseModel):
    """注册中心统计。"""

    total: int = Field(..., description="注册实例总数")
    healthy: int = Field(..., description="健康实例数")
    unhealthy: int = Field(..., description="不健康实例数")


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    summary="注册服务",
    description="将一个服务实例注册到注册中心。服务需定期发送心跳以保持健康状态。",
    response_model=RegistryMessage,
)
async def register_service(service: ServiceInfo) -> dict[str, str]:
    """注册服务实例。"""
    registry = get_service_registry()
    await registry.register(service)
    return {"message": f"服务 {service.service_id} 注册成功"}


@router.post(
    "/deregister/{service_id}",
    summary="注销服务",
    description="从注册中心移除一个服务实例。",
    response_model=RegistryMessage,
)
async def deregister_service(service_id: str) -> dict[str, str]:
    """注销服务实例。"""
    registry = get_service_registry()
    removed = await registry.deregister(service_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"服务 {service_id} 不存在")
    return {"message": f"服务 {service_id} 注销成功"}


@router.post(
    "/heartbeat/{service_id}",
    summary="服务心跳",
    description="更新服务实例的心跳时间。超过心跳超时未更新的实例将被标记为不健康。",
    response_model=RegistryMessage,
)
async def heartbeat(service_id: str) -> dict[str, str]:
    """更新服务心跳。"""
    registry = get_service_registry()
    found = await registry.heartbeat(service_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"服务 {service_id} 不存在")
    return {"message": "心跳更新成功"}


@router.get(
    "/services",
    summary="获取服务列表",
    description="获取所有已注册的服务实例，可按服务名过滤。",
    response_model=ServiceListResponse,
)
async def get_services(
    service_name: str | None = None,
) -> dict[str, Any]:
    """获取服务列表。"""
    registry = get_service_registry()
    services = await registry.get_all_services(service_name)
    return {
        "services": [s.to_dict() for s in services],
        "total": len(services),
    }


@router.get(
    "/services/{service_name}",
    summary="发现服务",
    description="获取指定服务名的一个健康实例（随机负载均衡）。",
    response_model=None,
)
async def discover_service(service_name: str) -> dict[str, Any]:
    """发现服务实例。"""
    registry = get_service_registry()
    service = await registry.get_service(service_name)
    if service is None:
        raise HTTPException(
            status_code=404,
            detail=f"没有可用的健康实例: {service_name}",
        )
    return service.to_dict()


@router.get(
    "/stats",
    summary="注册中心统计",
    description="返回注册中心的实例统计信息。",
    response_model=RegistryStatsResponse,
)
async def get_stats() -> dict[str, int]:
    """获取注册中心统计。"""
    registry = get_service_registry()
    return {
        "total": registry.service_count,
        "healthy": registry.healthy_count,
        "unhealthy": registry.service_count - registry.healthy_count,
    }


@router.post(
    "/cleanup",
    summary="清理不健康实例",
    description="移除所有心跳超时的不健康服务实例。",
    response_model=RegistryMessage,
)
async def cleanup_unhealthy(
    service_name: str | None = None,
) -> dict[str, str]:
    """清理不健康实例。"""
    registry = get_service_registry()
    removed = await registry.remove_unhealthy(service_name)
    return {"message": f"已清理 {removed} 个不健康实例"}
