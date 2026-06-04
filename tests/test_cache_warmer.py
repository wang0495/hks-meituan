"""cache_warmup 模块测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.cache_warmup import (
    schedule_cache_refresh,
    warmup_memory_caches,
    warmup_multilevel_cache,
)


# ---------------------------------------------------------------------------
# warmup_multilevel_cache 测试
# ---------------------------------------------------------------------------


class TestWarmupMultilevelCache:
    """warmup_multilevel_cache 异步预热测试。"""

    @pytest.mark.asyncio
    async def test_warmup_with_data(self) -> None:
        mock_pois = [
            {"id": "1", "name": "A", "city": "BJ", "category": "景点"},
            {"id": "2", "name": "B", "city": "SH", "category": "餐厅"},
            {"id": "3", "name": "C", "city": "BJ", "category": "餐厅"},
        ]
        mock_cache = AsyncMock()

        with (
            patch("backend.services.cache_warmup.get_multilevel_cache", return_value=mock_cache),
            patch("backend.services.cache_warmup.get_data", return_value=mock_pois),
        ):
            await warmup_multilevel_cache()

        # all_pois + cities + categories + dataset calls
        assert mock_cache.set.await_count >= 3

    @pytest.mark.asyncio
    async def test_warmup_empty_data(self) -> None:
        mock_cache = AsyncMock()
        with (
            patch("backend.services.cache_warmup.get_multilevel_cache", return_value=mock_cache),
            patch("backend.services.cache_warmup.get_data", return_value=[]),
        ):
            await warmup_multilevel_cache()

        # 无数据时不会调用 set
        mock_cache.set.assert_not_awaited()


# ---------------------------------------------------------------------------
# warmup_memory_caches 测试
# ---------------------------------------------------------------------------


class TestWarmupMemoryCaches:
    """warmup_memory_caches 同步预热测试。"""

    def test_warmup_with_data(self) -> None:
        mock_pois = [
            {"id": "1", "name": "A", "city": "BJ", "category": "景点"},
            {"id": "2", "name": "B", "city": "SH", "category": "餐厅"},
            {"id": "3", "name": "C", "city": "BJ", "category": "餐厅"},
        ]

        mock_poi_cache = MagicMock()
        mock_general_cache = MagicMock()

        # warmup_memory_caches does local imports from backend.services.cache
        with (
            patch("backend.services.cache.poi_cache", mock_poi_cache),
            patch("backend.services.cache.general_cache", mock_general_cache),
        ):
            warmup_memory_caches(mock_pois)

        # 2 cities: BJ, SH
        assert mock_poi_cache.set.call_count == 2
        # 1 categories call
        assert mock_general_cache.set.call_count == 1

    def test_warmup_empty(self) -> None:
        with patch("backend.services.cache_warmup.get_data", return_value=[]):
            warmup_memory_caches([])

    def test_warmup_none_uses_get_data(self) -> None:
        with patch("backend.services.cache_warmup.get_data", return_value=[]):
            warmup_memory_caches(None)


# ---------------------------------------------------------------------------
# schedule_cache_refresh 测试
# ---------------------------------------------------------------------------


class TestScheduleCacheRefresh:
    """schedule_cache_refresh 定时任务测试。"""

    @pytest.mark.asyncio
    async def test_runs_and_can_be_cancelled(self) -> None:
        call_count = 0

        async def counting_warmup() -> None:
            nonlocal call_count
            call_count += 1

        with patch("backend.services.cache_warmup.warmup_multilevel_cache", counting_warmup):
            task = asyncio.create_task(schedule_cache_refresh(interval_seconds=1))

            # 等第一次执行
            await asyncio.sleep(1.5)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_continues_on_error(self) -> None:
        call_count = 0

        async def failing_warmup() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")

        with patch("backend.services.cache_warmup.warmup_multilevel_cache", failing_warmup):
            task = asyncio.create_task(schedule_cache_refresh(interval_seconds=1))

            await asyncio.sleep(2.5)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        # 第一次失败后仍会继续
        assert call_count >= 2
