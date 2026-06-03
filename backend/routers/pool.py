"""CityFlow 连接池监控 API。

提供连接池统计、健康检查、告警查询和仪表盘数据。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.pool.monitor import get_pool_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pool", tags=["连接池"])


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


class PoolStatsResponse(BaseModel):
    """连接池统计响应。"""

    database: dict[str, Any] = Field(default_factory=dict, description="数据库连接池统计")
    http: dict[str, Any] = Field(default_factory=dict, description="HTTP 连接池统计")


class AlertItem(BaseModel):
    """告警条目。"""

    pool_type: str
    message: str
    severity: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: float


class HealthResponse(BaseModel):
    """健康检查响应。"""

    healthy: bool
    issues: list[str]
    database: dict[str, Any]
    http: dict[str, Any]
    alerts: list[dict[str, Any]]


class DashboardResponse(BaseModel):
    """仪表盘响应。"""

    stats: dict[str, Any]
    alerts: list[dict[str, Any]]
    health: dict[str, Any]
    history: list[dict[str, Any]]
    thresholds: dict[str, float]


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    summary="连接池统计",
    description="获取数据库和 HTTP 连接池的实时统计数据。",
    response_model=PoolStatsResponse,
)
async def pool_stats() -> dict[str, Any]:
    """获取连接池统计信息。

    返回数据库连接池的 pool_size / checkedin / checkedout / overflow，
    以及 HTTP 连接池的 max_connections / active / keepalive。
    """
    monitor = get_pool_monitor()
    return monitor.get_stats()


@router.get(
    "/health",
    summary="连接池健康检查",
    description=(
        "执行全面健康检查，返回各连接池状态、告警列表和问题摘要。\n\n"
        "- `healthy=true` 表示所有连接池正常\n"
        "- `issues` 列出所有严重问题（critical 级别告警）\n"
        "- `alerts` 包含所有告警（warning + critical）"
    ),
    response_model=HealthResponse,
)
async def pool_health() -> dict[str, Any]:
    """连接池健康检查。"""
    monitor = get_pool_monitor()
    report = monitor.check_health()
    return report.to_dict()


@router.get(
    "/alerts",
    summary="连接池告警",
    description=(
        "查询当前活跃的连接池告警。\n\n"
        "支持按严重级别过滤：warning（使用率偏高）、critical（使用率严重过高）。"
    ),
    response_model=list[AlertItem],
)
async def pool_alerts(
    severity: str | None = Query(
        None,
        description="按告警级别过滤: warning / critical",
    ),
) -> list[dict[str, Any]]:
    """查询连接池告警。"""
    monitor = get_pool_monitor()
    alerts = monitor.check_alerts()

    if severity is not None:
        alerts = [a for a in alerts if a.severity.value == severity]

    return [a.to_dict() for a in alerts]


@router.get(
    "/dashboard",
    summary="连接池仪表盘",
    description=(
        "返回连接池仪表盘的完整数据，包含：\n\n"
        "- `stats`: 实时统计\n"
        "- `alerts`: 当前告警\n"
        "- `health`: 健康检查结果\n"
        "- `history`: 最近 60 条历史统计\n"
        "- `thresholds`: 告警阈值配置"
    ),
    response_model=DashboardResponse,
)
async def pool_dashboard() -> dict[str, Any]:
    """连接池仪表盘数据。"""
    monitor = get_pool_monitor()
    return monitor.get_dashboard()


@router.get(
    "/history",
    summary="连接池历史统计",
    description="获取最近 N 条连接池统计数据，用于趋势图表展示。",
)
async def pool_history(
    last_n: int = Query(
        60,
        ge=1,
        le=360,
        description="返回条数（最大 360，约 1 小时 @ 15s 间隔）",
    ),
) -> list[dict[str, Any]]:
    """获取连接池历史统计。"""
    monitor = get_pool_monitor()
    return monitor.get_history(last_n=last_n)
