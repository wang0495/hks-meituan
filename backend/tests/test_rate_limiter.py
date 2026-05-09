"""速率限制器单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.rate_limiter import (RateLimiter, RateLimitExceededError,
                                           RateLimitResult, _LocalRateLimiter)


class TestRateLimitResult:
    def test_to_headers(self) -> None:
        result = RateLimitResult(
            allowed=True, limit=60, remaining=55, reset_ts=1700000060
        )
        headers = result.to_headers()
        assert headers["X-RateLimit-Limit"] == "60"
        assert headers["X-RateLimit-Remaining"] == "55"
        assert headers["X-RateLimit-Reset"] == "1700000060"

    def test_allowed_is_true_when_within_limit(self) -> None:
        result = RateLimitResult(allowed=True, limit=10, remaining=5, reset_ts=0)
        assert result.allowed is True

    def test_allowed_is_false_when_exceeded(self) -> None:
        result = RateLimitResult(allowed=False, limit=10, remaining=0, reset_ts=0)
        assert result.allowed is False


class TestLocalRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_first_request(self) -> None:
        limiter = _LocalRateLimiter()
        result = await limiter.check("test:key", limit=5, window=60)
        assert result.allowed is True
        assert result.remaining == 4

    @pytest.mark.asyncio
    async def test_blocks_after_limit_reached(self) -> None:
        limiter = _LocalRateLimiter()
        for _ in range(5):
            await limiter.check("test:key", limit=5, window=60)

        result = await limiter.check("test:key", limit=5, window=60)
        assert result.allowed is False
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_different_keys_independent(self) -> None:
        limiter = _LocalRateLimiter()
        for _ in range(5):
            await limiter.check("user:a", limit=5, window=60)

        # user:a 已满，user:b 应该还能用
        result_b = await limiter.check("user:b", limit=5, window=60)
        assert result_b.allowed is True

        result_a = await limiter.check("user:a", limit=5, window=60)
        assert result_a.allowed is False

    @pytest.mark.asyncio
    async def test_window_reset(self) -> None:
        limiter = _LocalRateLimiter()
        # 用极短窗口
        for _ in range(3):
            await limiter.check("test:reset", limit=3, window=1)

        result = await limiter.check("test:reset", limit=3, window=1)
        assert result.allowed is False

        # 等窗口过期
        await asyncio.sleep(1.1)
        result = await limiter.check("test:reset", limit=3, window=1)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_remaining_decrements(self) -> None:
        limiter = _LocalRateLimiter()
        r1 = await limiter.check("test:dec", limit=3, window=60)
        r2 = await limiter.check("test:dec", limit=3, window=60)
        r3 = await limiter.check("test:dec", limit=3, window=60)

        assert r1.remaining == 2
        assert r2.remaining == 1
        assert r3.remaining == 0

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale_windows(self) -> None:
        limiter = _LocalRateLimiter()
        # 先触发一个请求创建窗口
        await limiter.check("stale:key", limit=1, window=60)
        # 手动把窗口的 start_ts 改到很久以前，模拟过期
        import time

        limiter._windows["stale:key"].start_ts = time.monotonic() - 9999
        cleaned = limiter.cleanup(max_idle_seconds=600)
        assert cleaned == 1


class TestRateLimiterWithoutRedis:
    """测试无 Redis 时的本地模式。"""

    @pytest.mark.asyncio
    async def test_uses_local_backend(self) -> None:
        limiter = RateLimiter(redis_client=None)
        assert limiter.backend_type == "local"

    @pytest.mark.asyncio
    async def test_is_allowed_delegates_to_local(self) -> None:
        limiter = RateLimiter(redis_client=None)
        result = await limiter.is_allowed("user:1", limit=2, window=60)
        assert result.allowed is True

        result = await limiter.is_allowed("user:1", limit=2, window=60)
        assert result.allowed is True

        result = await limiter.is_allowed("user:1", limit=2, window=60)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_cleanup_local_noop_for_redis_mode(self) -> None:
        # 本地模式下 cleanup 有效
        limiter = RateLimiter(redis_client=None)
        assert await limiter.cleanup_local() == 0


class TestRateLimitExceededError:
    def test_default_message(self) -> None:
        err = RateLimitExceededError()
        assert "频繁" in err.message
        assert err.status_code == 429

    def test_custom_details(self) -> None:
        err = RateLimitExceededError(
            details={"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0"}
        )
        assert err.details["X-RateLimit-Limit"] == "60"
        assert err.to_dict()["error"]["code"] == 1005
