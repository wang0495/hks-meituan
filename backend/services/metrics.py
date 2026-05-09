"""CityFlow 应用指标收集模块

提供 Prometheus 格式的指标收集，包括：
- HTTP 请求计数与延迟
- 活跃会话数
- 路线规划统计
- POI 查询统计
"""

import time

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# 请求计数
REQUEST_COUNT = Counter(
    "cityflow_requests_total", "Total requests", ["method", "endpoint", "status"]
)

# 请求延迟
REQUEST_LATENCY = Histogram(
    "cityflow_request_duration_seconds", "Request latency", ["method", "endpoint"]
)

# 活跃会话数
ACTIVE_SESSIONS = Gauge(
    "cityflow_active_sessions", "Number of active dialogue sessions"
)

# 路线规划计数
ROUTE_COUNT = Counter("cityflow_routes_total", "Total routes planned", ["user_type"])

# POI查询计数
POI_QUERY_COUNT = Counter("cityflow_poi_queries_total", "Total POI queries")


class MetricsMiddleware:
    """指标收集中间件"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()

            # 处理请求
            await self.app(scope, receive, send)

            # 记录指标
            duration = time.time() - start_time
            method = scope["method"]
            path = scope["path"]

            REQUEST_COUNT.labels(method=method, endpoint=path, status=200).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)
        else:
            await self.app(scope, receive, send)


def track_route_planning(user_type: str):
    """记录路线规划"""
    ROUTE_COUNT.labels(user_type=user_type).inc()


def track_poi_query():
    """记录POI查询"""
    POI_QUERY_COUNT.inc()


def get_metrics():
    """获取 Prometheus 格式的指标数据"""
    return generate_latest()
