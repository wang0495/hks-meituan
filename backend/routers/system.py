"""系统级端点 — 健康检查 + 缓存监控。"""

from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import HealthResponse
from backend.services.cache import (
    distance_cache,
    general_cache,
    get_multilevel_cache,
    poi_cache,
    profile_cache,
    route_cache,
)

router = APIRouter(tags=["系统"])


@router.get(
    "/api/health",
    summary="健康检查",
    description="返回服务运行状态，可用于负载均衡器探活。",
    response_model=HealthResponse,
    responses={200: {"description": "服务正常"}},
)
async def health():
    """健康检查接口。"""
    return {"status": "ok"}


@router.get(
    "/api/cache/stats",
    summary="缓存统计",
    description="返回各缓存实例的命中率和使用情况，用于性能监控。",
)
async def cache_stats():
    """返回缓存命中率统计。"""
    ml_cache = get_multilevel_cache()
    return {
        "l1_caches": {
            "route_cache": route_cache.stats,
            "distance_cache": distance_cache.stats,
            "poi_cache": poi_cache.stats,
            "profile_cache": profile_cache.stats,
            "general_cache": general_cache.stats,
        },
        "multilevel_cache": ml_cache.stats,
    }
