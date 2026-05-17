"""API 网关测试。

覆盖：
- GatewayRouter 路由匹配、前缀剥离、服务注册
- AuthMiddleware JWT 认证、白名单、可选模式
- GatewayRateLimitMiddleware 速率限制、IP 识别
- create_gateway_app 端到端转发（mock httpx）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import jwt
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from backend.gateway.auth import AuthMiddleware, create_token
from backend.gateway.main import create_gateway_app
from backend.gateway.rate_limit import GatewayRateLimitMiddleware
from backend.gateway.router import GatewayRouter, RouteTarget, setup_default_routes


# ===================================================================
# GatewayRouter
# ===================================================================


class TestGatewayRouter:
    """路由器单元测试。"""

    def test_register_and_match(self) -> None:
        router = GatewayRouter()
        router.register("poi", "http://localhost:8001", prefix="/api/poi")

        result = router.match("/api/poi/search", "GET")
        assert result is not None
        target, forward_path = result
        assert target.service == "poi"
        assert forward_path == "/search"

    def test_match_exact_prefix(self) -> None:
        """路径刚好等于前缀时也应匹配。"""
        router = GatewayRouter()
        router.register("route", "http://localhost:8002", prefix="/api/route")

        result = router.match("/api/route", "GET")
        assert result is not None
        target, forward_path = result
        assert target.service == "route"
        assert forward_path == "/"

    def test_no_match_returns_none(self) -> None:
        router = GatewayRouter()
        router.register("poi", "http://localhost:8001", prefix="/api/poi")

        assert router.match("/api/unknown", "GET") is None

    def test_method_filter(self) -> None:
        """不匹配的 HTTP 方法应返回 None。"""
        router = GatewayRouter()
        router.register("poi", "http://localhost:8001", prefix="/api/poi", methods=["GET"])

        assert router.match("/api/poi/search", "GET") is not None
        assert router.match("/api/poi/search", "DELETE") is None

    def test_strip_prefix_false(self) -> None:
        """strip_prefix=False 时保留完整路径。"""
        router = GatewayRouter()
        router.register(
            "dialogue", "http://localhost:8003", prefix="/api/dialogue", strip_prefix=False
        )

        result = router.match("/api/dialogue/chat", "POST")
        assert result is not None
        _, forward_path = result
        assert forward_path == "/api/dialogue/chat"

    def test_first_match_wins(self) -> None:
        """多个路由匹配时，第一个注册的优先。"""
        router = GatewayRouter()
        router.register("svc1", "http://localhost:8001", prefix="/api")
        router.register("svc2", "http://localhost:8002", prefix="/api/poi")

        result = router.match("/api/poi/search", "GET")
        assert result is not None
        target, _ = result
        assert target.service == "svc1"

    def test_get_service_url(self) -> None:
        router = GatewayRouter()
        router.register("poi", "http://localhost:8001", prefix="/api/poi")

        assert router.get_service_url("poi") == "http://localhost:8001"
        assert router.get_service_url("unknown") is None

    def test_service_names(self) -> None:
        router = GatewayRouter()
        router.register("poi", "http://localhost:8001", prefix="/api/poi")
        router.register("route", "http://localhost:8002", prefix="/api/route")

        assert router.service_names == ["poi", "route"]

    def test_setup_default_routes(self) -> None:
        router = setup_default_routes(
            poi_url="http://poi:9001",
            route_url="http://route:9002",
            dialogue_url="http://dialogue:9003",
        )

        assert "poi" in router.service_names
        assert "route" in router.service_names
        assert "dialogue" in router.service_names
        assert router.get_service_url("poi") == "http://poi:9001"

        # 验证路由匹配
        result = router.match("/api/poi/detail/123", "GET")
        assert result is not None
        target, forward_path = result
        assert target.service == "poi"
        assert forward_path == "/detail/123"


class TestRouteTarget:
    """RouteTarget 数据类测试。"""

    def test_default_methods(self) -> None:
        target = RouteTarget(service="svc", prefix="/api")
        assert "GET" in target.methods
        assert "POST" in target.methods
        assert "PATCH" in target.methods

    def test_default_strip_prefix(self) -> None:
        target = RouteTarget(service="svc", prefix="/api")
        assert target.strip_prefix is True


# ===================================================================
# AuthMiddleware
# ===================================================================


SECRET = "test-secret-key-that-is-long-enough-for-hmac"


class TestAuthMiddleware:
    """JWT 认证中间件测试。"""

    def _make_app(self, optional: bool = False):
        """创建带认证中间件的最小 FastAPI 应用。"""
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(AuthMiddleware, secret_key=SECRET, optional=optional)

        @app.get("/protected")
        async def protected():
            return {"ok": True}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app

    def test_whitelisted_path_skips_auth(self) -> None:
        """白名单路径不需要认证。"""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_missing_token_returns_401(self) -> None:
        """缺少 token 应返回 401。"""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == 2001

    def test_valid_token_passes(self) -> None:
        """有效 token 应通过认证。"""
        app = self._make_app()
        client = TestClient(app)
        token = create_token({"sub": "user-1"}, SECRET)
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_expired_token_returns_401(self) -> None:
        """过期 token 应返回 401。"""
        app = self._make_app()
        client = TestClient(app)
        token = create_token({"sub": "user-1"}, SECRET, expires_in=-10)
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == 2003

    def test_invalid_token_returns_401(self) -> None:
        """无效 token 应返回 401。"""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/protected", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401

    def test_optional_mode_no_token(self) -> None:
        """optional=True 时缺少 token 也放行。"""
        app = self._make_app(optional=True)
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_query_param_token(self) -> None:
        """支持 query 参数传 token（SSE 场景）。"""
        app = self._make_app()
        client = TestClient(app)
        token = create_token({"sub": "user-1"}, SECRET)
        resp = client.get(f"/protected?token={token}")
        assert resp.status_code == 200

    def test_docs_whitelisted(self) -> None:
        """/docs 白名单放行。"""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/docs")
        assert resp.status_code == 200


class TestCreateToken:
    """create_token 辅助函数测试。"""

    def test_token_decodes_correctly(self) -> None:
        token = create_token({"sub": "u1", "role": "admin"}, SECRET)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["sub"] == "u1"
        assert payload["role"] == "admin"
        assert "iat" in payload
        assert "exp" in payload

    def test_custom_expiry(self) -> None:
        token = create_token({"sub": "u1"}, SECRET, expires_in=60)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 60


# ===================================================================
# GatewayRateLimitMiddleware
# ===================================================================


class TestGatewayRateLimitMiddleware:
    """速率限制中间件测试。"""

    def _make_app(self, rpm: int = 5):
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(GatewayRateLimitMiddleware, requests_per_minute=rpm)

        @app.get("/api/test")
        async def test_endpoint():
            return {"ok": True}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app

    def test_within_limit(self) -> None:
        """未超限时正常返回，包含限流头。"""
        app = self._make_app(rpm=10)
        client = TestClient(app)
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers

    def test_exceed_limit_returns_429(self) -> None:
        """超过限额应返回 429。"""
        app = self._make_app(rpm=3)
        client = TestClient(app)

        for _ in range(3):
            client.get("/api/test")

        resp = client.get("/api/test")
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == 1005
        assert "Retry-After" in resp.headers

    def test_whitelist_path_bypasses_limit(self) -> None:
        """白名单路径不受限流限制。"""
        app = self._make_app(rpm=1)
        client = TestClient(app)

        # 先用掉配额
        client.get("/api/test")

        # health 是白名单，应正常返回
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_get_client_ip_from_forwarded_for(self) -> None:
        """优先使用 X-Forwarded-For 头。"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"1.2.3.4, 5.6.7.8")],
        }
        request = StarletteRequest(scope)
        ip = GatewayRateLimitMiddleware._get_client_ip(request)
        assert ip == "1.2.3.4"

    def test_get_client_ip_from_real_ip(self) -> None:
        """回退到 X-Real-IP 头。"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-real-ip", b"10.0.0.1")],
        }
        request = StarletteRequest(scope)
        ip = GatewayRateLimitMiddleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_unknown(self) -> None:
        """无头时返回 unknown。"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        }
        request = StarletteRequest(scope)
        ip = GatewayRateLimitMiddleware._get_client_ip(request)
        assert ip == "unknown"


# ===================================================================
# End-to-end gateway app
# ===================================================================


class TestGatewayApp:
    """网关应用集成测试。"""

    def _make_gateway(self) -> TestClient:
        app = create_gateway_app(
            jwt_secret=SECRET,
            auth_optional=True,
            rate_limit=1000,  # 测试时不触发限流
        )
        return TestClient(app, raise_server_exceptions=False)

    def test_health_endpoint(self) -> None:
        """健康检查不走转发。"""
        client = self._make_gateway()
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "poi" in data["services"]

    def test_unknown_service_returns_404(self) -> None:
        """未注册的服务路径返回 404。"""
        client = self._make_gateway()
        resp = client.get("/api/unknown/endpoint")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == 1002

    @patch("backend.gateway.main.httpx.AsyncClient")
    def test_forward_request_success(self, mock_client_cls) -> None:
        """成功转发请求到后端服务。"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b'{"results": []}'
        mock_response.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        client = self._make_gateway()
        resp = client.get("/api/poi/search?keyword=test")

        assert resp.status_code == 200
        call_args = mock_client.request.call_args
        target_url = call_args.kwargs.get("url", "")
        assert "8001" in target_url
        assert "/search" in target_url

    @patch("backend.gateway.main.httpx.AsyncClient")
    def test_forward_request_connect_error(self, mock_client_cls) -> None:
        """后端服务不可达时返回 502。"""
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        client = self._make_gateway()
        resp = client.get("/api/poi/search")

        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == 5002

    @patch("backend.gateway.main.httpx.AsyncClient")
    def test_forward_request_timeout(self, mock_client_cls) -> None:
        """后端服务超时时返回 504。"""
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        client = self._make_gateway()
        resp = client.get("/api/route/plan")

        assert resp.status_code == 504
        assert resp.json()["error"]["code"] == 1004

    @patch("backend.gateway.main.httpx.AsyncClient")
    def test_forward_preserves_query_string(self, mock_client_cls) -> None:
        """转发时保留 query string。"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        client = self._make_gateway()
        client.get("/api/poi/search?keyword=test&page=2")

        call_args = mock_client.request.call_args
        target_url = call_args.kwargs.get("url", "")
        assert "keyword=test" in target_url
        assert "page=2" in target_url

    @patch("backend.gateway.main.httpx.AsyncClient")
    def test_forward_strips_prefix(self, mock_client_cls) -> None:
        """转发时剥离 /api/poi 前缀。"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        client = self._make_gateway()
        client.get("/api/poi/detail/123")

        call_args = mock_client.request.call_args
        target_url = call_args.kwargs.get("url", "")
        # 前缀应被剥离，只保留 /detail/123
        assert target_url.endswith("/detail/123")
        assert "/api/poi" not in target_url.split("8001")[1]

    @patch("backend.gateway.main.httpx.AsyncClient")
    def test_forward_injects_headers(self, mock_client_cls) -> None:
        """转发时注入 X-Forwarded-For 和 X-Request-ID 头。"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        client = self._make_gateway()
        client.get("/api/route/plan")

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers", {})
        assert "X-Forwarded-For" in headers
        assert "X-Request-ID" in headers
        assert "X-Forwarded-Host" in headers
        assert "X-Forwarded-Proto" in headers
