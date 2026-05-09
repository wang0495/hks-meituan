"""熔断器单元测试。"""

from __future__ import annotations

import pytest

from backend.services.circuit_breaker import (CircuitBreaker,
                                              CircuitBreakerOpenError,
                                              CircuitState)


class TestCircuitState:
    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test")
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2

    def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test")
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_to_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, name="test")
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 未超时，仍然是 OPEN
        assert cb.state == CircuitState.OPEN

        # 等待恢复超时
        import time

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, name="test")
        cb.record_failure()

        import time

        time.sleep(0.02)
        # 现在是 HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, name="test")
        cb.record_failure()

        import time

        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, name="test")
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerDecorator:
    @pytest.mark.asyncio
    async def test_passes_through_when_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test")

        @cb
        async def work() -> str:
            return "ok"

        assert await work() == "ok"

    @pytest.mark.asyncio
    async def test_records_failure_on_exception(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, name="test")

        @cb
        async def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await fail()

        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED

        with pytest.raises(ValueError):
            await fail()

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_rejects_when_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test")
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        @cb
        async def work() -> str:
            return "ok"

        with pytest.raises(CircuitBreakerOpenError):
            await work()

    @pytest.mark.asyncio
    async def test_only_catches_expected_exceptions(self) -> None:
        cb = CircuitBreaker(
            failure_threshold=3,
            expected_exception=(TimeoutError,),
            name="test",
        )

        @cb
        async def raise_value_error() -> None:
            raise ValueError("not expected")

        # ValueError 不在 expected_exception 中，不会被记录为失败
        with pytest.raises(ValueError):
            await raise_value_error()

        assert cb.failure_count == 0

    def test_sync_function_support(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, name="test")

        @cb
        def sync_work() -> str:
            return "sync_ok"

        assert sync_work() == "sync_ok"
        assert cb.metrics.success_count == 1


class TestCircuitBreakerManualControl:
    def test_reset(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test")
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_trip(self) -> None:
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

        cb.trip()
        assert cb.state == CircuitState.OPEN

    def test_reject_if_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test")
        cb.record_failure()

        with pytest.raises(CircuitBreakerOpenError):
            cb.reject_if_open()

    def test_reject_if_open_noop_when_closed(self) -> None:
        cb = CircuitBreaker(name="test")
        cb.reject_if_open()  # 应该不抛异常


class TestCircuitBreakerMetrics:
    def test_tracks_counts(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, name="test")
        cb.record_success()
        cb.record_success()
        cb.record_failure()

        m = cb.metrics.as_dict()
        assert m["success_count"] == 2
        assert m["failure_count"] == 1

    def test_tracks_rejected(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test")
        cb.record_failure()
        # OPEN 状态
        try:
            cb.reject_if_open()
        except CircuitBreakerOpenError:
            pass

        assert cb.metrics.rejected_count == 1
