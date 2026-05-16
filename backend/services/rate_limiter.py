"""CityFlow 速率限制器服务。

提供灵活的速率限制功能，支持：
- Redis 分布式滑动窗口（多实例共享）
- 本地内存固定窗口（单实例降级）
- 按用户 ID / IP / API Key 等维度限流
- 标准 RateLimit 响应头注入

与 middleware/rate_limit.py 的区别：
- middleware 层：基于 IP 的简单滑动窗口，保护全局入口
- service 层：可编程的限流器，支持自定义 key / limit / window，
  可在路由层或业务层按需调用
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

import redis.asyncio as aioredis

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

__all__ = [
    "RateLimiter",
    "RateLimitResult",
    "RateLimitExceededError",
    "get_rate_limiter",
]


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class RateLimitExceededError(CityFlowException):
    """速率限制超出。"""

    def __init__(
        self,
        message: str = "请求过于频繁，请稍后再试",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            message=message,
            details=details,
        )


# ---------------------------------------------------------------------------
# 限流结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """速率限制检查结果。"""

    allowed: bool
    limit: int
    remaining: int
    reset_ts: int  # 窗口重置的 Unix 时间戳

    def to_headers(self) -> dict[str, str]:
        """转换为标准 RateLimit 响应头。"""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_ts),
        }


# ---------------------------------------------------------------------------
# 本地内存限流（固定窗口）
# ---------------------------------------------------------------------------


@dataclass
class _LocalWindow:
    """本地固定窗口计数器。"""

    count: int = 0
    start_ts: float = field(default_factory=time.monotonic)


class _LocalRateLimiter:
    """本地内存固定窗口限流器，单实例降级方案。

    不支持跨进程共享，适合开发环境或 Redis 不可用时。
    """

    def __init__(self) -> None:
        self._windows: dict[str, _LocalWindow] = {}

    async def check(self, key: str, limit: int, window: int) -> RateLimitResult:
        now = time.monotonic()
        win = self._windows.get(key)

        if win is None or now - win.start_ts >= window:
            # 新窗口
            win = _LocalWindow(count=0, start_ts=now)
            self._windows[key] = win

        remaining = max(0, limit - win.count - 1)
        allowed = win.count < limit

        if allowed:
            win.count += 1

        reset_ts = int(time.time() + window - (now - win.start_ts))
        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining if allowed else 0,
            reset_ts=reset_ts,
        )

    def cleanup(self, max_idle_seconds: int = 600) -> int:
        """清理长时间无活动的窗口，返回清理数量。"""
        now = time.monotonic()
        stale = [
            k for k, w in self._windows.items() if now - w.start_ts > max_idle_seconds
        ]
        for k in stale:
            del self._windows[k]
        return len(stale)


# ---------------------------------------------------------------------------
# Redis 滑动窗口限流
# ---------------------------------------------------------------------------


class _RedisRateLimiter:
    """基于 Redis Sorted Set 的滑动窗口限流器。

    使用 ZREMRANGEBYSCORE + ZCARD + EXPIRE 的 pipeline 实现，
    原子性强，支持多实例共享。
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._prefix = "cityflow:ratelimit:"

    async def check(self, key: str, limit: int, window: int) -> RateLimitResult:
        full_key = self._prefix + key
        now = time.time()
        window_start = now - window

        pipe = self._redis.pipeline(transaction=True)
        # 清理窗口外的旧记录
        pipe.zremrangebyscore(full_key, 0, window_start)
        # 添加当前请求时间戳（用微秒避免 key 冲突）
        pipe.zadd(full_key, {f"{now:.6f}": now})
        # 获取窗口内请求数
        pipe.zcard(full_key)
        # 设置键过期时间（兜底清理）
        pipe.expire(full_key, window + 1)
        results = await pipe.execute()

        current_count: int = results[2]
        allowed = current_count <= limit
        remaining = max(0, limit - current_count)
        reset_ts = int(now + window)

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining if allowed else 0,
            reset_ts=reset_ts,
        )


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------


class RateLimiter:
    """速率限制器统一入口。

    优先使用 Redis 实现分布式限流；Redis 不可用时自动降级到本地内存。

    用法::

        limiter = get_rate_limiter()
        result = await limiter.is_allowed("user:123", limit=60, window=60)
        if not result.allowed:
            raise RateLimitExceededError(details=result.to_headers())
    """

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        if redis_client is not None:
            self._backend: _RedisRateLimiter | _LocalRateLimiter = _RedisRateLimiter(
                redis_client
            )
            self._use_redis = True
            logger.info("速率限制器已初始化（Redis 模式）")
        else:
            self._backend = _LocalRateLimiter()
            self._use_redis = False
            logger.info("速率限制器已初始化（本地内存模式）")

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int = 60,
    ) -> RateLimitResult:
        """检查是否允许请求。

        Args:
            key: 限制维度键，如 ``"user:123"``、``"ip:1.2.3.4"``。
            limit: 时间窗口内允许的最大请求数。
            window: 时间窗口大小（秒），默认 60。

        Returns:
            RateLimitResult 包含是否允许、剩余配额、重置时间。
        """
        return await self._backend.check(key, limit, window)

    @property
    def backend_type(self) -> str:
        """当前后端类型：``"redis"`` 或 ``"local"``。"""
        return "redis" if self._use_redis else "local"

    async def cleanup_local(self) -> int:
        """清理本地内存中的过期窗口。仅本地模式有效。"""
        if isinstance(self._backend, _LocalRateLimiter):
            return self._backend.cleanup()
        return 0


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """获取全局速率限制器单例。

    首次调用时根据配置自动创建。如配置了 Redis 则使用分布式模式，
    否则降级到本地内存。
    """
    global _limiter
    if _limiter is None:
        from backend.config import settings

        redis_client: aioredis.Redis | None = None
        redis_cfg = settings.redis
        if redis_cfg.host:
            url = f"redis://{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
            if redis_cfg.password:
                url = f"redis://:{quote_plus(redis_cfg.password)}@{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
            redis_client = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        _limiter = RateLimiter(redis_client)
    return _limiter
