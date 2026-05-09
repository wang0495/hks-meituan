"""重试机制单元测试。"""

from __future__ import annotations

import pytest

from backend.services.retry import RetryExhaustedError, retry


class TestRetryDecorator:
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self) -> None:
        call_count = 0

        @retry(max_retries=3, delay=0.01)
        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeed()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self) -> None:
        call_count = 0

        @retry(max_retries=2, delay=0.01, backoff=1.0, jitter=False)
        async def fail_twice_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "ok"

        result = await fail_twice_then_succeed()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_exhaustion(self) -> None:
        call_count = 0

        @retry(max_retries=1, delay=0.01, jitter=False)
        async def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("down")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await always_fail()

        assert exc_info.value.attempts == 2
        assert isinstance(exc_info.value.last_exception, ConnectionError)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_only_retries_specified_exceptions(self) -> None:
        call_count = 0

        @retry(max_retries=3, delay=0.01, exceptions=(TimeoutError,))
        async def raise_value_error() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("wrong type")

        with pytest.raises(ValueError):
            await raise_value_error()

        # ValueError 不在重试列表中，只调用一次
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self) -> None:
        retry_log: list[tuple[int, str]] = []

        def on_retry(attempt: int, exc: BaseException) -> None:
            retry_log.append((attempt, str(exc)))

        @retry(max_retries=2, delay=0.01, on_retry=on_retry, jitter=False)
        async def fail_then_succeed() -> str:
            if len(retry_log) < 2:
                raise TimeoutError("timeout")
            return "ok"

        result = await fail_then_succeed()
        assert result == "ok"
        assert len(retry_log) == 2
        assert retry_log[0][0] == 1
        assert retry_log[1][0] == 2

    @pytest.mark.asyncio
    async def test_max_delay_respected(self) -> None:
        """验证延迟不会超过 max_delay。"""
        import time

        @retry(max_retries=1, delay=100.0, max_delay=0.02, jitter=False)
        async def fail_once() -> None:
            raise TimeoutError("timeout")

        start = time.monotonic()
        with pytest.raises(RetryExhaustedError):
            await fail_once()
        elapsed = time.monotonic() - start

        # max_delay=0.02, 所以等待时间应远小于 100s
        assert elapsed < 1.0

    def test_sync_function_support(self) -> None:
        call_count = 0

        @retry(max_retries=2, delay=0.01, jitter=False)
        def sync_fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("fail")
            return "done"

        result = sync_fail_then_succeed()
        assert result == "done"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_zero_retries(self) -> None:
        """max_retries=0 时不重试，直接抛出。"""

        @retry(max_retries=0, delay=0.01)
        async def fail_once() -> None:
            raise RuntimeError("fail")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await fail_once()

        assert exc_info.value.attempts == 1
