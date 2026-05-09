"""配额管理器单元测试。"""

from __future__ import annotations

import pytest

from backend.services.quota import (QUOTA_LIMITS, QuotaCheckResult,
                                    QuotaExceededError, QuotaInfo,
                                    QuotaManager, QuotaPeriod)


class TestQuotaPeriod:
    def test_hourly_value(self) -> None:
        assert QuotaPeriod.HOURLY.value == "hourly"

    def test_daily_value(self) -> None:
        assert QuotaPeriod.DAILY.value == "daily"


class TestQuotaInfo:
    def test_within_quota_when_remaining_positive(self) -> None:
        info = QuotaInfo(period=QuotaPeriod.DAILY, limit=100, used=50, remaining=50)
        assert info.within_quota is True

    def test_not_within_quota_when_remaining_zero(self) -> None:
        info = QuotaInfo(period=QuotaPeriod.DAILY, limit=100, used=100, remaining=0)
        assert info.within_quota is False


class TestQuotaCheckResult:
    def test_within_quota_all_periods_ok(self) -> None:
        result = QuotaCheckResult(
            user_id="u1",
            quota_type="route_planning",
            periods={
                QuotaPeriod.HOURLY: QuotaInfo(
                    period=QuotaPeriod.HOURLY, limit=10, used=5, remaining=5
                ),
                QuotaPeriod.DAILY: QuotaInfo(
                    period=QuotaPeriod.DAILY, limit=100, used=50, remaining=50
                ),
            },
        )
        assert result.within_quota is True
        assert result.exceeded_periods == []

    def test_not_within_quota_when_one_period_exceeded(self) -> None:
        result = QuotaCheckResult(
            user_id="u1",
            quota_type="route_planning",
            periods={
                QuotaPeriod.HOURLY: QuotaInfo(
                    period=QuotaPeriod.HOURLY, limit=10, used=10, remaining=0
                ),
                QuotaPeriod.DAILY: QuotaInfo(
                    period=QuotaPeriod.DAILY, limit=100, used=50, remaining=50
                ),
            },
        )
        assert result.within_quota is False
        assert QuotaPeriod.HOURLY in result.exceeded_periods

    def test_to_dict(self) -> None:
        result = QuotaCheckResult(
            user_id="u1",
            quota_type="poi_search",
            periods={
                QuotaPeriod.DAILY: QuotaInfo(
                    period=QuotaPeriod.DAILY, limit=1000, used=10, remaining=990
                ),
            },
        )
        d = result.to_dict()
        assert d["user_id"] == "u1"
        assert d["quota_type"] == "poi_search"
        assert d["within_quota"] is True
        assert d["periods"]["daily"]["limit"] == 1000
        assert d["periods"]["daily"]["remaining"] == 990


class TestQuotaManagerWithoutRedis:
    """测试无 Redis 时的配额管理器（默认放行）。"""

    @pytest.mark.asyncio
    async def test_get_usage_returns_zero_when_no_redis(self) -> None:
        mgr = QuotaManager(redis_client=None)
        result = await mgr.get_usage("user:1", "route_planning")
        assert result.within_quota is True
        for info in result.periods.values():
            assert info.used == 0

    @pytest.mark.asyncio
    async def test_check_and_consume_always_passes_without_redis(self) -> None:
        mgr = QuotaManager(redis_client=None)
        result = await mgr.check_and_consume("user:1", "route_planning")
        assert result.within_quota is True

    @pytest.mark.asyncio
    async def test_reset_noop_without_redis(self) -> None:
        mgr = QuotaManager(redis_client=None)
        deleted = await mgr.reset("user:1", "route_planning")
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_unknown_quota_type_returns_empty_periods(self) -> None:
        mgr = QuotaManager(redis_client=None)
        result = await mgr.get_usage("user:1", "unknown_type")
        assert result.periods == {}


class TestQuotaExceededError:
    def test_default_message(self) -> None:
        err = QuotaExceededError()
        assert "上限" in err.message
        assert err.status_code == 429

    def test_custom_details(self) -> None:
        err = QuotaExceededError(
            details={"quota_type": "route_planning", "period": "daily"}
        )
        assert err.details["quota_type"] == "route_planning"
        assert err.to_dict()["error"]["code"] == 1005


class TestQuotaLimits:
    def test_route_planning_limits(self) -> None:
        assert QUOTA_LIMITS["route_planning"]["daily"] == 100
        assert QUOTA_LIMITS["route_planning"]["hourly"] == 10

    def test_poi_search_limits(self) -> None:
        assert QUOTA_LIMITS["poi_search"]["daily"] == 1000
        assert QUOTA_LIMITS["poi_search"]["hourly"] == 100

    def test_dialogue_limits(self) -> None:
        assert QUOTA_LIMITS["dialogue"]["daily"] == 500
        assert QUOTA_LIMITS["dialogue"]["hourly"] == 50

    def test_all_types_have_both_periods(self) -> None:
        for quota_type, periods in QUOTA_LIMITS.items():
            assert "daily" in periods, f"{quota_type} missing daily limit"
            assert "hourly" in periods, f"{quota_type} missing hourly limit"
