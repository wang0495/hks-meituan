"""CityFlow 健康检查路由。

提供基础健康检查和详细健康状态端点，用于：
- 负载均衡器探活（Nginx health_check）
- Docker 容器健康检查（docker HEALTHCHECK）
- 运维监控（系统资源 + 依赖服务状态）
- 深度健康检查（系统资源 + 依赖服务 + 聚合状态）
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["系统"])

# 启动时间戳，用于计算 uptime
_start_time = time.monotonic()


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """基础健康检查响应。"""

    status: str = Field("healthy", description="服务状态")
    timestamp: str = Field(..., description="ISO 8601 时间戳")
    instance_id: str = Field(..., description="实例标识")
    uptime_seconds: float = Field(..., description="运行时长（秒）")


class SystemInfo(BaseModel):
    """系统资源信息。"""

    cpu_percent: float = Field(..., description="CPU 使用率 (%)")
    memory_percent: float = Field(..., description="内存使用率 (%)")
    memory_used_mb: float = Field(..., description="已用内存 (MB)")
    memory_total_mb: float = Field(..., description="总内存 (MB)")
    disk_percent: float = Field(..., description="磁盘使用率 (%)")


class ServiceStatus(BaseModel):
    """依赖服务状态。"""

    redis: str = Field(..., description="Redis 连接状态")
    database: str = Field(..., description="数据库连接状态")


class DetailedHealthResponse(BaseModel):
    """详细健康检查响应。"""

    status: str = Field("healthy", description="综合状态")
    timestamp: str = Field(..., description="ISO 8601 时间戳")
    instance_id: str = Field(..., description="实例标识")
    uptime_seconds: float = Field(..., description="运行时长（秒）")
    system: SystemInfo = Field(..., description="系统资源")
    services: ServiceStatus = Field(..., description="依赖服务状态")
    pools: dict | None = Field(default=None, description="连接池统计")


class CheckDetail(BaseModel):
    """单个检查项的详细结果。"""

    name: str = Field(..., description="检查项名称")
    status: str = Field(..., description="检查状态")
    latency_ms: float = Field(..., description="耗时（毫秒）")
    critical: bool = Field(False, description="是否为关键依赖")
    error: str | None = Field(None, description="错误信息")
    details: dict[str, Any] = Field(default_factory=dict, description="附加信息")
    timestamp: str = Field(..., description="ISO 8601 时间戳")


class DeepHealthResponse(BaseModel):
    """深度健康检查响应。"""

    status: str = Field(
        ...,
        description="聚合状态：healthy / degraded / unhealthy",
    )
    timestamp: str = Field(..., description="ISO 8601 时间戳")
    instance_id: str = Field(..., description="实例标识")
    uptime_seconds: float = Field(..., description="运行时长（秒）")
    duration_ms: float = Field(..., description="检查总耗时（毫秒）")
    total: int = Field(..., description="检查项总数")
    healthy: int = Field(..., description="健康检查项数")
    checks: dict[str, CheckDetail] = Field(..., description="各检查项详情")


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    summary="基础健康检查",
    description="快速返回服务状态，用于负载均衡器探活和 Docker HEALTHCHECK。",
    response_model=HealthResponse,
)
async def health_check() -> dict:
    """基础健康检查 -- 轻量、快速，适合高频调用。"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "instance_id": os.getenv("INSTANCE_ID", "unknown"),
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
    }


@router.get(
    "/health/detailed",
    summary="详细健康状态",
    description=(
        "返回系统资源使用情况和依赖服务连接状态。\n\n"
        "综合状态规则：\n"
        "- `healthy`: 所有服务正常\n"
        "- `degraded`: 部分服务异常\n"
        "- `unhealthy`: 核心服务不可用"
    ),
    response_model=DetailedHealthResponse,
)
async def detailed_health() -> dict:
    """详细健康检查 -- 包含系统资源和依赖服务状态。"""
    system_info = _get_system_info()
    service_status = await _get_service_status()

    # 连接池统计
    pool_stats = _get_pool_stats()

    # 判定综合状态
    if service_status["database"] == "unhealthy":
        overall = "unhealthy"
    elif service_status["redis"] == "unhealthy":
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "timestamp": datetime.now(UTC).isoformat(),
        "instance_id": os.getenv("INSTANCE_ID", "unknown"),
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "system": system_info,
        "services": service_status,
        "pools": pool_stats,
    }


@router.get(
    "/health/deep",
    summary="深度健康检查",
    description=(
        "执行系统资源检查和依赖服务连通性检查，并返回聚合状态。\n\n"
        "检查项：\n"
        "- `database`: 数据库连接（关键依赖）\n"
        "- `redis`: Redis 连接（关键依赖）\n"
        "- `llm_service`: LLM 服务连通性\n"
        "- `disk_space`: 磁盘使用率（>90% degraded, >95% unhealthy）\n"
        "- `memory`: 内存使用率（>85% degraded, >95% unhealthy）\n\n"
        "聚合状态规则：\n"
        "- `healthy`: 所有检查通过\n"
        "- `degraded`: 非关键依赖失败或资源告警\n"
        "- `unhealthy`: 关键依赖（database/redis）不可用\n\n"
        "可通过 `critical_only=true` 只检查关键依赖，跳过系统资源检查。"
    ),
)
async def deep_health_check(
    critical_only: bool = Query(
        default=False,
        description="若为 true，只检查关键依赖（database、redis），跳过系统资源检查。",
    ),
) -> dict:
    """深度健康检查 -- 并行执行所有检查项，返回聚合状态。"""
    from backend.health.deep_check import DeepHealthCheck

    checker = DeepHealthCheck(critical_only=critical_only)
    result = await checker.run()

    return {
        "status": result["status"],
        "timestamp": result["timestamp"],
        "instance_id": os.getenv("INSTANCE_ID", "unknown"),
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "duration_ms": result["duration_ms"],
        "total": result["total"],
        "healthy": result["healthy"],
        "checks": result["checks"],
    }


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _get_system_info() -> dict:
    """采集系统资源指标。"""
    try:
        import psutil

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": mem.percent,
            "memory_used_mb": round(mem.used / (1024 * 1024), 1),
            "memory_total_mb": round(mem.total / (1024 * 1024), 1),
            "disk_percent": disk.percent,
        }
    except ImportError:
        # psutil 未安装时返回占位值
        return {
            "cpu_percent": -1,
            "memory_percent": -1,
            "memory_used_mb": -1,
            "memory_total_mb": -1,
            "disk_percent": -1,
        }


async def _get_service_status() -> dict:
    """检查依赖服务的连接状态。"""
    return {
        "redis": await _check_redis(),
        "database": await _check_database(),
    }


async def _check_redis() -> str:
    """检查 Redis 连接（复用session manager的连接）。"""
    try:
        from backend.services.session import get_session_manager

        sm = get_session_manager()
        if sm._redis and await sm._redis.ping():
            return "healthy"
        return "unhealthy"
    except Exception:
        # Fallback: direct connection if session manager unavailable
        try:
            import redis.asyncio as aioredis

            from backend.config import settings

            r = aioredis.from_url(
                f"redis://{settings.redis.host}:{settings.redis.port}/{settings.redis.db}",
                socket_connect_timeout=2,
            )
            await r.ping()
            await r.aclose()
            return "healthy"
        except Exception:
            return "unhealthy"


async def _check_database() -> str:
    """检查数据库连接。"""
    try:
        from sqlalchemy import text

        from backend.database.base import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return "healthy"
    except Exception:
        return "unhealthy"


def _get_pool_stats() -> dict | None:
    """获取连接池统计信息。"""
    try:
        from backend.services.pool_manager import get_pool_manager

        manager = get_pool_manager()
        if manager.is_started:
            return manager.get_stats_dict()
    except Exception:
        pass
    return None


@router.get(
    "/health/pools",
    summary="连接池监控",
    description="返回数据库、HTTP、Redis 连接池的实时统计和健康状态。",
)
async def pool_health() -> dict:
    """连接池健康检查 -- 返回各池统计与告警。"""
    from backend.services.pool_manager import get_pool_manager

    manager = get_pool_manager()
    if not manager.is_started:
        return {"status": "not_started", "pools": None}

    health = await manager.check_health()
    return {
        "status": "healthy" if health["all_healthy"] else "degraded",
        "pools": {
            "database": health["database"],
            "http": health["http"],
        },
        "warnings": health["warnings"],
    }


@router.get(
    "/health/pools/history",
    summary="连接池历史统计",
    description="返回最近 N 条数据库连接池使用率历史数据。",
)
async def pool_history(last_n: int = Query(default=60, ge=1, le=360)) -> dict:
    """连接池历史统计 -- 用于趋势分析和告警。"""
    from backend.services.pool_monitor import get_pool_monitor

    monitor = get_pool_monitor()
    return {
        "history": monitor.get_history(last_n=last_n),
    }
