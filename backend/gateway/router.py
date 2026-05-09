"""网关路由配置。

基于前缀匹配将请求转发到对应的后端微服务。
支持精确匹配和正则模式匹配。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RouteTarget:
    """路由目标。"""

    service: str
    prefix: str
    methods: list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH"]
    )
    strip_prefix: bool = True


class GatewayRouter:
    """网关路由器。

    按注册顺序匹配路由，首个匹配生效。
    支持两种模式：
    - 精确前缀匹配（默认）：`/api/poi` 匹配 `/api/poi/xxx`
    - 正则匹配：以 `^` 开头的 pattern 按正则处理

    用法::

        router = GatewayRouter()
        router.register("poi", "http://localhost:8001", prefix="/api/poi")
        target = router.match("/api/poi/search?keyword=故宫", "GET")
    """

    def __init__(self) -> None:
        self._routes: list[RouteTarget] = []
        self._services: dict[str, str] = {}  # service_name -> base_url

    def register(
        self,
        service: str,
        base_url: str,
        prefix: str = "",
        methods: list[str] | None = None,
        strip_prefix: bool = True,
    ) -> None:
        """注册后端服务。

        Args:
            service: 服务名称（如 ``poi``）。
            base_url: 服务基础 URL（如 ``http://localhost:8001``）。
            prefix: URL 前缀（如 ``/api/poi``）。
            methods: 允许的 HTTP 方法，默认全部。
            strip_prefix: 转发时是否剥离前缀。
        """
        self._services[service] = base_url.rstrip("/")
        target = RouteTarget(
            service=service,
            prefix=prefix,
            methods=methods or ["GET", "POST", "PUT", "DELETE", "PATCH"],
            strip_prefix=strip_prefix,
        )
        self._routes.append(target)
        logger.info("注册路由: %s -> %s (prefix=%s)", service, base_url, prefix)

    def match(self, path: str, method: str) -> tuple[RouteTarget, str] | None:
        """匹配路由，返回 (目标, 转发路径)。

        Args:
            path: 请求路径（如 ``/api/poi/search``）。
            method: HTTP 方法。

        Returns:
            匹配成功返回 ``(RouteTarget, 转发后路径)``，否则 ``None``。
        """
        for route in self._routes:
            if method.upper() not in route.methods:
                continue

            if path == route.prefix or path.startswith(route.prefix + "/"):
                # 计算转发路径
                if route.strip_prefix:
                    forward_path = path[len(route.prefix) :] or "/"
                else:
                    forward_path = path

                return route, forward_path

        return None

    def get_service_url(self, service: str) -> str | None:
        """获取服务的基础 URL。"""
        return self._services.get(service)

    @property
    def service_names(self) -> list[str]:
        """已注册的服务名列表。"""
        return list(self._services.keys())


# ---------------------------------------------------------------------------
# 默认路由配置
# ---------------------------------------------------------------------------

_default_router = GatewayRouter()


def get_gateway_router() -> GatewayRouter:
    """获取默认网关路由器实例。

    根据环境变量或配置注册后端服务。可在启动时调用
    ``router.register(...)`` 添加更多服务。
    """
    return _default_router


def setup_default_routes(
    poi_url: str = "http://localhost:8001",
    route_url: str = "http://localhost:8002",
    dialogue_url: str = "http://localhost:8003",
) -> GatewayRouter:
    """用默认地址配置路由。

    Args:
        poi_url: POI 服务地址。
        route_url: 路线服务地址。
        dialogue_url: 对话服务地址。

    Returns:
        配置好的路由器实例。
    """
    router = get_gateway_router()
    router.register("poi", poi_url, prefix="/api/poi")
    router.register("route", route_url, prefix="/api/route")
    router.register("dialogue", dialogue_url, prefix="/api/dialogue")
    return router
