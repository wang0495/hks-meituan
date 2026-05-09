"""CityFlow 用户配额管理服务。

提供基于 Redis 的用户配额管理，支持：
- 按用户 / 操作类型 / 时间周期的配额限制
- 配额查询与使用量递增（原子操作）
- 多周期（小时级 / 日级）同时生效
- 超额抛出统一异常

用法::

    quota = get_quota_manager()
    info = await quota.check_and_consume("user:123", "route_planning")
    if not info.within_quota:
        raise QuotaExceededError(...)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import redis.asyncio as aioredis

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

__all__ = [
    "QuotaManager",
    "QuotaInfo",
    "QuotaExceededError",
    "QuotaPeriod",
    "QUOTA_LIMITS",
    "get_quota_manager",
]


# ---------------------------------------------------------------------------
# 常量：各操作的配额上限
# ---------------------------------------------------------------------------

QUOTA_LIMITS: dict[str, dict[str, int]] = {
    "route_planning": {"daily": 100, "hourly": 10},
    "poi_search": {"daily": 1000, "hourly": 100},
    "dialogue": {"daily": 500, "hourly": 50},
    "narrative_generation": {"daily": 200, "hourly": 20},
}


# ---------------------------------------------------------------------------
# 配额周期枚举
# ---------------------------------------------------------------------------


class QuotaPeriod(str, Enum):
    """配额统计周期。"""

    HOURLY = "hourly"
    DAILY = "daily"


# 各周期对应的 Redis key TTL（秒）
_PERIOD_TTL: dict[QuotaPeriod, int] = {
    QuotaPeriod.HOURLY: 3600,
    QuotaPeriod.DAILY: 86400,
}


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class QuotaExceededError(CityFlowException):
    """用户配额超出限制。"""

    def __init__(
        self,
        message: str = "已达到使用上限，请稍后再试",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            message=message,
            details=details,
        )


# ---------------------------------------------------------------------------
# 配额查询结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuotaInfo:
    """单个周期的配额信息。"""

    period: QuotaPeriod
    limit: int
    used: int
    remaining: int

    @property
    def within_quota(self) -> bool:
        """是否在配额范围内。"""
        return self.remaining > 0


@dataclass(frozen=True, slots=True)
class QuotaCheckResult:
    """配额检查综合结果，包含所有周期信息。"""

    user_id: str
    quota_type: str
    periods: dict[QuotaPeriod, QuotaInfo]

    @property
    def within_quota(self) -> bool:
        """所有周期是否都在配额范围内。"""
        return all(info.within_quota for info in self.periods.values())

    @property
    def exceeded_periods(self) -> list[QuotaPeriod]:
        """已超限的周期列表。"""
        return [p for p, info in self.periods.items() if not info.within_quota]

    def to_dict(self) -> dict[str, Any]:
        """转换为 API 响应字典。"""
        return {
            "user_id": self.user_id,
            "quota_type": self.quota_type,
            "within_quota": self.within_quota,
            "periods": {
                p.value: {
                    "limit": info.limit,
                    "used": info.used,
                    "remaining": info.remaining,
                }
                for p, info in self.periods.items()
            },
        }


# ---------------------------------------------------------------------------
# 配额管理器
# ---------------------------------------------------------------------------


class QuotaManager:
    """用户配额管理器。

    使用 Redis INCR + EXPIRE 实现原子性的配额计数。
    支持同时检查多个周期（如 hourly + daily），全部通过才算在配额内。

    Args:
        redis_client: Redis 异步客户端，为 None 时所有检查默认放行。
        quota_limits: 配额上限配置，默认使用模块级 ``QUOTA_LIMITS``。
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        quota_limits: dict[str, dict[str, int]] | None = None,
    ) -> None:
        self._redis = redis_client
        self._limits = quota_limits or QUOTA_LIMITS
        self._prefix = "cityflow:quota:"

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    async def get_usage(
        self,
        user_id: str,
        quota_type: str,
    ) -> QuotaCheckResult:
        """查询用户当前配额使用情况（不消耗配额）。

        Args:
            user_id: 用户标识。
            quota_type: 操作类型，须在 ``QUOTA_LIMITS`` 中注册。

        Returns:
            QuotaCheckResult 包含各周期的使用详情。
        """
        type_limits = self._limits.get(quota_type, {})
        periods: dict[QuotaPeriod, QuotaInfo] = {}

        for period_str, limit in type_limits.items():
            period = QuotaPeriod(period_str)
            used = await self._get_count(user_id, quota_type, period)
            remaining = max(0, limit - used)
            periods[period] = QuotaInfo(
                period=period,
                limit=limit,
                used=used,
                remaining=remaining,
            )

        return QuotaCheckResult(
            user_id=user_id,
            quota_type=quota_type,
            periods=periods,
        )

    # ------------------------------------------------------------------
    # 消耗
    # ------------------------------------------------------------------

    async def check_and_consume(
        self,
        user_id: str,
        quota_type: str,
        amount: int = 1,
    ) -> QuotaCheckResult:
        """检查配额并消耗一次。原子操作。

        如果任一周期已超限，不会递增计数，直接返回当前状态。

        Args:
            user_id: 用户标识。
            quota_type: 操作类型。
            amount: 消耗量，默认 1。

        Returns:
            QuotaCheckResult，``within_quota`` 为 False 表示已超限。
        """
        type_limits = self._limits.get(quota_type, {})
        periods: dict[QuotaPeriod, QuotaInfo] = {}

        # 先检查所有周期是否还有余量
        for period_str, limit in type_limits.items():
            period = QuotaPeriod(period_str)
            used = await self._get_count(user_id, quota_type, period)
            remaining = max(0, limit - used)
            periods[period] = QuotaInfo(
                period=period,
                limit=limit,
                used=used,
                remaining=remaining,
            )

        result = QuotaCheckResult(
            user_id=user_id,
            quota_type=quota_type,
            periods=periods,
        )

        # 任一周期超限则不消耗
        if not result.within_quota:
            logger.warning(
                "用户 %s 的 %s 配额已超限: %s",
                user_id,
                quota_type,
                result.exceeded_periods,
            )
            return result

        # 所有周期都有余量，逐个递增
        for period_str, limit in type_limits.items():
            period = QuotaPeriod(period_str)
            await self._increment(user_id, quota_type, period, amount)

        # 重新获取递增后的数据
        return await self.get_usage(user_id, quota_type)

    # ------------------------------------------------------------------
    # 重置
    # ------------------------------------------------------------------

    async def reset(
        self,
        user_id: str,
        quota_type: str,
        period: QuotaPeriod | None = None,
    ) -> int:
        """重置用户配额计数。

        Args:
            user_id: 用户标识。
            quota_type: 操作类型。
            period: 指定周期，为 None 时重置所有周期。

        Returns:
            删除的 key 数量。
        """
        periods = [period] if period else list(QuotaPeriod)
        deleted = 0
        for p in periods:
            key = self._make_key(user_id, quota_type, p)
            if self._redis is not None:
                result = await self._redis.delete(key)
                deleted += result
        return deleted

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _make_key(self, user_id: str, quota_type: str, period: QuotaPeriod) -> str:
        """生成 Redis key。包含当前周期的唯一标识。"""
        if period == QuotaPeriod.HOURLY:
            bucket = int(time.time()) // 3600
        else:  # daily
            bucket = int(time.time()) // 86400
        return f"{self._prefix}{user_id}:{quota_type}:{period.value}:{bucket}"

    async def _get_count(
        self,
        user_id: str,
        quota_type: str,
        period: QuotaPeriod,
    ) -> int:
        """获取当前周期的使用计数。"""
        if self._redis is None:
            return 0
        key = self._make_key(user_id, quota_type, period)
        try:
            val = await self._redis.get(key)
            return int(val) if val else 0
        except Exception:
            logger.debug("配额计数读取失败: %s", key, exc_info=True)
            return 0

    async def _increment(
        self,
        user_id: str,
        quota_type: str,
        period: QuotaPeriod,
        amount: int = 1,
    ) -> int:
        """原子递增并设置过期时间。返回递增后的值。"""
        if self._redis is None:
            return 0
        key = self._make_key(user_id, quota_type, period)
        ttl = _PERIOD_TTL[period]
        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.incrby(key, amount)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return int(results[0])
        except Exception:
            logger.debug("配额计数递增失败: %s", key, exc_info=True)
            return 0


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_quota_manager: QuotaManager | None = None


def get_quota_manager() -> QuotaManager:
    """获取全局配额管理器单例。

    首次调用时根据配置自动创建。Redis 不可用时配额检查默认放行。
    """
    global _quota_manager
    if _quota_manager is None:
        from backend.config import settings

        redis_client: aioredis.Redis | None = None
        redis_cfg = settings.redis
        if redis_cfg.host:
            url = f"redis://{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
            if redis_cfg.password:
                url = f"redis://:{redis_cfg.password}@{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
            redis_client = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        _quota_manager = QuotaManager(redis_client)
    return _quota_manager
