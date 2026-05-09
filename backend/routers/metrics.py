"""Prometheus 监控端点。

提供两个端点：
  - GET /metrics        — Prometheus exposition format 指标抓取
  - GET /metrics/health — 关键指标摘要（JSON），供运维快速查看
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from backend.monitoring.prometheus import get_metrics, get_metrics_summary

router = APIRouter(tags=["监控"])


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


class MetricsHealthResponse(BaseModel):
    """关键指标摘要。"""

    active_sessions: int = Field(0, description="当前活跃会话数")
    ws_connections: int = Field(0, description="当前 WebSocket 连接数")
    task_queue_size: int = Field(0, description="待处理任务数")
    system_cpu_percent: float = Field(0.0, description="系统 CPU 使用率 (%)")
    system_memory_percent: float = Field(0.0, description="系统内存使用率 (%)")
    system_disk_percent: float = Field(0.0, description="系统磁盘使用率 (%)")


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    summary="Prometheus 指标",
    description=(
        "以 Prometheus exposition format 返回所有自定义指标，"
        "供 Prometheus server 抓取。\n\n"
        "涵盖以下指标类别：\n"
        "- HTTP 请求计数与延迟\n"
        "- 路线规划统计（成功/兜底/失败）\n"
        "- POI 查询统计\n"
        "- LLM 调用次数、延迟与 Token 用量\n"
        "- 对话调整统计\n"
        "- 缓存命中率\n"
        "- WebSocket 连接数\n"
        "- 熔断器状态\n"
        "- 后台任务队列\n"
        "- 系统资源（CPU/内存/磁盘）"
    ),
    response_class=Response,
)
async def metrics() -> Response:
    """返回 Prometheus 指标文本。"""
    return Response(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get(
    "/metrics/health",
    summary="指标健康摘要",
    description=(
        "返回关键运行指标的 JSON 摘要，供运维快速查看系统状态。\n\n"
        "无需 Prometheus 即可直接访问。"
    ),
    response_model=MetricsHealthResponse,
)
async def metrics_health() -> MetricsHealthResponse:
    """返回关键指标摘要。"""
    summary = get_metrics_summary()
    return MetricsHealthResponse(**summary)
