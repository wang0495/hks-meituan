"""CityFlow Prometheus 指标中心。

汇总所有业务指标的定义和工具函数，供 /metrics 端点和
Grafana 仪表盘使用。

基础指标（REQUEST_COUNT / REQUEST_LATENCY / ACTIVE_SESSIONS / ROUTE_COUNT）
定义在 ``metrics.py`` 中，本模块通过导入复用，避免重复注册。

本模块新增指标分类：
  - HTTP 扩展（请求/响应体大小）
  - 会话生命周期
  - 业务流程（路线规划细节、路线规划错误、POI 查询、POI 查询错误）
  - LLM 调用（次数、延迟、Token 用量）
  - 对话调整
  - 高德地图 API（错误、延迟）
  - 缓存（命中 / 未命中、逐出）
  - WebSocket（连接数、消息数）
  - 熔断器（状态、拒绝次数）
  - 消息队列
  - 后台任务
  - 系统资源（CPU、内存、磁盘）
"""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, Info, generate_latest

# 复用 metrics.py 中已定义的基础指标，避免重复注册
from backend.monitoring.metrics import (  # noqa: F401
    ACTIVE_SESSIONS,
    CACHE_HITS,
    CACHE_MISSES,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    ROUTE_COUNT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 应用信息
# ---------------------------------------------------------------------------

APP_INFO = Info("cityflow", "CityFlow application info")
APP_INFO.info(
    {
        "version": "1.0.0",
        "component": "api",
    }
)

# ---------------------------------------------------------------------------
# HTTP 扩展指标
# ---------------------------------------------------------------------------

REQUEST_SIZE = Histogram(
    "cityflow_request_size_bytes",
    "HTTP request body size in bytes",
    ["method", "endpoint"],
    buckets=(64, 256, 1024, 4096, 16384, 65536, 262144),
)

RESPONSE_SIZE = Histogram(
    "cityflow_response_size_bytes",
    "HTTP response body size in bytes",
    ["method", "endpoint", "status"],
    buckets=(64, 256, 1024, 4096, 16384, 65536, 262144, 1048576),
)

# ---------------------------------------------------------------------------
# 会话指标
# ---------------------------------------------------------------------------

SESSION_CREATED = Counter(
    "cityflow_sessions_created_total",
    "Total sessions created",
)

SESSION_EXPIRED = Counter(
    "cityflow_sessions_expired_total",
    "Total sessions expired",
)

# ---------------------------------------------------------------------------
# 业务流程指标
# ---------------------------------------------------------------------------

# 路线规划细节
ROUTE_PLANNING_LATENCY = Histogram(
    "cityflow_route_planning_duration_seconds",
    "Route planning end-to-end latency",
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 30.0),
)

ROUTE_PLANNING_PHASE_LATENCY = Histogram(
    "cityflow_route_phase_duration_seconds",
    "Route planning phase latency",
    ["phase"],  # parsing / searching / solving / narrating
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0),
)

ROUTE_STEP_COUNT = Histogram(
    "cityflow_route_steps",
    "Number of steps (POIs) per route",
    buckets=(1, 2, 3, 4, 5, 6, 7, 8, 10, 15),
)

# 路线规划错误（供告警规则 RoutePlanningFailureRateHigh 使用）
ROUTE_PLANNING_ERRORS = Counter(
    "cityflow_route_planning_errors_total",
    "Total route planning errors",
    ["error_type"],  # api_error / timeout / no_result / parsing_error
)

# POI 查询
POI_QUERY_COUNT = Counter(
    "cityflow_poi_queries_total",
    "Total POI queries",
    ["query_type"],  # search / detail / distance / filter
)

POI_QUERY_LATENCY = Histogram(
    "cityflow_poi_query_duration_seconds",
    "POI query latency",
    ["query_type"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

POI_CANDIDATES_COUNT = Histogram(
    "cityflow_poi_candidates",
    "Number of candidate POIs returned by filter",
    buckets=(0, 1, 5, 10, 20, 50, 100, 200, 500),
)

# POI 查询错误（供告警规则 PoiQueryFailureRateHigh 使用）
POI_QUERY_ERRORS = Counter(
    "cityflow_poi_query_errors_total",
    "Total POI query errors",
    ["query_type", "error_type"],  # api_error / timeout / not_found
)

# LLM 调用
LLM_CALL_COUNT = Counter(
    "cityflow_llm_calls_total",
    "Total LLM API calls",
    ["model", "status"],  # success / error / timeout
)

LLM_CALL_LATENCY = Histogram(
    "cityflow_llm_call_duration_seconds",
    "LLM API call latency",
    ["model"],
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 30.0),
)

LLM_TOKEN_USAGE = Counter(
    "cityflow_llm_tokens_total",
    "Total LLM tokens consumed",
    ["model", "type"],  # prompt / completion
)

# 对话调整
DIALOGUE_COUNT = Counter(
    "cityflow_dialogue_total",
    "Total dialogue adjustments",
    ["instruction_type"],  # replace / pace / budget / time / retry / unknown
)

DIALOGUE_LATENCY = Histogram(
    "cityflow_dialogue_duration_seconds",
    "Dialogue adjustment latency",
    ["instruction_type"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# 高德地图 API 指标（供告警规则 AmapApi* 使用）
# ---------------------------------------------------------------------------

AMAP_API_ERRORS = Counter(
    "cityflow_amap_api_errors_total",
    "Total Amap API errors",
    ["error_type"],  # quota_exceeded / timeout / server_error / invalid_response
)

AMAP_API_LATENCY = Histogram(
    "cityflow_amap_api_duration_seconds",
    "Amap API call latency",
    ["api_type"],  # direction / geocode / poi / search
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0),
)

# ---------------------------------------------------------------------------
# 缓存指标（CACHE_HITS / CACHE_MISSES 定义在 metrics.py 基础层）
# ---------------------------------------------------------------------------

CACHE_EVICTIONS = Counter(
    "cityflow_cache_evictions_total",
    "Total cache evictions",
    ["cache_name"],
)

CACHE_SIZE = Gauge(
    "cityflow_cache_entries",
    "Current number of entries in cache",
    ["cache_name"],
)

# ---------------------------------------------------------------------------
# WebSocket 指标
# ---------------------------------------------------------------------------

WS_CONNECTIONS = Gauge(
    "cityflow_ws_connections",
    "Current WebSocket connections",
)

WS_MESSAGES = Counter(
    "cityflow_ws_messages_total",
    "Total WebSocket messages",
    ["direction"],  # sent / received
)

WS_ERRORS = Counter(
    "cityflow_ws_errors_total",
    "Total WebSocket errors",
)

# ---------------------------------------------------------------------------
# 熔断器指标
# ---------------------------------------------------------------------------

CIRCUIT_BREAKER_STATE = Gauge(
    "cityflow_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"],
)

CIRCUIT_BREAKER_REJECTIONS = Counter(
    "cityflow_circuit_breaker_rejections_total",
    "Total requests rejected by circuit breaker",
    ["service"],
)

# ---------------------------------------------------------------------------
# 消息队列指标
# ---------------------------------------------------------------------------

MQ_MESSAGES_PUBLISHED = Counter(
    "cityflow_mq_published_total",
    "Total messages published to queue",
    ["queue"],
)

MQ_MESSAGES_CONSUMED = Counter(
    "cityflow_mq_consumed_total",
    "Total messages consumed from queue",
    ["queue", "status"],  # success / error
)

MQ_QUEUE_SIZE = Gauge(
    "cityflow_mq_queue_size",
    "Current queue size",
    ["queue"],
)

# ---------------------------------------------------------------------------
# 后台任务指标
# ---------------------------------------------------------------------------

TASK_COUNT = Counter(
    "cityflow_tasks_total",
    "Total background tasks submitted",
    ["status"],  # submitted / completed / failed / cancelled
)

TASK_DURATION = Histogram(
    "cityflow_task_duration_seconds",
    "Background task execution duration",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

TASK_QUEUE_SIZE = Gauge(
    "cityflow_task_queue_size",
    "Current number of pending tasks",
)

# ---------------------------------------------------------------------------
# 系统资源指标（由 ResourceMonitor 周期性更新）
# ---------------------------------------------------------------------------

SYSTEM_CPU_PERCENT = Gauge(
    "cityflow_system_cpu_percent",
    "System CPU usage percentage",
)

SYSTEM_MEMORY_PERCENT = Gauge(
    "cityflow_system_memory_percent",
    "System memory usage percentage",
)

SYSTEM_MEMORY_USED_MB = Gauge(
    "cityflow_system_memory_used_mb",
    "System memory used in MB",
)

SYSTEM_DISK_PERCENT = Gauge(
    "cityflow_system_disk_percent",
    "System disk usage percentage",
)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def track_request_size(method: str, endpoint: str, size: int) -> None:
    """记录请求体大小。"""
    REQUEST_SIZE.labels(method=method, endpoint=endpoint).observe(size)


def track_response_size(method: str, endpoint: str, status: int, size: int) -> None:
    """记录响应体大小。"""
    RESPONSE_SIZE.labels(method=method, endpoint=endpoint, status=str(status)).observe(size)


def track_route_planning(
    status: str = "success",
    duration: float | None = None,
    steps: int | None = None,
    error_type: str | None = None,
) -> None:
    """路线规划完成时调用。"""
    ROUTE_COUNT.inc()
    if status == "error" and error_type is not None:
        ROUTE_PLANNING_ERRORS.labels(error_type=error_type).inc()
    if duration is not None:
        ROUTE_PLANNING_LATENCY.observe(duration)
    if steps is not None:
        ROUTE_STEP_COUNT.observe(steps)


def track_route_phase(phase: str, duration: float) -> None:
    """记录路线规划各阶段耗时。"""
    ROUTE_PLANNING_PHASE_LATENCY.labels(phase=phase).observe(duration)


def track_poi_query(
    query_type: str = "search",
    duration: float | None = None,
    error_type: str | None = None,
) -> None:
    """记录 POI 查询。"""
    if error_type is not None:
        POI_QUERY_ERRORS.labels(query_type=query_type, error_type=error_type).inc()
    else:
        POI_QUERY_COUNT.labels(query_type=query_type).inc()
    if duration is not None:
        POI_QUERY_LATENCY.labels(query_type=query_type).observe(duration)


def track_poi_candidates(count: int) -> None:
    """记录 POI 候选数量。"""
    POI_CANDIDATES_COUNT.observe(count)


def track_llm_call(
    model: str,
    status: str = "success",
    duration: float | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    """记录 LLM API 调用。"""
    LLM_CALL_COUNT.labels(model=model, status=status).inc()
    if duration is not None:
        LLM_CALL_LATENCY.labels(model=model).observe(duration)
    if prompt_tokens is not None:
        LLM_TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)
    if completion_tokens is not None:
        LLM_TOKEN_USAGE.labels(model=model, type="completion").inc(completion_tokens)


def track_dialogue(instruction_type: str = "unknown", duration: float | None = None) -> None:
    """记录对话调整。"""
    DIALOGUE_COUNT.labels(instruction_type=instruction_type).inc()
    if duration is not None:
        DIALOGUE_LATENCY.labels(instruction_type=instruction_type).observe(duration)


def track_amap_api_call(
    api_type: str,
    duration: float | None = None,
    error_type: str | None = None,
) -> None:
    """记录高德地图 API 调用。"""
    if error_type is not None:
        AMAP_API_ERRORS.labels(error_type=error_type).inc()
    if duration is not None:
        AMAP_API_LATENCY.labels(api_type=api_type).observe(duration)


def track_cache_hit(cache_name: str) -> None:
    """记录缓存命中。"""
    CACHE_HITS.labels(cache_name=cache_name).inc()


def track_cache_miss(cache_name: str) -> None:
    """记录缓存未命中。"""
    CACHE_MISSES.labels(cache_name=cache_name).inc()


def track_cache_eviction(cache_name: str) -> None:
    """记录缓存逐出。"""
    CACHE_EVICTIONS.labels(cache_name=cache_name).inc()


def update_cache_size(cache_name: str, size: int) -> None:
    """更新缓存条目数。"""
    CACHE_SIZE.labels(cache_name=cache_name).set(size)


def track_ws_connect() -> None:
    """WebSocket 连接建立。"""
    WS_CONNECTIONS.inc()


def track_ws_disconnect() -> None:
    """WebSocket 连接断开。"""
    WS_CONNECTIONS.dec()


def track_ws_message(direction: str) -> None:
    """记录 WebSocket 消息。"""
    WS_MESSAGES.labels(direction=direction).inc()


def track_ws_error() -> None:
    """记录 WebSocket 错误。"""
    WS_ERRORS.inc()


def update_circuit_breaker_state(service: str, state: int) -> None:
    """更新熔断器状态（0=closed, 1=open, 2=half_open）。"""
    CIRCUIT_BREAKER_STATE.labels(service=service).set(state)


def track_circuit_breaker_rejection(service: str) -> None:
    """记录熔断器拒绝。"""
    CIRCUIT_BREAKER_REJECTIONS.labels(service=service).inc()


def track_task(status: str, duration: float | None = None) -> None:
    """记录后台任务。"""
    TASK_COUNT.labels(status=status).inc()
    if duration is not None:
        TASK_DURATION.observe(duration)


def update_task_queue_size(size: int) -> None:
    """更新任务队列大小。"""
    TASK_QUEUE_SIZE.set(size)


def update_system_resources(
    cpu: float,
    memory_percent: float,
    memory_used_mb: float,
    disk_percent: float,
) -> None:
    """更新系统资源指标（由 ResourceMonitor 调用）。"""
    SYSTEM_CPU_PERCENT.set(cpu)
    SYSTEM_MEMORY_PERCENT.set(memory_percent)
    SYSTEM_MEMORY_USED_MB.set(memory_used_mb)
    SYSTEM_DISK_PERCENT.set(disk_percent)


def get_metrics() -> bytes:
    """返回当前所有 Prometheus 指标的文本表示。"""
    return generate_latest(REGISTRY)


def get_metrics_summary() -> dict[str, Any]:
    """返回关键指标的摘要（供 /metrics/health 端点使用）。"""
    return {
        "active_sessions": ACTIVE_SESSIONS._value.get(),  # type: ignore[attr-defined]
        "ws_connections": WS_CONNECTIONS._value.get(),  # type: ignore[attr-defined]
        "task_queue_size": TASK_QUEUE_SIZE._value.get(),  # type: ignore[attr-defined]
        "system_cpu_percent": SYSTEM_CPU_PERCENT._value.get(),  # type: ignore[attr-defined]
        "system_memory_percent": SYSTEM_MEMORY_PERCENT._value.get(),  # type: ignore[attr-defined]
        "system_disk_percent": SYSTEM_DISK_PERCENT._value.get(),  # type: ignore[attr-defined]
    }
