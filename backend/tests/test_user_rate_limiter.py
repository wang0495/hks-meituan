"""用户限流器单元测试。"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.services.user_rate_limiter import (EndpointTier, UserRateLimiter,
                                                UserRateLimitExceededError,
                                                UserRateLimitResult,
                                                _LocalUserRateLimiter,
                                                register_whitelist_user,
                                                remove_whitelist_user,
                                                resolve_endpoint_tier)


class TestEndpointTier:
    def test_resolve_plan_route(self) -> None:
        assert resolve_endpoint_tier("/api/v1/plan_route") == EndpointTier.PLAN_ROUTE
        assert resolve_endpoint_tier("/api/v2/plan/anything") == EndpointTier.PLAN_ROUTE

    def test_resolve_search_poi(self) -> None:
        assert resolve_endpoint_tier("/api/v1/poi/search") == EndpointTier.SEARCH_POI
        assert resolve_endpoint_tier("/api/v2/poi/detail") == EndpointTier.SEARCH_POI

    def test_resolve_dialogue(self) -> None:
        assert resolve_endpoint_tier("/api/v1/dialogue") == EndpointTier.DIALOGUE

    def test_resolve_default_for_unknown(self) -> None:
        assert resolve_endpoint_tier("/api/v1/unknown") == EndpointTier.DEFAULT
        assert resolve_endpoint_tier("/health") == EndpointTier.DEFAULT


class TestUserRateLimitResult:
    def test_to_headers(self) -> None:
        result = UserRateLimitResult(
            allowed=True,
            user_id="u1",
            endpoint="/api/v1/plan_route",
            tier=EndpointTier.PLAN_ROUTE,
            limit=10,
            remaining=7,
            reset_ts=1700000060,
        )
        headers = result.to_headers()
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "7"
        assert headers["X-RateLimit-Reset"] == "1700000060"
        assert headers["X-RateLimit-Endpoint"] == "/api/v1/plan_route"


class TestLocalUserRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_first_request(self) -> None:
        limiter = _LocalUserRateLimiter()
        allowed, remaining, _ = await limiter.check("key", limit=5, window=60)
        assert allowed is True
        assert remaining == 4

    @pytest.mark.asyncio
    async def test_blocks_after_limit(self) -> None:
        limiter = _LocalUserRateLimiter()
        for _ in range(5):
            await limiter.check("key", limit=5, window=60)

        allowed, remaining, _ = await limiter.check("key", limit=5, window=60)
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_window_reset(self) -> None:
        limiter = _LocalUserRateLimiter()
        for _ in range(3):
            await limiter.check("key:reset", limit=3, window=1)

        allowed, _, _ = await limiter.check("key:reset", limit=3, window=1)
        assert allowed is False

        await asyncio.sleep(1.1)
        allowed, _, _ = await limiter.check("key:reset", limit=3, window=1)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_different_keys_independent(self) -> None:
        limiter = _LocalUserRateLimiter()
        for _ in range(3):
            await limiter.check("user:a", limit=3, window=60)

        allowed, _, _ = await limiter.check("user:b", limit=3, window=60)
        assert allowed is True

        allowed, _, _ = await limiter.check("user:a", limit=3, window=60)
        assert allowed is False


class TestUserRateLimiterLocal:
    """本地模式集成测试。"""

    @pytest.mark.asyncio
    async def test_backend_type_is_local(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        assert limiter.backend_type == "local"

    @pytest.mark.asyncio
    async def test_check_respects_endpoint_tier(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        # plan_route 限制为 10 次
        for _ in range(10):
            result = await limiter.check("user_1", "/api/v1/plan_route")
            assert result.allowed is True

        result = await limiter.check("user_1", "/api/v1/plan_route")
        assert result.allowed is False
        assert result.tier == EndpointTier.PLAN_ROUTE

    @pytest.mark.asyncio
    async def test_different_endpoints_independent(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        # plan_route 耗尽
        for _ in range(10):
            await limiter.check("user_2", "/api/v1/plan_route")

        # search_poi 仍然可用
        result = await limiter.check("user_2", "/api/v1/poi/search")
        assert result.allowed is True
        assert result.tier == EndpointTier.SEARCH_POI

    @pytest.mark.asyncio
    async def test_multiplier_reduces_limit(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        # plan_route 默认 10，multiplier=0.5 -> 实际 5
        for _ in range(5):
            result = await limiter.check("user_3", "/api/v1/plan_route", multiplier=0.5)
            assert result.allowed is True

        result = await limiter.check("user_3", "/api/v1/plan_route", multiplier=0.5)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_multiplier_increases_limit(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        # plan_route 默认 10，multiplier=2.0 -> 实际 20
        for _ in range(15):
            result = await limiter.check("user_4", "/api/v1/plan_route", multiplier=2.0)
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_whitelist_user_always_allowed(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        register_whitelist_user("vip_user")
        try:
            for _ in range(100):
                result = await limiter.check("vip_user", "/api/v1/plan_route")
                assert result.allowed is True
        finally:
            remove_whitelist_user("vip_user")

    @pytest.mark.asyncio
    async def test_check_with_tier(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        for _ in range(100):
            result = await limiter.check_with_tier(
                "user_5", "/custom/endpoint", EndpointTier.SEARCH_POI
            )
            assert result.allowed is True

        result = await limiter.check_with_tier(
            "user_5", "/custom/endpoint", EndpointTier.SEARCH_POI
        )
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_result_contains_correct_fields(self) -> None:
        limiter = UserRateLimiter(redis_client=None)
        result = await limiter.check("user_6", "/api/v1/dialogue")

        assert result.user_id == "user_6"
        assert result.endpoint == "/api/v1/dialogue"
        assert result.tier == EndpointTier.DIALOGUE
        assert result.limit == 30
        assert result.remaining == 29
        assert result.reset_ts > int(time.time())


class TestUserRateLimitExceededError:
    def test_default_message(self) -> None:
        err = UserRateLimitExceededError()
        assert "频繁" in err.message
        assert err.status_code == 429

    def test_custom_details(self) -> None:
        err = UserRateLimitExceededError(
            details={"X-RateLimit-Limit": "10", "X-RateLimit-Remaining": "0"}
        )
        assert err.details["X-RateLimit-Limit"] == "10"
        assert err.to_dict()["error"]["code"] == 1005
