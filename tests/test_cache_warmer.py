"""cache_warmer 模块测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.cache_warmer import (CacheWarmer, CacheWarmerError,
                                           WarmupReport, WarmupResult,
                                           get_cache_warmer,
                                           reset_cache_warmer)

# ---------------------------------------------------------------------------
# WarmupResult / WarmupReport 数据类测试
# ---------------------------------------------------------------------------


class TestWarmupResult:
    """WarmupResult 数据类测试。"""

    def test_success_result(self) -> None:
        r = WarmupResult(task_name="t", success=True, duration_ms=12.3)
        assert r.task_name == "t"
        assert r.success is True
        assert r.duration_ms == 12.3
        assert r.error is None

    def test_failure_result(self) -> None:
        r = WarmupResult(task_name="t", success=False, duration_ms=5.0, error="boom")
        assert r.success is False
        assert r.error == "boom"


class TestWarmupReport:
    """WarmupReport 数据类测试。"""

    def test_counts(self) -> None:
        report = WarmupReport(
            results=[
                WarmupResult(task_name="a", success=True, duration_ms=10),
                WarmupResult(task_name="b", success=False, duration_ms=5, error="err"),
                WarmupResult(task_name="c", success=True, duration_ms=8),
            ],
            total_duration_ms=23.0,
        )
        assert report.success_count == 2
        assert report.failure_count == 1

    def test_empty_report(self) -> None:
        report = WarmupReport()
        assert report.success_count == 0
        assert report.failure_count == 0

    def test_to_dict(self) -> None:
        report = WarmupReport(
            results=[
                WarmupResult(task_name="x", success=True, duration_ms=100.0),
            ],
            total_duration_ms=100.0,
        )
        d = report.to_dict()
        assert d["total"] == 1
        assert d["success"] == 1
        assert d["failure"] == 0
        assert d["tasks"][0]["name"] == "x"


# ---------------------------------------------------------------------------
# CacheWarmer 核心逻辑测试
# ---------------------------------------------------------------------------


class TestCacheWarmer:
    """CacheWarmer 注册、执行、停止测试。"""

    @pytest.fixture
    def warmer(self) -> CacheWarmer:
        return CacheWarmer()

    # --- 注册 ---

    def test_register_and_list(self, warmer: CacheWarmer) -> None:
        warmer.register("a", AsyncMock())
        warmer.register("b", AsyncMock())
        assert set(warmer.task_names) == {"a", "b"}

    def test_register_empty_name_raises(self, warmer: CacheWarmer) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            warmer.register("", AsyncMock())

    def test_register_duplicate_raises(self, warmer: CacheWarmer) -> None:
        warmer.register("dup", AsyncMock())
        with pytest.raises(ValueError, match="already registered"):
            warmer.register("dup", AsyncMock())

    def test_unregister(self, warmer: CacheWarmer) -> None:
        warmer.register("x", AsyncMock())
        warmer.unregister("x")
        assert "x" not in warmer.task_names

    def test_unregister_nonexistent_noop(self, warmer: CacheWarmer) -> None:
        warmer.unregister("ghost")  # 不应抛异常

    # --- warmup_all ---

    @pytest.mark.asyncio
    async def test_warmup_all_executes_tasks(self, warmer: CacheWarmer) -> None:
        called: list[str] = []

        async def task_a() -> None:
            called.append("a")

        async def task_b() -> None:
            called.append("b")

        warmer.register("a", task_a)
        warmer.register("b", task_b)

        report = await warmer.warmup_all()

        assert called == ["a", "b"]
        assert report.success_count == 2
        assert report.failure_count == 0

    @pytest.mark.asyncio
    async def test_warmup_all_continues_on_failure(self, warmer: CacheWarmer) -> None:
        called: list[str] = []

        async def fail_task() -> None:
            raise RuntimeError("boom")

        async def ok_task() -> None:
            called.append("ok")

        warmer.register("fail", fail_task)
        warmer.register("ok", ok_task)

        report = await warmer.warmup_all()

        assert called == ["ok"]
        assert report.success_count == 1
        assert report.failure_count == 1
        assert report.results[0].error == "boom"

    @pytest.mark.asyncio
    async def test_warmup_all_empty(self, warmer: CacheWarmer) -> None:
        report = await warmer.warmup_all()
        assert report.success_count == 0
        assert len(report.results) == 0

    @pytest.mark.asyncio
    async def test_warmup_all_stores_last_report(self, warmer: CacheWarmer) -> None:
        warmer.register("t", AsyncMock())
        assert warmer.last_report is None
        await warmer.warmup_all()
        assert warmer.last_report is not None
        assert warmer.last_report.success_count == 1

    # --- warmup (单个) ---

    @pytest.mark.asyncio
    async def test_warmup_single(self, warmer: CacheWarmer) -> None:
        mock = AsyncMock()
        warmer.register("solo", mock)
        result = await warmer.warmup("solo")
        assert result.success is True
        mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_warmup_unregistered_raises(self, warmer: CacheWarmer) -> None:
        with pytest.raises(CacheWarmerError, match="未注册"):
            await warmer.warmup("nonexistent")

    @pytest.mark.asyncio
    async def test_warmup_single_failure(self, warmer: CacheWarmer) -> None:
        async def bad() -> None:
            raise ValueError("bad data")

        warmer.register("bad", bad)
        result = await warmer.warmup("bad")
        assert result.success is False
        assert "bad data" in result.error  # type: ignore[union-attr]

    # --- stop ---

    def test_stop_when_not_running(self, warmer: CacheWarmer) -> None:
        warmer.stop()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_stop_halts_background(self, warmer: CacheWarmer) -> None:
        call_count = 0

        async def counting_task() -> None:
            nonlocal call_count
            call_count += 1

        warmer.register("counter", counting_task)

        async def run_with_stop() -> None:
            # 让后台循环跑一次后停止
            async def delayed_stop() -> None:
                await asyncio.sleep(0.05)
                warmer.stop()

            stopper = asyncio.create_task(delayed_stop())
            await warmer.start_background_warmup(interval=1)
            await stopper

        await run_with_stop()
        # 至少执行过一次
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_start_background_warmup_no_duplicate(
        self, warmer: CacheWarmer
    ) -> None:
        """重复调用 start_background_warmup 不会创建多个循环。"""
        warmer._running = True  # 模拟已在运行
        # 不应进入循环，直接返回
        await warmer.start_background_warmup(interval=1)
        warmer._running = False  # 清理


# ---------------------------------------------------------------------------
# 全局单例测试
# ---------------------------------------------------------------------------


class TestGlobalWarmer:
    """get_cache_warmer 单例测试。"""

    def setup_method(self) -> None:
        reset_cache_warmer()

    def teardown_method(self) -> None:
        reset_cache_warmer()

    def test_singleton(self) -> None:
        w1 = get_cache_warmer()
        w2 = get_cache_warmer()
        assert w1 is w2

    def test_default_tasks_registered(self) -> None:
        warmer = get_cache_warmer()
        names = warmer.task_names
        assert "poi" in names
        assert "city_category_index" in names
        assert "user_profiles" in names
        assert "other_datasets" in names

    def test_reset(self) -> None:
        w1 = get_cache_warmer()
        reset_cache_warmer()
        w2 = get_cache_warmer()
        assert w1 is not w2


# ---------------------------------------------------------------------------
# 默认预热任务集成测试（mock 数据层）
# ---------------------------------------------------------------------------


class TestDefaultWarmupTasks:
    """默认预热任务测试，mock 数据层避免依赖文件系统。"""

    @pytest.mark.asyncio
    async def test_warmup_poi_cache(self) -> None:
        from backend.services.cache_warmer import warmup_poi_cache

        mock_pois = [
            {"id": "1", "name": "A", "city": "BJ", "category": "景点"},
            {"id": "2", "name": "B", "city": "SH", "category": "餐厅"},
            {"id": "3", "name": "C", "city": "BJ", "category": "餐厅"},
        ]
        mock_cache = AsyncMock()

        with (
            patch(
                "backend.services.cache.get_multilevel_cache", return_value=mock_cache
            ),
            patch("backend.services.data_service.get_data", return_value=mock_pois),
        ):
            await warmup_poi_cache()

        # 全量 + 2 城市 + cities 列表 + categories 列表 = 5 次 set
        assert mock_cache.set.await_count == 5

    @pytest.mark.asyncio
    async def test_warmup_poi_cache_empty(self) -> None:
        from backend.services.cache_warmer import warmup_poi_cache

        mock_cache = AsyncMock()
        with (
            patch(
                "backend.services.cache.get_multilevel_cache", return_value=mock_cache
            ),
            patch("backend.services.data_service.get_data", return_value=[]),
        ):
            await warmup_poi_cache()

        mock_cache.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_warmup_city_category_cache(self) -> None:
        from backend.services.cache_warmer import warmup_city_category_cache

        mock_pois = [
            {"city": "BJ", "category": "景点"},
            {"city": "BJ", "category": "餐厅"},
            {"city": "SH", "category": "景点"},
        ]
        mock_cache = AsyncMock()

        with (
            patch(
                "backend.services.cache.get_multilevel_cache", return_value=mock_cache
            ),
            patch("backend.services.data_service.get_data", return_value=mock_pois),
        ):
            await warmup_city_category_cache()

        # 3 个组合: BJ:景点, BJ:餐厅, SH:景点
        assert mock_cache.set.await_count == 3

    @pytest.mark.asyncio
    async def test_warmup_user_profiles(self) -> None:
        from backend.services.cache_warmer import warmup_user_profiles

        mock_profiles = {
            "P1": {
                "group_type": "独居",
                "preferences": {
                    "culture": 0.6,
                    "food": 0.4,
                    "nature": 0.7,
                    "social": 0.1,
                },
                "pace": "闲逛型",
                "budget_level": "中",
            },
        }
        mock_cache = AsyncMock()

        with (
            patch(
                "backend.services.cache.get_multilevel_cache", return_value=mock_cache
            ),
            patch("backend.services.user_profiles.USER_PROFILES", mock_profiles),
            patch("backend.services.user_profiles.match_profile", return_value="P1"),
        ):
            await warmup_user_profiles()

        # 1 个 profile_match + 1 个 user_profiles dict = 2
        assert mock_cache.set.await_count == 2

    @pytest.mark.asyncio
    async def test_warmup_other_datasets(self) -> None:
        from backend.services.cache_warmer import warmup_other_datasets

        mock_cache = AsyncMock()
        with (
            patch(
                "backend.services.cache.get_multilevel_cache", return_value=mock_cache
            ),
            patch(
                "backend.services.data_service.get_datasets",
                return_value=["city_poi_db", "orders"],
            ),
            patch("backend.services.data_service.get_data", return_value=[{"a": 1}]),
        ):
            await warmup_other_datasets()

        # city_poi_db 被跳过，只预热 orders
        assert mock_cache.set.await_count == 1
