"""CityFlow API 网关入口。

将请求路由转发到后端微服务（POI、路线、对话），
集成 JWT 认证和速率限制中间件。

用法::

    # 作为独立服务运行
    uvicorn backend.gateway.main:app --port 9000

    # 或在代码中创建
    from backend.gateway.main import create_gateway_app
    app = create_gateway_app()
"""

from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from backend.gateway.auth import AuthMiddleware
from backend.gateway.rate_limit import GatewayRateLimitMiddleware
from backend.gateway.router import GatewayRouter, setup_default_routes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 超时配置（秒）
# ---------------------------------------------------------------------------
_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 30.0
_WRITE_TIMEOUT = 10.0


def create_gateway_app(
    *,
    router: GatewayRouter | None = None,
    jwt_secret: str = "change-me-in-production",
    auth_optional: bool = True,
    rate_limit: int = 120,
) -> FastAPI:
    """创建网关 FastAPI 应用。

    Args:
        router: 自定义路由器，为 ``None`` 时使用默认配置。
        jwt_secret: JWT 签名密钥。
        auth_optional: 认证是否可选（开发模式为 ``True``）。
        rate_limit: 每分钟最大请求数。

    Returns:
        配置好的 FastAPI 实例。
    """
    gateway_app = FastAPI(
        title="CityFlow API Gateway",
        description="请求路由转发、认证授权、速率限制",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # ---- 路由 ----
    gw_router = router or setup_default_routes()
    gateway_app.state.router = gw_router

    # ---- 中间件（从外到内执行顺序） ----

    # CORS
    gateway_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID",
        ],
    )

    # 速率限制
    gateway_app.add_middleware(
        GatewayRateLimitMiddleware,
        requests_per_minute=rate_limit,
    )

    # JWT 认证
    gateway_app.add_middleware(
        AuthMiddleware,
        secret_key=jwt_secret,
        optional=auth_optional,
    )

    # ---- 健康检查（不走转发，必须在 catch-all 之前注册） ----

    @gateway_app.get("/health", summary="网关健康检查", tags=["系统"])
    async def health():
        """网关自身健康检查。"""
        router_instance: GatewayRouter = gateway_app.state.router
        return {
            "status": "ok",
            "services": router_instance.service_names,
        }

    # ---- 核心路由：catch-all 转发 ----

    @gateway_app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        summary="网关转发",
        description="将请求转发到对应的后端微服务。",
    )
    async def gateway_forward(request: Request, path: str) -> Response:
        """核心转发逻辑。

        流程：
        1. 根据路径匹配后端服务
        2. 构建目标 URL
        3. 转发请求头、body、query params
        4. 返回后端响应
        """
        gw_router: GatewayRouter = request.app.state.router
        match_result = gw_router.match(f"/{path}", request.method)

        if match_result is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": 1002,
                        "message": f"未找到匹配的服务: /{path}",
                    }
                },
            )

        route_target, forward_path = match_result
        base_url = gw_router.get_service_url(route_target.service)
        target_url = f"{base_url}{forward_path}"

        # 保留 query string
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        # 构建转发头
        headers = _build_forward_headers(request)

        logger.debug(
            "转发请求: %s %s -> %s",
            request.method,
            request.url.path,
            target_url,
        )

        # 执行转发
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=_READ_TIMEOUT,
                    write=_WRITE_TIMEOUT,
                    pool=_CONNECT_TIMEOUT,
                ),
                follow_redirects=True,
            ) as client:
                backend_response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=await request.body(),
                )
        except httpx.ConnectError:
            logger.error("无法连接后端服务: %s", target_url)
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "code": 5002,
                        "message": f"后端服务不可达: {route_target.service}",
                    }
                },
            )
        except httpx.TimeoutException:
            logger.error("后端服务超时: %s", target_url)
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": 1004,
                        "message": f"后端服务响应超时: {route_target.service}",
                    }
                },
            )

        # 过滤 hop-by-hop 头
        response_headers = {
            k: v
            for k, v in backend_response.headers.items()
            if k.lower()
            not in {
                "transfer-encoding",
                "connection",
                "keep-alive",
                "content-encoding",
                "content-length",
            }
        }

        return Response(
            content=backend_response.content,
            status_code=backend_response.status_code,
            headers=response_headers,
        )

    # ---- 生命周期 ----

    @gateway_app.on_event("startup")
    async def on_startup():
        logger.info(
            "API 网关启动完成 | 服务: %s",
            gw_router.service_names,
        )

    return gateway_app


# ---------------------------------------------------------------------------
# 默认 app 实例（可直接 uvicorn backend.gateway.main:app）
# ---------------------------------------------------------------------------

app = create_gateway_app()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _build_forward_headers(request: Request) -> dict[str, str]:
    """构建转发请求头。

    过滤 hop-by-hop 头，注入网关追踪信息。
    """
    # hop-by-hop 头（不应转发）
    skip = {
        "host",
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
    }

    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() not in skip:
            headers[key] = value

    # 注入网关信息
    if request.client:
        headers["X-Forwarded-For"] = request.client.host
    headers["X-Forwarded-Host"] = request.headers.get("host", "")
    headers["X-Forwarded-Proto"] = request.url.scheme

    # 请求追踪 ID
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    headers["X-Request-ID"] = request_id

    # 注入已认证的用户信息（供后端使用）
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        headers["X-User-ID"] = str(user_id)

    return headers
