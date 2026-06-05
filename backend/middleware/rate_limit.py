"""速率限制中间件。

基于客户端 IP 的滑动窗口速率限制。
优先使用 Redis 存储（支持多实例共享），Redis 不可用时自动回退到内存存储。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)

# Redis 连接延迟初始化，避免 import 时强制依赖
_redis: object | None = None
_redis_init_attempted = False


async def _get_redis():
    """延迟初始化 Redis 连接，用于速率限制。"""
    global _redis, _redis_init_attempted
    if _redis is not None:
        return _redis
    if _redis_init_attempted:
        return None
    _redis_init_attempted = True
    try:
        import redis.asyncio as aioredis

        from backend.config import settings

        redis_cfg = settings.redis
        if redis_cfg.password:
            from urllib.parse import quote_plus

            url = f"redis://:{quote_plus(redis_cfg.password)}@{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
        else:
            url = f"redis://{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
        _redis = aioredis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        # 快速验证连接
        await _redis.ping()  # type: ignore[union-attr]
        logger.info("速率限制：Redis 连接成功")
        return _redis
    except Exception as exc:
        logger.warning("速率限制：Redis 不可用，回退到内存存储 (%s)", exc)
        _redis = None
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口速率限制。

    优先使用 Redis sorted-set 实现分布式滑动窗口，
    Redis 不可用时自动降级为进程内内存存储。

    Args:
        app: ASGI 应用。
        requests_per_minute: 每个 IP 每分钟允许的最大请求数。
        cleanup_interval: 内存模式下清理过期记录的间隔（秒）。
        trusted_proxies: 可信反向代理 IP 列表。
    """

    # 核心规划路径享有独立的、更高的限速阈值，防止攻击者通过
    # 刷低价值端点（如 /api/health）耗尽配额来阻塞 /api/plan。
    _PLAN_PREFIXES = ("/api/plan", "/api/route", "/api/dialogue")
    _WINDOW_SECONDS = 60

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        cleanup_interval: int = 300,
        trusted_proxies: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._plan_limit = requests_per_minute * 3
        self.cleanup_interval = cleanup_interval
        self._trusted_proxies: frozenset[str] = frozenset(trusted_proxies or [])
        # 内存回退存储 {ip: [timestamp, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._plan_requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()

    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        now = time.time()

        # 根据路径选择独立的限速阈值
        path = request.url.path
        is_plan = path.startswith(self._PLAN_PREFIXES)
        limit = self._plan_limit if is_plan else self.requests_per_minute
        prefix = "rl:plan:" if is_plan else "rl:gen:"

        # 尝试使用 Redis
        redis_conn = await _get_redis()
        if redis_conn is not None:
            count, oldest = await self._redis_check(redis_conn, prefix, client_ip, now, limit)
        else:
            count, oldest = self._memory_check(prefix, client_ip, now, limit)

        # 检查是否超限
        if count >= limit:
            retry_after = int(oldest + self._WINDOW_SECONDS - now) + 1 if oldest else self._WINDOW_SECONDS
            logger.warning(
                "IP %s 触发速率限制 (%d 请求/分钟, path=%s)", client_ip, count, path
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now) + retry_after),
                },
            )

        # 处理请求
        response = await call_next(request)

        # 注入速率限制响应头
        remaining = limit - count - 1
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(int(now) + self._WINDOW_SECONDS)

        return response

    # ------------------------------------------------------------------
    # Redis 滑动窗口（sorted-set 实现）
    # ------------------------------------------------------------------

    async def _redis_check(
        self, redis_conn, prefix: str, client_ip: str, now: float, limit: int
    ) -> tuple[int, float]:
        """使用 Redis sorted-set 实现分布式滑动窗口。

        Returns:
            (当前窗口请求数, 窗口中最早请求的时间戳)
        """
        key = f"{prefix}{client_ip}"
        cutoff = now - self._WINDOW_SECONDS
        pipe = redis_conn.pipeline(transaction=True)
        # 1) 移除过期条目
        pipe.zremrangebyscore(key, "-inf", cutoff)
        # 2) 添加当前请求
        pipe.zadd(key, {str(now): now})
        # 3) 统计窗口内请求数
        pipe.zcard(key)
        # 4) 设置 key 过期时间（自动清理）
        pipe.expire(key, self._WINDOW_SECONDS + 10)
        # 5) 取窗口中最早的请求（用于计算 retry-after）
        pipe.zrange(key, 0, 0, withscores=True)
        results = await pipe.execute()
        count = results[2]  # zcard result
        oldest_entry = results[4]  # zrange result
        oldest = oldest_entry[0][1] if oldest_entry else now
        return count, oldest

    # ------------------------------------------------------------------
    # 内存回退（原有逻辑）
    # ------------------------------------------------------------------

    def _memory_check(
        self, prefix: str, client_ip: str, now: float, limit: int
    ) -> tuple[int, float]:
        """进程内内存滑动窗口回退。"""
        self._maybe_cleanup(now)

        counter = self._plan_requests if prefix.startswith("rl:plan") else self._requests
        window = counter[client_ip]
        cutoff = now - self._WINDOW_SECONDS
        counter[client_ip] = [t for t in window if t > cutoff]
        window = counter[client_ip]

        oldest = window[0] if window else now
        return len(window), oldest

    # ------------------------------------------------------------------

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP，仅在可信代理链中读取转发头。"""
        direct_ip = request.client.host if request.client else "unknown"

        # 仅当直连 IP 是可信代理时，才读取 X-Forwarded-For
        if self._trusted_proxies and direct_ip in self._trusted_proxies:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # 取最右边的非可信条目（最接近客户端的真实 IP）
                parts = [p.strip() for p in forwarded.split(",")]
                for ip in reversed(parts):
                    if ip not in self._trusted_proxies:
                        return ip
                return parts[-1]  # 全部都是代理，取最后一个
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()

        return direct_ip

    def _maybe_cleanup(self, now: float) -> None:
        """定期清理超过 2 分钟无请求的 IP 条目（内存回退模式）。"""
        mono_now = time.monotonic()
        if mono_now - self._last_cleanup < self.cleanup_interval:
            return
        self._last_cleanup = mono_now

        stale_threshold = now - 120
        total_cleaned = 0
        for counter in (self._requests, self._plan_requests):
            stale_ips = [
                ip
                for ip, timestamps in counter.items()
                if not timestamps or timestamps[-1] < stale_threshold
            ]
            for ip in stale_ips:
                del counter[ip]
            total_cleaned += len(stale_ips)
        if total_cleaned:
            logger.debug("速率限制：清理了 %d 个过期 IP 条目", total_cleaned)
