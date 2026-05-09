"""backend/cache/warmup.py 和 backend/startup/warmup.py 测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.cache.warmup import (CacheWarmup, WarmupReport, WarmupResult,
                                  get_cache_warmup, reset_cache_warmup,
                                  warmup_city_category_cache,
                                  warmup_other_datasets, warmup_poi_cache,
                                  warmup_user_profiles)

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
# CacheWarmup 核心逻辑测试
# ---------------------------------------------------------------------------


class TestCacheWarmup:
    """CacheWarmup 注册、执行、停止测试。"""

    @pytest.fixture
    def mock_cache(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def warmup(self, mock_cache: AsyncMock) -> CacheWarmup:
        return CacheWarmup(mock_cache)

    # --- 注册 ---

    def test_register_and_list(self, warmup: CacheWarmup) -> None:
        async def task_a(cache):
            pass

        async def task_b(cache):
            pass

        warmup.register("a", task_a)
        warmup.register("b", task_b)
        assert set(warmup.task_names) == {"a", "b"}

    def test_register_empty_name_raises(self, warmup: CacheWarmup) -> None:
        async def dummy(cache):
            pass

        with pytest.raises(ValueError, match="must not be empty"):
            warmup.register("", dummy)

    def test_register_duplicate_raises(self, warmup: CacheWarmup) -> None:
        async def dummy(cache):
            pass

        warmup.register("dup", dummy)
        with pytest.raises(ValueError, match="already registered"):
            warmup.register("dup", dummy)

    def test_unregister(self, warmup: CacheWarmup) -> None:
        async def dummy(cache):
            pass

        warmup.register("x", dummy)
        warmup.unregister("x")
        assert "x" not in warmup.task_names

    def test_unregister_nonexistent_noop(self, warmup: CacheWarmup) -> None:
        warmup.unregister("ghost")  # 不应抛异常

    # --- warmup_all ---

    @pytest.mark.asyncio
    async def test_warmup_all_executes_tasks(
        self, warmup: CacheWarmup, mock_cache: AsyncMock
    ) -> None:
        called: list[str] = []

        async def task_a(cache) -> None:
            called.append("a")

        async def task_b(cache) -> None:
            called.append("b")

        warmup.register("a", task_a)
        warmup.register("b", task_b)

        report = await warmup.warmup_all()

        assert called == ["a", "b"]
        assert report.success_count == 2
        assert report.failure_count == 0

    @pytest.mark.asyncio
    async def test_warmup_all_continues_on_failure(
        self, warmup: CacheWarmup, mock_cache: AsyncMock
    ) -> None:
        called: list[str] = []

        async def fail_task(cache) -> None:
            raise RuntimeError("boom")

        async def ok_task(cache) -> None:
            called.append("ok")

        warmup.register("fail", fail_task)
        warmup.register("ok", ok_task)

        report = await warmup.warmup_all()

        assert called == ["ok"]
        assert report.success_count == 1
        assert report.failure_count == 1
        assert report.results[0].error == "boom"

    @pytest.mark.asyncio
    async def test_warmup_all_empty(self, warmup: CacheWarmup) -> None:
        report = await warmup.warmup_all()
        assert report.success_count == 0
        assert len(report.results) == 0

    @pytest.mark.asyncio
    async def test_warmup_all_stores_last_report(
        self, warmup: CacheWarmup, mock_cache: AsyncMock
    ) -> None:
        async def dummy(cache) -> None:
            pass

        warmup.register("t", dummy)
        assert warmup.last_report is None
        await warmup.warmup_all()
        assert warmup.last_report is not None
        assert warmup.last_report.success_count == 1

    # --- warmup_task (单个) ---

    @pytest.mark.asyncio
    async def test_warmup_task_single(
        self, warmup: CacheWarmup, mock_cache: AsyncMock
    ) -> None:
        called = False

        async def solo(cache) -> None:
            nonlocal called
            called = True

        warmup.register("solo", solo)
        result = await warmup.warmup_task("solo")
        assert result.success is True
        assert called is True

    @pytest.mark.asyncio
    async def test_warmup_task_unregistered_raises(self, warmup: CacheWarmup) -> None:
        with pytest.raises(KeyError, match="未注册"):
            await warmup.warmup_task("nonexistent")

    @pytest.mark.asyncio
    async def test_warmup_task_failure(
        self, warmup: CacheWarmup, mock_cache: AsyncMock
    ) -> None:
        async def bad(cache) -> None:
            raise ValueError("bad data")

        warmup.register("bad", bad)
        result = await warmup.warmup_task("bad")
        assert result.success is False
        assert "bad data" in result.error  # type: ignore[union-attr]

    # --- cache 传递 ---

    @pytest.mark.asyncio
    async def test_cache_passed_to_task(
        self, warmup: CacheWarmup, mock_cache: AsyncMock
    ) -> None:
        received_cache = None

        async def capture(cache) -> None:
            nonlocal received_cache
            received_cache = cache

        warmup.register("capture", capture)
        await warmup.warmup_all()
        assert received_cache is mock_cache

    # --- stop ---

    def test_stop_when_not_running(self, warmup: CacheWarmup) -> None:
        warmup.stop()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_stop_halts_background(
        self, warmup: CacheWarmup, mock_cache: AsyncMock
    ) -> None:
        call_count = 0

        async def counting_task(cache) -> None:
            nonlocal call_count
            call_count += 1

        warmup.register("counter", counting_task)

        async def run_with_stop() -> None:
            async def delayed_stop() -> None:
                await asyncio.sleep(0.05)
                warmup.stop()

            stopper = asyncio.create_task(delayed_stop())
            await warmup.start_background_warmup(interval=1)
            await stopper

        await run_with_stop()
        # 至少执行过一次
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_start_background_warmup_no_duplicate(
        self, warmup: CacheWarmup
    ) -> None:
        """重复调用 start_background_warmup 不会创建多个循环。"""
        warmup._running = True  # 模拟已在运行
        # 不应进入循环，直接返回
        await warmup.start_background_warmup(interval=1)
        warmup._running = False  # 清理


# ---------------------------------------------------------------------------
# 全局单例测试
# ---------------------------------------------------------------------------


class TestGlobalWarmup:
    """get_cache_warmup 单例测试。"""

    def setup_method(self) -> None:
        reset_cache_warmup()

    def teardown_method(self) -> None:
        reset_cache_warmup()

    def test_singleton(self) -> None:
        w1 = get_cache_warmup()
        w2 = get_cache_warmup()
        assert w1 is w2

    def test_default_tasks_registered(self) -> None:
        warmup = get_cache_warmup()
        names = warmup.task_names
        assert "poi" in names
        assert "city_category_index" in names
        assert "user_profiles" in names
        assert "other_datasets" in names

    def test_reset(self) -> None:
        w1 = get_cache_warmup()
        reset_cache_warmup()
        w2 = get_cache_warmup()
        assert w1 is not w2


# ---------------------------------------------------------------------------
# 默认预热任务测试（mock 数据层）
# ---------------------------------------------------------------------------


class TestDefaultWarmupTasks:
    """默认预热任务测试，mock 数据层避免依赖文件系统。"""

    @pytest.mark.asyncio
    async def test_warmup_poi_cache(self) -> None:
        mock_pois = [
            {"id": "1", "name": "A", "city": "BJ", "category": "景点"},
            {"id": "2", "name": "B", "city": "SH", "category": "餐厅"},
            {"id": "3", "name": "C", "city": "BJ", "category": "餐厅"},
        ]
        mock_cache = AsyncMock()

        with patch("backend.services.data_service.get_data", return_value=mock_pois):
            await warmup_poi_cache(mock_cache)

        # 全量 + 2 城市 + cities 列表 + categories 列表 = 5 次 set
        assert mock_cache.set.await_count == 5

    @pytest.mark.asyncio
    async def test_warmup_poi_cache_empty(self) -> None:
        mock_cache = AsyncMock()
        with patch("backend.services.data_service.get_data", return_value=[]):
            await warmup_poi_cache(mock_cache)

        mock_cache.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_warmup_city_category_cache(self) -> None:
        mock_pois = [
            {"city": "BJ", "category": "景点"},
            {"city": "BJ", "category": "餐厅"},
            {"city": "SH", "category": "景点"},
        ]
        mock_cache = AsyncMock()

        with patch("backend.services.data_service.get_data", return_value=mock_pois):
            await warmup_city_category_cache(mock_cache)

        # 3 个组合: BJ:景点, BJ:餐厅, SH:景点
        assert mock_cache.set.await_count == 3

    @pytest.mark.asyncio
    async def test_warmup_user_profiles(self) -> None:
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
            patch("backend.services.user_profiles.USER_PROFILES", mock_profiles),
            patch(
                "backend.services.user_profiles.match_profile",
                return_value="P1",
            ),
        ):
            await warmup_user_profiles(mock_cache)

        # 1 个 profile_match + 1 个 user_profiles dict = 2
        assert mock_cache.set.await_count == 2

    @pytest.mark.asyncio
    async def test_warmup_other_datasets(self) -> None:
        mock_cache = AsyncMock()
        with (
            patch(
                "backend.services.data_service.get_datasets",
                return_value=["city_poi_db", "orders"],
            ),
            patch(
                "backend.services.data_service.get_data",
                return_value=[{"a": 1}],
            ),
        ):
            await warmup_other_datasets(mock_cache)

        # city_poi_db 被跳过，只预热 orders
        assert mock_cache.set.await_count == 1


# ---------------------------------------------------------------------------
# startup_warmup 测试
# ---------------------------------------------------------------------------


class TestStartupWarmup:
    """startup_warmup 函数测试。"""

    @pytest.mark.asyncio
    async def test_startup_warmup(self) -> None:
        from backend.startup.warmup import startup_warmup

        mock_warmup = AsyncMock()
        mock_warmup.warmup_all.return_value = WarmupReport(
            results=[WarmupResult(task_name="t", success=True, duration_ms=10.0)],
            total_duration_ms=10.0,
        )

        with patch(
            "backend.startup.warmup.get_cache_warmup",
            return_value=mock_warmup,
        ):
            result = await startup_warmup()

        assert result is mock_warmup
        mock_warmup.warmup_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_startup_warmup_with_background(self) -> None:
        from backend.startup.warmup import startup_warmup_with_background

        mock_warmup = AsyncMock()
        mock_warmup.warmup_all.return_value = WarmupReport(
            results=[WarmupResult(task_name="t", success=True, duration_ms=10.0)],
            total_duration_ms=10.0,
        )

        with patch(
            "backend.startup.warmup.get_cache_warmup",
            return_value=mock_warmup,
        ):
            warmup, task = await startup_warmup_with_background(interval=1)

        assert warmup is mock_warmup
        assert isinstance(task, asyncio.Task)
        # 清理后台任务
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
