"""异步并行处理模块测试。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.services.parallel import parallel_filter, parallel_map, parallel_solve, with_timeout

# ---------------------------------------------------------------------------
# parallel_filter 测试
# ---------------------------------------------------------------------------


class TestParallelFilter:
    """并行过滤测试。"""

    @pytest.mark.asyncio
    async def test_basic_filter(self) -> None:
        items = [1, 2, 3, 4, 5, 6]

        async def is_even(x: int) -> bool:
            return x % 2 == 0

        result = await parallel_filter(items, is_even, max_workers=2)
        assert sorted(result) == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        async def always_true(x: Any) -> bool:
            return True

        result = await parallel_filter([], always_true)
        assert result == []

    @pytest.mark.asyncio
    async def test_all_filtered_out(self) -> None:
        async def always_false(x: Any) -> bool:
            return False

        result = await parallel_filter([1, 2, 3], always_false)
        assert result == []

    @pytest.mark.asyncio
    async def test_filter_preserves_order(self) -> None:
        items = [1, 2, 3, 4, 5]

        async def greater_than_two(x: int) -> bool:
            await asyncio.sleep(0.01)  # 模拟异步操作
            return x > 2

        result = await parallel_filter(items, greater_than_two, max_workers=3)
        assert result == [3, 4, 5]

    @pytest.mark.asyncio
    async def test_filter_handles_exceptions(self) -> None:
        """过滤函数抛出异常时，该元素被跳过。"""

        async def maybe_fail(x: int) -> bool:
            if x == 3:
                raise ValueError("boom")
            return True

        result = await parallel_filter([1, 2, 3, 4], maybe_fail)
        assert 3 not in result
        assert 1 in result
        assert 2 in result
        assert 4 in result


# ---------------------------------------------------------------------------
# parallel_map 测试
# ---------------------------------------------------------------------------


class TestParallelMap:
    """并行映射测试。"""

    @pytest.mark.asyncio
    async def test_basic_map(self) -> None:
        async def double(x: int) -> int:
            return x * 2

        result = await parallel_map([1, 2, 3], double)
        assert result == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_preserves_order(self) -> None:
        async def slow_identity(x: int) -> int:
            await asyncio.sleep(0.05 * (5 - x))  # 倒序延迟
            return x

        result = await parallel_map([1, 2, 3, 4, 5], slow_identity, max_workers=5)
        assert result == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        async def identity(x: Any) -> Any:
            return x

        result = await parallel_map([], identity)
        assert result == []


# ---------------------------------------------------------------------------
# parallel_solve 测试
# ---------------------------------------------------------------------------


class TestParallelSolve:
    """并行求解测试。"""

    @pytest.mark.asyncio
    async def test_returns_best_score(self) -> None:
        call_count = 0

        async def solve() -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            # 返回不同分数的路线
            scores = [0.5, 0.9, 0.3]
            idx = (call_count - 1) % 3
            return {"route": [f"route_{idx}"], "score": scores[idx]}

        result = await parallel_solve(solve, n_attempts=3)
        assert result["score"] == 0.9

    @pytest.mark.asyncio
    async def test_handles_exceptions(self) -> None:
        call_count = 0

        async def sometimes_fail() -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("fail")
            return {"route": [], "score": 0.5}

        result = await parallel_solve(sometimes_fail, n_attempts=3)
        assert "route" in result

    @pytest.mark.asyncio
    async def test_all_fail_returns_empty(self) -> None:
        async def always_fail() -> dict[str, Any]:
            raise ValueError("fail")

        result = await parallel_solve(always_fail, n_attempts=3)
        assert result == {}


# ---------------------------------------------------------------------------
# with_timeout 测试
# ---------------------------------------------------------------------------


class TestWithTimeout:
    """超时包装测试。"""

    @pytest.mark.asyncio
    async def test_completes_before_timeout(self) -> None:
        async def fast() -> str:
            return "done"

        result = await with_timeout(fast(), timeout_seconds=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback(self) -> None:
        async def slow() -> str:
            await asyncio.sleep(10)
            return "done"

        result = await with_timeout(slow(), timeout_seconds=0.1, fallback="fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_timeout_returns_none_by_default(self) -> None:
        async def slow() -> str:
            await asyncio.sleep(10)
            return "done"

        result = await with_timeout(slow(), timeout_seconds=0.1)
        assert result is None
