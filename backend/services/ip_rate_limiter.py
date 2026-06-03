"""CityFlow IP 级限流器。

在 middleware/rate_limit.py（全局入口 IP 限流）基础上，提供可编程的
IP 限流服务，支持：
- 按 IP + 端点维度限流
- 自动 / 手动 IP 封禁
- 可疑行为检测（短时间内大量不同端点访问）
- Redis 分布式 / 本地内存双模式

用法::

    limiter = get_ip_rate_limiter()
    result = await limiter.check("1.2.3.4", "/api/v1/plan_route")
    if not result.allowed:
        raise RateLimitExceededError(details=result.to_headers())
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

import redis.asyncio as aioredis

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

__all__ = [
    "IPRateLimitExceededError",
    "IPRateLimitResult",
    "IPRateLimiter",
    "get_ip_rate_limiter",
]


# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

# 每 IP 每端点的默认限流
_DEFAULT_ENDPOINT_LIMIT = 100
_DEFAULT_ENDPOINT_WINDOW = 60  # 秒

# 每 IP 全局限流（所有端点合计）
_DEFAULT_GLOBAL_LIMIT = 300
_DEFAULT_GLOBAL_WINDOW = 60

# IP 封禁时长（秒）
_BAN_DURATION = 600  # 10 分钟

# 可疑行为阈值：在窗口内访问不同端点数超过此值则标记可疑
_SUSPICIOUS_UNIQUE_ENDPOINTS = 20
_SUSPICIOUS_WINDOW = 60


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class IPRateLimitExceededError(CityFlowException):
    """IP 速率限制超出。"""

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
class IPRateLimitResult:
    """IP 限流检查结果。"""

    allowed: bool
    ip: str
    endpoint: str
    limit: int
    remaining: int
    reset_ts: int
    banned: bool = False
    suspicious: bool = False

    def to_headers(self) -> dict[str, str]:
        """转换为标准 RateLimit 响应头。"""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_ts),
        }
        if self.banned:
            headers["X-RateLimit-Banned"] = "true"
        return headers


# ---------------------------------------------------------------------------
# 本地内存实现
# ---------------------------------------------------------------------------


@dataclass
class _LocalWindow:
    """本地固定窗口计数器。"""

    count: int = 0
    start_ts: float = field(default_factory=time.monotonic)


class _LocalIPRateLimiter:
    """本地内存 IP 限流器。"""

    def __init__(self) -> None:
        # key -> _LocalWindow
        self._windows: dict[str, _LocalWindow] = {}
        # 被封禁的 IP -> 解封时间戳
        self._banned: dict[str, float] = {}
        # IP -> 最近访问过的端点集合（用于可疑行为检测）
        self._endpoint_tracker: dict[str, dict[str, float]] = defaultdict(dict)

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

    def is_banned(self, ip: str) -> bool:
        """检查 IP 是否被封禁。"""
        unban_ts = self._banned.get(ip)
        if unban_ts is None:
            return False
        if time.time() >= unban_ts:
            del self._banned[ip]
            return False
        return True

    def ban_ip(self, ip: str, duration: int = _BAN_DURATION) -> None:
        """封禁 IP。"""
        self._banned[ip] = time.time() + duration
        logger.warning("IP %s 已被封禁 %d 秒", ip, duration)

    def unban_ip(self, ip: str) -> None:
        """解封 IP。"""
        self._banned.pop(ip, None)

    def track_endpoint(self, ip: str, endpoint: str) -> bool:
        """记录端点访问，返回是否触发可疑行为。"""
        now = time.time()
        tracker = self._endpoint_tracker[ip]

        # 清理窗口外的记录
        stale = [ep for ep, ts in tracker.items() if now - ts > _SUSPICIOUS_WINDOW]
        for ep in stale:
            del tracker[ep]

        tracker[endpoint] = now
        return len(tracker) > _SUSPICIOUS_UNIQUE_ENDPOINTS

    def cleanup(self, max_idle_seconds: int = 600) -> int:
        """清理过期记录。"""
        now = time.monotonic()
        stale = [k for k, w in self._windows.items() if now - w.start_ts > max_idle_seconds]
        for k in stale:
            del self._windows[k]

        # 清理过期封禁
        now_wall = time.time()
        expired_bans = [ip for ip, ts in self._banned.items() if now_wall >= ts]
        for ip in expired_bans:
            del self._banned[ip]

        # 清理过期端点追踪
        stale_ips = []
        for ip, tracker in self._endpoint_tracker.items():
            stale_eps = [ep for ep, ts in tracker.items() if now_wall - ts > _SUSPICIOUS_WINDOW]
            for ep in stale_eps:
                del tracker[ep]
            if not tracker:
                stale_ips.append(ip)
        for ip in stale_ips:
            del self._endpoint_tracker[ip]

        return len(stale)


# ---------------------------------------------------------------------------
# Redis 滑动窗口实现
# ---------------------------------------------------------------------------


class _RedisIPRateLimiter:
    """基于 Redis 的 IP 限流器。"""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._prefix = "cityflow:ip_ratelimit:"
        self._ban_prefix = "cityflow:ip_ban:"
        self._track_prefix = "cityflow:ip_track:"

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

    async def is_banned(self, ip: str) -> bool:
        """检查 IP 是否被封禁。"""
        return await self._redis.exists(self._ban_prefix + ip) > 0

    async def ban_ip(self, ip: str, duration: int = _BAN_DURATION) -> None:
        """封禁 IP。"""
        await self._redis.setex(self._ban_prefix + ip, duration, "1")
        logger.warning("IP %s 已被封禁 %d 秒", ip, duration)

    async def unban_ip(self, ip: str) -> None:
        """解封 IP。"""
        await self._redis.delete(self._ban_prefix + ip)

    async def track_endpoint(self, ip: str, endpoint: str) -> bool:
        """记录端点访问，返回是否触发可疑行为。"""
        track_key = self._track_prefix + ip
        now = time.time()

        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(track_key, 0, now - _SUSPICIOUS_WINDOW)
        pipe.zadd(track_key, {endpoint: now})
        pipe.zcard(track_key)
        pipe.expire(track_key, _SUSPICIOUS_WINDOW + 1)
        results = await pipe.execute()

        unique_count: int = results[2]
        return unique_count > _SUSPICIOUS_UNIQUE_ENDPOINTS


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------


class IPRateLimiter:
    """IP 级速率限制器。

    提供三层保护：
    1. 单端点限流：每个 IP 对每个端点的请求频率限制
    2. 全局限流：每个 IP 所有端点的总请求频率限制
    3. 可疑行为检测：短时间内大量不同端点访问 -> 自动封禁

    用法::

        limiter = IPRateLimiter(redis_client)
        result = await limiter.check("1.2.3.4", "/api/v1/plan_route")
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        endpoint_limit: int = _DEFAULT_ENDPOINT_LIMIT,
        endpoint_window: int = _DEFAULT_ENDPOINT_WINDOW,
        global_limit: int = _DEFAULT_GLOBAL_LIMIT,
        global_window: int = _DEFAULT_GLOBAL_WINDOW,
        ban_duration: int = _BAN_DURATION,
    ) -> None:
        self._endpoint_limit = endpoint_limit
        self._endpoint_window = endpoint_window
        self._global_limit = global_limit
        self._global_window = global_window
        self._ban_duration = ban_duration

        if redis_client is not None:
            self._backend: _RedisIPRateLimiter | _LocalIPRateLimiter = _RedisIPRateLimiter(
                redis_client
            )
            self._use_redis = True
            logger.info("IP 限流器已初始化（Redis 模式）")
        else:
            self._backend = _LocalIPRateLimiter()
            self._use_redis = False
            logger.info("IP 限流器已初始化（本地内存模式）")

    async def check(
        self,
        ip: str,
        endpoint: str,
        endpoint_limit: int | None = None,
        global_limit: int | None = None,
    ) -> IPRateLimitResult:
        """检查 IP 对指定端点的限流。

        Args:
            ip: 客户端 IP 地址。
            endpoint: API 端点路径。
            endpoint_limit: 覆盖单端点限制（可选）。
            global_limit: 覆盖全局限制（可选）。

        Returns:
            IPRateLimitResult 包含限流判定和配额信息。
        """
        now = time.time()
        ep_limit = endpoint_limit or self._endpoint_limit
        gl_limit = global_limit or self._global_limit

        # 第 0 层：封禁检查
        banned = await self._check_banned(ip)
        if banned:
            return IPRateLimitResult(
                allowed=False,
                ip=ip,
                endpoint=endpoint,
                limit=0,
                remaining=0,
                reset_ts=int(now) + self._ban_duration,
                banned=True,
            )

        # 第 0.5 层：可疑行为检测
        suspicious = await self._track_and_detect(ip, endpoint)

        # 第 1 层：单端点限流
        ep_key = f"ep:{ip}:{endpoint}"
        ep_allowed, ep_remaining, ep_reset = await self._backend.check(
            ep_key, ep_limit, self._endpoint_window
        )

        if not ep_allowed:
            # 连续超限且可疑 -> 自动封禁
            if suspicious:
                await self._ban(ip)
            return IPRateLimitResult(
                allowed=False,
                ip=ip,
                endpoint=endpoint,
                limit=ep_limit,
                remaining=0,
                reset_ts=ep_reset,
                suspicious=suspicious,
            )

        # 第 2 层：全局限流
        gl_key = f"gl:{ip}"
        gl_allowed, _gl_remaining, gl_reset = await self._backend.check(
            gl_key, gl_limit, self._global_window
        )

        if not gl_allowed:
            if suspicious:
                await self._ban(ip)
            return IPRateLimitResult(
                allowed=False,
                ip=ip,
                endpoint=endpoint,
                limit=gl_limit,
                remaining=0,
                reset_ts=gl_reset,
                suspicious=suspicious,
            )

        return IPRateLimitResult(
            allowed=True,
            ip=ip,
            endpoint=endpoint,
            limit=ep_limit,
            remaining=ep_remaining,
            reset_ts=ep_reset,
            suspicious=suspicious,
        )

    async def manual_ban(self, ip: str, duration: int | None = None) -> None:
        """手动封禁 IP。"""
        await self._ban(ip, duration)

    async def manual_unban(self, ip: str) -> None:
        """手动解封 IP。"""
        if isinstance(self._backend, _RedisIPRateLimiter):
            await self._backend.unban_ip(ip)
        else:
            self._backend.unban_ip(ip)
        logger.info("IP %s 已被手动解封", ip)

    async def is_banned(self, ip: str) -> bool:
        """检查 IP 是否被封禁。"""
        return await self._check_banned(ip)

    @property
    def backend_type(self) -> str:
        """当前后端类型：``"redis"`` 或 ``"local"``。"""
        return "redis" if self._use_redis else "local"

    async def cleanup_local(self) -> int:
        """清理本地内存中的过期记录。仅本地模式有效。"""
        if isinstance(self._backend, _LocalIPRateLimiter):
            return self._backend.cleanup()
        return 0

    # -- 内部方法 --

    async def _check_banned(self, ip: str) -> bool:
        """检查封禁状态。"""
        if isinstance(self._backend, _RedisIPRateLimiter):
            return await self._backend.is_banned(ip)
        return self._backend.is_banned(ip)

    async def _ban(self, ip: str, duration: int | None = None) -> None:
        """执行封禁。"""
        dur = duration or self._ban_duration
        if isinstance(self._backend, _RedisIPRateLimiter):
            await self._backend.ban_ip(ip, dur)
        else:
            self._backend.ban_ip(ip, dur)

    async def _track_and_detect(self, ip: str, endpoint: str) -> bool:
        """追踪端点访问并检测可疑行为。"""
        if isinstance(self._backend, _RedisIPRateLimiter):
            return await self._backend.track_endpoint(ip, endpoint)
        return self._backend.track_endpoint(ip, endpoint)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_ip_limiter: IPRateLimiter | None = None


def get_ip_rate_limiter() -> IPRateLimiter:
    """获取全局 IP 限流器单例。"""
    global _ip_limiter
    if _ip_limiter is None:
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
        _ip_limiter = IPRateLimiter(redis_client)
    return _ip_limiter
