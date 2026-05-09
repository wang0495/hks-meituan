"""CityFlow API 网关模块。

提供请求路由转发、JWT 认证授权、速率限制等网关功能。
可作为独立服务运行，也可嵌入主应用。
"""

from backend.gateway.auth import AuthMiddleware
from backend.gateway.main import create_gateway_app
from backend.gateway.rate_limit import GatewayRateLimitMiddleware
from backend.gateway.router import GatewayRouter

__all__ = [
    "AuthMiddleware",
    "GatewayRateLimitMiddleware",
    "GatewayRouter",
    "create_gateway_app",
]
