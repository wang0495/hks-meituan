"""CityFlow 用户级限流器。

在通用 RateLimiter 基础上增加：
- 按用户 ID + 端点维度限流
- 端点级自定义配额（如路线规划 10次/分钟，POI搜索 100次/分钟）
- 白名单 / VIP 用户倍率
- 与 Redis 分布式 / 本地内存双模式兼容

用法::

    limiter = get_user_rate_limiter()
    result = await limiter.check("user_abc", "/api/v1/plan_route")
    if not result.allowed:
        raise RateLimitExceededError(details=result.to_headers())
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import quote_plus

import redis.asyncio as aioredis

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

__all__ = [
    "EndpointTier",
    "UserRateLimitExceededError",
    "UserRateLimitResult",
    "UserRateLimiter",
    "get_user_rate_limiter",
]


# ---------------------------------------------------------------------------
# 端点配额等级
# ---------------------------------------------------------------------------


class EndpointTier(str, Enum):
    """端点配额等级，用于统一管理不同端点的限流策略。"""

    DEFAULT = "default"
    PLAN_ROUTE = "plan_route"
    SEARCH_POI = "search_poi"
    DIALOGUE = "dialogue"


# 端点 -> (每窗口最大请求数, 窗口秒数)
ENDPOINT_LIMITS: dict[EndpointTier, tuple[int, int]] = {
    EndpointTier.DEFAULT: (60, 60),
    EndpointTier.PLAN_ROUTE: (10, 60),
    EndpointTier.SEARCH_POI: (100, 60),
    EndpointTier.DIALOGUE: (30, 60),
}

# 端点路径 -> 配额等级的映射（模糊前缀匹配）
_ENDPOINT_TIER_MAP: dict[str, EndpointTier] = {
    "/api/v1/plan": EndpointTier.PLAN_ROUTE,
    "/api/v2/plan": EndpointTier.PLAN_ROUTE,
    "/api/v1/route": EndpointTier.PLAN_ROUTE,
    "/api/v1/poi": EndpointTier.SEARCH_POI,
    "/api/v2/poi": EndpointTier.SEARCH_POI,
    "/api/v1/dialogue": EndpointTier.DIALOGUE,
    "/api/v2/dialogue": EndpointTier.DIALOGUE,
}

# 白名单用户：不受限流约束（VIP / 内部服务）
_WHITELIST_USERS: set[str] = set()


def register_whitelist_user(user_id: str) -> None:
    """注册白名单用户。"""
    _WHITELIST_USERS.add(user_id)


def remove_whitelist_user(user_id: str) -> None:
    """移除白名单用户。"""
    _WHITELIST_USERS.discard(user_id)


def resolve_endpoint_tier(endpoint: str) -> EndpointTier:
    """根据端点路径解析配额等级。"""
    for prefix, tier in _ENDPOINT_TIER_MAP.items():
        if endpoint.startswith(prefix):
            return tier
    return EndpointTier.DEFAULT


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class UserRateLimitExceededError(CityFlowException):
    """用户速率限制超出。"""

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
# 结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UserRateLimitResult:
    """用户限流检查结果。"""

    allowed: bool
    user_id: str
    endpoint: str
    tier: EndpointTier
    limit: int
    remaining: int
    reset_ts: int

    def to_headers(self) -> dict[str, str]:
        """转换为标准 RateLimit 响应头。"""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_ts),
            "X-RateLimit-Endpoint": self.endpoint,
        }


# ---------------------------------------------------------------------------
# 本地内存实现
# ---------------------------------------------------------------------------


@dataclass
class _LocalWindow:
    """本地固定窗口计数器。"""

    count: int = 0
    start_ts: float = field(default_factory=time.monotonic)


class _LocalUserRateLimiter:
    """本地内存用户限流器。"""

    def __init__(self) -> None:
        # key -> _LocalWindow
        self._windows: dict[str, _LocalWindow] = {}

    async def check(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int, int]:
        """检查限流，返回 (allowed, remaining, reset_ts)。"""
        now = time.monotonic()
        win = self._windows.get(key)

        if win is None or now - win.start_ts >= window:
            win = _LocalWindow(count=0, start_ts=now)
            self._windows[key] = win

        remaining = max(0, limit - win.count - 1)
        allowed = win.count < limit

        if allowed:
            win.count += 1

        reset_ts = int(time.time() + window - (now - win.start_ts))
        return allowed, remaining if allowed else 0, reset_ts

    def cleanup(self, max_idle_seconds: int = 600) -> int:
        """清理长时间无活动的窗口。"""
        now = time.monotonic()
        stale = [k for k, w in self._windows.items() if now - w.start_ts > max_idle_seconds]
        for k in stale:
            del self._windows[k]
        return len(stale)


# ---------------------------------------------------------------------------
# Redis 滑动窗口实现
# ---------------------------------------------------------------------------


class _RedisUserRateLimiter:
    """基于 Redis Sorted Set 的用户限流器。"""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._prefix = "cityflow:user_ratelimit:"

    async def check(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int, int]:
        """检查限流，返回 (allowed, remaining, reset_ts)。"""
        full_key = self._prefix + key
        now = time.time()
        window_start = now - window

        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(full_key, 0, window_start)
        pipe.zadd(full_key, {f"{now:.6f}": now})
        pipe.zcard(full_key)
        pipe.expire(full_key, window + 1)
        results = await pipe.execute()

        current_count: int = results[2]
        allowed = current_count <= limit
        remaining = max(0, limit - current_count) if allowed else 0
        reset_ts = int(now + window)

        return allowed, remaining, reset_ts


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------


class UserRateLimiter:
    """用户级速率限制器。

    自动根据端点路径匹配配额等级，支持白名单用户豁免。
    优先使用 Redis 分布式模式，Redis 不可用时降级到本地内存。

    用法::

        limiter = UserRateLimiter(redis_client)
        result = await limiter.check("user_123", "/api/v1/plan_route")
    """

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        if redis_client is not None:
            self._backend: _RedisUserRateLimiter | _LocalUserRateLimiter = _RedisUserRateLimiter(
                redis_client
            )
            self._use_redis = True
            logger.info("用户限流器已初始化（Redis 模式）")
        else:
            self._backend = _LocalUserRateLimiter()
            self._use_redis = False
            logger.info("用户限流器已初始化（本地内存模式）")

    async def check(
        self,
        user_id: str,
        endpoint: str,
        multiplier: float = 1.0,
    ) -> UserRateLimitResult:
        """检查用户对指定端点的限流。

        Args:
            user_id: 用户 ID。
            endpoint: API 端点路径，如 ``"/api/v1/plan_route"``。
            multiplier: 配额倍率，>1 放宽限制，<1 收紧限制。

        Returns:
            UserRateLimitResult 包含限流判定和配额信息。
        """
        # 白名单用户直接放行
        if user_id in _WHITELIST_USERS:
            tier = resolve_endpoint_tier(endpoint)
            base_limit, window = ENDPOINT_LIMITS[tier]
            return UserRateLimitResult(
                allowed=True,
                user_id=user_id,
                endpoint=endpoint,
                tier=tier,
                limit=int(base_limit * multiplier),
                remaining=int(base_limit * multiplier),
                reset_ts=int(time.time()) + window,
            )

        tier = resolve_endpoint_tier(endpoint)
        base_limit, window = ENDPOINT_LIMITS[tier]
        effective_limit = max(1, int(base_limit * multiplier))

        key = f"{user_id}:{tier.value}"
        allowed, remaining, reset_ts = await self._backend.check(key, effective_limit, window)

        result = UserRateLimitResult(
            allowed=allowed,
            user_id=user_id,
            endpoint=endpoint,
            tier=tier,
            limit=effective_limit,
            remaining=remaining,
            reset_ts=reset_ts,
        )

        if not allowed:
            logger.warning(
                "用户 %s 在端点 %s 触发限流（%d/%d）",
                user_id,
                endpoint,
                effective_limit - remaining,
                effective_limit,
            )

        return result

    async def check_with_tier(
        self,
        user_id: str,
        endpoint: str,
        tier: EndpointTier,
        multiplier: float = 1.0,
    ) -> UserRateLimitResult:
        """使用指定配额等级检查限流（跳过自动解析）。

        适用于需要手动覆盖端点配额等级的场景。
        """
        if user_id in _WHITELIST_USERS:
            base_limit, window = ENDPOINT_LIMITS[tier]
            return UserRateLimitResult(
                allowed=True,
                user_id=user_id,
                endpoint=endpoint,
                tier=tier,
                limit=int(base_limit * multiplier),
                remaining=int(base_limit * multiplier),
                reset_ts=int(time.time()) + window,
            )

        base_limit, window = ENDPOINT_LIMITS[tier]
        effective_limit = max(1, int(base_limit * multiplier))

        key = f"{user_id}:{tier.value}"
        allowed, remaining, reset_ts = await self._backend.check(key, effective_limit, window)

        return UserRateLimitResult(
            allowed=allowed,
            user_id=user_id,
            endpoint=endpoint,
            tier=tier,
            limit=effective_limit,
            remaining=remaining,
            reset_ts=reset_ts,
        )

    @property
    def backend_type(self) -> str:
        """当前后端类型：``"redis"`` 或 ``"local"``。"""
        return "redis" if self._use_redis else "local"

    async def cleanup_local(self) -> int:
        """清理本地内存中的过期窗口。仅本地模式有效。"""
        if isinstance(self._backend, _LocalUserRateLimiter):
            return self._backend.cleanup()
        return 0


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_user_limiter: UserRateLimiter | None = None


def get_user_rate_limiter() -> UserRateLimiter:
    """获取全局用户限流器单例。"""
    global _user_limiter
    if _user_limiter is None:
        from backend.config import settings

        redis_client: aioredis.Redis | None = None
        redis_cfg = settings.redis
        if redis_cfg.host:
            url = f"redis://{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
            if redis_cfg.password:
                url = (
                    f"redis://:{quote_plus(redis_cfg.password)}"
                    f"@{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
                )
            redis_client = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        _user_limiter = UserRateLimiter(redis_client)
    return _user_limiter
