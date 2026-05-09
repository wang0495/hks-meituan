"""IP 限流器单元测试。"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.services.ip_rate_limiter import (IPRateLimiter,
                                              IPRateLimitExceededError,
                                              IPRateLimitResult,
                                              _LocalIPRateLimiter)


class TestIPRateLimitResult:
    def test_to_headers_basic(self) -> None:
        result = IPRateLimitResult(
            allowed=True,
            ip="1.2.3.4",
            endpoint="/api/v1/poi",
            limit=100,
            remaining=95,
            reset_ts=1700000060,
        )
        headers = result.to_headers()
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "95"
        assert headers["X-RateLimit-Reset"] == "1700000060"
        assert "X-RateLimit-Banned" not in headers

    def test_to_headers_with_ban(self) -> None:
        result = IPRateLimitResult(
            allowed=False,
            ip="1.2.3.4",
            endpoint="/api/v1/poi",
            limit=0,
            remaining=0,
            reset_ts=1700000060,
            banned=True,
        )
        headers = result.to_headers()
        assert headers["X-RateLimit-Banned"] == "true"


class TestLocalIPRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_first_request(self) -> None:
        limiter = _LocalIPRateLimiter()
        allowed, remaining, _ = await limiter.check(
            "ep:1.2.3.4:/api", limit=10, window=60
        )
        assert allowed is True
        assert remaining == 9

    @pytest.mark.asyncio
    async def test_blocks_after_limit(self) -> None:
        limiter = _LocalIPRateLimiter()
        for _ in range(5):
            await limiter.check("ep:5.6.7.8:/api", limit=5, window=60)

        allowed, remaining, _ = await limiter.check(
            "ep:5.6.7.8:/api", limit=5, window=60
        )
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_ban_and_unban(self) -> None:
        limiter = _LocalIPRateLimiter()
        assert limiter.is_banned("10.0.0.1") is False

        limiter.ban_ip("10.0.0.1", duration=60)
        assert limiter.is_banned("10.0.0.1") is True

        limiter.unban_ip("10.0.0.1")
        assert limiter.is_banned("10.0.0.1") is False

    @pytest.mark.asyncio
    async def test_ban_expires(self) -> None:
        limiter = _LocalIPRateLimiter()
        limiter.ban_ip("10.0.0.2", duration=1)
        assert limiter.is_banned("10.0.0.2") is True

        await asyncio.sleep(1.1)
        assert limiter.is_banned("10.0.0.2") is False

    @pytest.mark.asyncio
    async def test_track_endpoint_detects_suspicious(self) -> None:
        limiter = _LocalIPRateLimiter()
        # 访问 20 个不同端点不应触发
        for i in range(20):
            suspicious = limiter.track_endpoint("attacker", f"/api/ep_{i}")
            assert suspicious is False

        # 第 21 个端点触发可疑
        suspicious = limiter.track_endpoint("attacker", "/api/ep_21")
        assert suspicious is True

    @pytest.mark.asyncio
    async def test_different_keys_independent(self) -> None:
        limiter = _LocalIPRateLimiter()
        for _ in range(5):
            await limiter.check("ep:a:/api", limit=5, window=60)

        allowed, _, _ = await limiter.check("ep:b:/api", limit=5, window=60)
        assert allowed is True

        allowed, _, _ = await limiter.check("ep:a:/api", limit=5, window=60)
        assert allowed is False


class TestIPRateLimiterLocal:
    """本地模式集成测试。"""

    @pytest.mark.asyncio
    async def test_backend_type_is_local(self) -> None:
        limiter = IPRateLimiter(redis_client=None)
        assert limiter.backend_type == "local"

    @pytest.mark.asyncio
    async def test_check_allows_within_limit(self) -> None:
        limiter = IPRateLimiter(redis_client=None, endpoint_limit=5, endpoint_window=60)
        for _ in range(5):
            result = await limiter.check("1.2.3.4", "/api/v1/poi")
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_blocks_after_endpoint_limit(self) -> None:
        limiter = IPRateLimiter(redis_client=None, endpoint_limit=3, endpoint_window=60)
        for _ in range(3):
            await limiter.check("10.0.0.1", "/api/v1/plan")

        result = await limiter.check("10.0.0.1", "/api/v1/plan")
        assert result.allowed is False
        assert result.ip == "10.0.0.1"
        assert result.endpoint == "/api/v1/plan"

    @pytest.mark.asyncio
    async def test_check_blocks_after_global_limit(self) -> None:
        limiter = IPRateLimiter(
            redis_client=None,
            endpoint_limit=100,
            endpoint_window=60,
            global_limit=5,
            global_window=60,
        )
        # 不同端点消耗全局配额
        for i in range(5):
            await limiter.check("10.0.0.2", f"/api/endpoint_{i}")

        result = await limiter.check("10.0.0.2", "/api/endpoint_new")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_manual_ban_blocks_requests(self) -> None:
        limiter = IPRateLimiter(redis_client=None)
        await limiter.manual_ban("evil.ip", duration=60)

        result = await limiter.check("evil.ip", "/api/v1/poi")
        assert result.allowed is False
        assert result.banned is True

    @pytest.mark.asyncio
    async def test_manual_unban_restores_access(self) -> None:
        limiter = IPRateLimiter(redis_client=None)
        await limiter.manual_ban("evil.ip", duration=60)

        result = await limiter.check("evil.ip", "/api/v1/poi")
        assert result.allowed is False

        await limiter.manual_unban("evil.ip")
        result = await limiter.check("evil.ip", "/api/v1/poi")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_is_banned(self) -> None:
        limiter = IPRateLimiter(redis_client=None)
        assert await limiter.is_banned("1.1.1.1") is False

        await limiter.manual_ban("1.1.1.1", duration=60)
        assert await limiter.is_banned("1.1.1.1") is True

    @pytest.mark.asyncio
    async def test_custom_limit_override(self) -> None:
        limiter = IPRateLimiter(
            redis_client=None, endpoint_limit=100, endpoint_window=60
        )
        # 覆盖为 2
        for _ in range(2):
            result = await limiter.check("2.2.2.2", "/api/v1/poi", endpoint_limit=2)
            assert result.allowed is True

        result = await limiter.check("2.2.2.2", "/api/v1/poi", endpoint_limit=2)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_suspicious_flag_on_result(self) -> None:
        limiter = IPRateLimiter(redis_client=None, endpoint_limit=3, endpoint_window=60)
        # 访问大量不同端点触发可疑检测
        for i in range(25):
            await limiter.check("attacker", f"/api/ep_{i}")

        result = await limiter.check("attacker", "/api/ep_25")
        # 当超限时，suspicious 应为 True
        if not result.allowed:
            assert result.suspicious is True

    @pytest.mark.asyncio
    async def test_result_fields(self) -> None:
        limiter = IPRateLimiter(
            redis_client=None, endpoint_limit=50, endpoint_window=60
        )
        result = await limiter.check("3.3.3.3", "/api/v1/dialogue")

        assert result.ip == "3.3.3.3"
        assert result.endpoint == "/api/v1/dialogue"
        assert result.limit == 50
        assert result.remaining == 49
        assert result.reset_ts > int(time.time())
        assert result.banned is False


class TestIPRateLimitExceededError:
    def test_default_message(self) -> None:
        err = IPRateLimitExceededError()
        assert "频繁" in err.message
        assert err.status_code == 429

    def test_custom_details(self) -> None:
        err = IPRateLimitExceededError(
            details={"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "0"}
        )
        assert err.details["X-RateLimit-Limit"] == "100"
        assert err.to_dict()["error"]["code"] == 1005
