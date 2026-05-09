"""Prometheus 指标定义与工具函数（基础层）。

本模块定义 CityFlow 基础指标，供 ``prometheus.py`` 和中间件复用。
更丰富的业务指标（LLM / POI / 缓存 / WS / 熔断器等）见 ``prometheus.py``。
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# ---------------------------------------------------------------------------
# 指标定义
# ---------------------------------------------------------------------------

# 请求计数（按方法、端点、状态码分组）
REQUEST_COUNT = Counter(
    "cityflow_requests_total",
    "Total requests",
    ["method", "endpoint", "status"],
)

# 请求延迟直方图（按方法、端点分组）
REQUEST_LATENCY = Histogram(
    "cityflow_request_duration_seconds",
    "Request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 当前活跃会话数
ACTIVE_SESSIONS = Gauge(
    "cityflow_active_sessions",
    "Number of active sessions",
)

# 路线规划累计次数
ROUTE_COUNT = Counter(
    "cityflow_routes_total",
    "Total routes planned",
)

# 缓存命中 / 未命中（基础层，供中间件和独立模块直接使用）
CACHE_HITS = Counter(
    "cityflow_cache_hits_total",
    "Total cache hits",
    ["cache_name"],
)

CACHE_MISSES = Counter(
    "cityflow_cache_misses_total",
    "Total cache misses",
    ["cache_name"],
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def track_request(method: str, endpoint: str, status: int, duration: float) -> None:
    """记录一次 HTTP 请求的指标。"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def track_route_planning() -> None:
    """路线规划完成时调用，计数 +1。"""
    ROUTE_COUNT.inc()


def track_cache_hit(cache_name: str) -> None:
    """记录一次缓存命中。"""
    CACHE_HITS.labels(cache_name=cache_name).inc()


def track_cache_miss(cache_name: str) -> None:
    """记录一次缓存未命中。"""
    CACHE_MISSES.labels(cache_name=cache_name).inc()


def get_metrics() -> bytes:
    """返回当前所有 Prometheus 指标的文本表示（供 /metrics 端点使用）。"""
    return generate_latest()
