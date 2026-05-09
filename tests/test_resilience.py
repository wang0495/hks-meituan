"""CityFlow 弹性组件测试。

覆盖以下模块（当前 0% 覆盖率）：
- backend/services/circuit_breaker.py
- backend/services/retry.py
- backend/services/fallback.py
- backend/services/resilient_service.py
"""

from __future__ import annotations

import time

import pytest

from backend.services.circuit_breaker import (CircuitBreaker,
                                              CircuitBreakerMetrics,
                                              CircuitBreakerOpenError,
                                              CircuitState)
from backend.services.fallback import (FallbackError, fallback,
                                       fallback_emotion_analysis,
                                       fallback_llm_chat,
                                       fallback_narrative_generation,
                                       fallback_poi_search,
                                       fallback_route_planning)
from backend.services.retry import RetryExhaustedError, retry

# ===========================================================================
# CircuitBreaker
# ===========================================================================


class TestCircuitState:
    """CircuitState 枚举测试。"""

    def test_states_exist(self) -> None:
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"

    def test_str_enum(self) -> None:
        assert isinstance(CircuitState.CLOSED, str)
        assert str(CircuitState.CLOSED) == "CircuitState.CLOSED"


class TestCircuitBreakerMetrics:
    """CircuitBreakerMetrics 测试。"""

    def test_initial_state(self) -> None:
        m = CircuitBreakerMetrics("test")
        assert m.name == "test"
        assert m.success_count == 0
        assert m.failure_count == 0
        assert m.rejected_count == 0
        assert m.state_changes == 0

    def test_record_success(self) -> None:
        m = CircuitBreakerMetrics("test")
        m.record_success()
        m.record_success()
        assert m.success_count == 2

    def test_record_failure(self) -> None:
        m = CircuitBreakerMetrics("test")
        m.record_failure()
        assert m.failure_count == 1

    def test_record_rejected(self) -> None:
        m = CircuitBreakerMetrics("test")
        m.record_rejected()
        assert m.rejected_count == 1

    def test_record_state_change(self) -> None:
        m = CircuitBreakerMetrics("test")
        m.record_state_change()
        assert m.state_changes == 1

    def test_as_dict(self) -> None:
        m = CircuitBreakerMetrics("test")
        m.record_success()
        m.record_failure()
        m.record_rejected()
        m.record_state_change()
        d = m.as_dict()
        assert d == {
            "success_count": 1,
            "failure_count": 1,
            "rejected_count": 1,
            "state_changes": 1,
        }


class TestCircuitBreaker:
    """CircuitBreaker 核心测试。"""

    def test_initial_state(self) -> None:
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30.0

    def test_record_success_resets_count(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_record_failure_opens_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()  # 第3次，触发打开
        assert cb.state == CircuitState.OPEN

    def test_open_circuit_rejects(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test")
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            cb.reject_if_open()

    def test_closed_circuit_passes(self) -> None:
        cb = CircuitBreaker(name="test")
        cb.reject_if_open()  # 不应抛异常

    def test_recovery_timeout(self) -> None:
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            name="test",
        )
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,
            name="test",
        )
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_manual_trip(self) -> None:
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        cb.trip()
        assert cb.state == CircuitState.OPEN

    def test_manual_reset(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test")
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_repr(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=5)
        r = repr(cb)
        assert "test" in r
        assert "closed" in r

    def test_metrics_property(self) -> None:
        cb = CircuitBreaker(name="test")
        assert isinstance(cb.metrics, CircuitBreakerMetrics)


class TestCircuitBreakerDecorator:
    """CircuitBreaker 作为装饰器的测试。"""

    @pytest.mark.asyncio
    async def test_async_decorator_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test_async")

        @cb
        async def my_func() -> str:
            return "ok"

        result = await my_func()
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_async_decorator_failure_opens(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, name="test_async_fail")

        @cb
        async def my_func() -> str:
            raise TimeoutError("timeout")

        with pytest.raises(TimeoutError):
            await my_func()
        with pytest.raises(TimeoutError):
            await my_func()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_async_decorator_open_rejects(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test_reject")

        @cb
        async def my_func() -> str:
            raise TimeoutError()

        with pytest.raises(TimeoutError):
            await my_func()
        with pytest.raises(CircuitBreakerOpenError):
            await my_func()

    def test_sync_decorator_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, name="test_sync")

        @cb
        def my_func() -> str:
            return "ok"

        assert my_func() == "ok"

    def test_sync_decorator_failure(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test_sync_fail")

        @cb
        def my_func() -> str:
            raise ValueError("bad")

        with pytest.raises(ValueError):
            my_func()
        assert cb.state == CircuitState.OPEN

    def test_sync_decorator_open_rejects(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, name="test_sync_reject")

        @cb
        def my_func() -> str:
            raise ValueError()

        with pytest.raises(ValueError):
            my_func()
        with pytest.raises(CircuitBreakerOpenError):
            my_func()


class TestCircuitBreakerOpenError:
    """CircuitBreakerOpenError 测试。"""

    def test_default_message(self) -> None:
        err = CircuitBreakerOpenError()
        assert "熔断器已打开" in err.message

    def test_custom_message(self) -> None:
        err = CircuitBreakerOpenError(message="custom")
        assert err.message == "custom"

    def test_inherits_cityflow(self) -> None:
        from backend.errors import CityFlowException

        err = CircuitBreakerOpenError()
        assert isinstance(err, CityFlowException)


# ===========================================================================
# Retry
# ===========================================================================


class TestRetry:
    """retry 装饰器测试。"""

    @pytest.mark.asyncio
    async def test_async_success_first_try(self) -> None:
        call_count = 0

        @retry(max_retries=3, delay=0.01, jitter=False)
        async def my_func() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await my_func()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_then_success(self) -> None:
        call_count = 0

        @retry(max_retries=3, delay=0.01, jitter=False)
        async def my_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "ok"

        result = await my_func()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_exhausted(self) -> None:
        @retry(max_retries=2, delay=0.01, jitter=False)
        async def my_func() -> str:
            raise ConnectionError("connection refused")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await my_func()
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ConnectionError)

    @pytest.mark.asyncio
    async def test_async_on_retry_callback(self) -> None:
        retry_args: list[tuple[int, BaseException]] = []

        def on_retry(attempt: int, exc: BaseException) -> None:
            retry_args.append((attempt, exc))

        call_count = 0

        @retry(max_retries=2, delay=0.01, jitter=False, on_retry=on_retry)
        async def my_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "ok"

        result = await my_func()
        assert result == "ok"
        assert len(retry_args) == 2
        assert retry_args[0][0] == 1

    @pytest.mark.asyncio
    async def test_async_only_specific_exceptions(self) -> None:
        @retry(max_retries=3, delay=0.01, exceptions=(TimeoutError,))
        async def my_func() -> str:
            raise ValueError("not retried")

        with pytest.raises(ValueError):
            await my_func()

    def test_sync_success(self) -> None:
        call_count = 0

        @retry(max_retries=3, delay=0.01, jitter=False)
        def my_func() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        assert my_func() == "ok"
        assert call_count == 1

    def test_sync_retry_then_success(self) -> None:
        call_count = 0

        @retry(max_retries=3, delay=0.01, jitter=False)
        def my_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("fail")
            return "ok"

        assert my_func() == "ok"
        assert call_count == 2

    def test_sync_retry_exhausted(self) -> None:
        @retry(max_retries=1, delay=0.01, jitter=False)
        def my_func() -> str:
            raise RuntimeError("always fail")

        with pytest.raises(RetryExhaustedError):
            my_func()

    def test_max_delay(self) -> None:
        @retry(max_retries=10, delay=100.0, backoff=10.0, max_delay=1.0, jitter=False)
        def my_func() -> str:
            raise RuntimeError()

        # 如果 max_delay 不生效，测试会非常慢
        import time as _time

        start = _time.monotonic()
        with pytest.raises(RetryExhaustedError):
            my_func()
        elapsed = _time.monotonic() - start
        # 总延迟应该远小于没有 max_delay 的情况
        assert elapsed < 30.0

    @pytest.mark.asyncio
    async def test_on_retry_callback_exception_is_ignored(self) -> None:
        def bad_callback(attempt: int, exc: BaseException) -> None:
            raise RuntimeError("callback error")

        call_count = 0

        @retry(max_retries=2, delay=0.01, jitter=False, on_retry=bad_callback)
        async def my_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError()
            return "ok"

        result = await my_func()
        assert result == "ok"


class TestRetryExhaustedError:
    """RetryExhaustedError 测试。"""

    def test_attributes(self) -> None:
        err = RetryExhaustedError(
            message="failed",
            last_exception=ValueError("inner"),
            attempts=5,
        )
        assert str(err) == "failed"
        assert err.attempts == 5
        assert isinstance(err.last_exception, ValueError)


# ===========================================================================
# Fallback
# ===========================================================================


class TestFallbackDecorator:
    """fallback 装饰器测试。"""

    @pytest.mark.asyncio
    async def test_async_success_no_fallback(self) -> None:
        async def my_fallback(*args, **kwargs):
            return "fallback"

        @fallback(my_fallback)
        async def my_func() -> str:
            return "ok"

        assert await my_func() == "ok"

    @pytest.mark.asyncio
    async def test_async_failure_triggers_fallback(self) -> None:
        async def my_fallback(*args, **kwargs):
            return "fallback"

        @fallback(my_fallback)
        async def my_func() -> str:
            raise RuntimeError("fail")

        assert await my_func() == "fallback"

    @pytest.mark.asyncio
    async def test_async_specific_exception(self) -> None:
        async def my_fallback(*args, **kwargs):
            return "fallback"

        @fallback(my_fallback, exceptions=(TimeoutError,))
        async def my_func() -> str:
            raise ValueError("not caught")

        with pytest.raises(ValueError):
            await my_func()

    @pytest.mark.asyncio
    async def test_async_fallback_also_fails(self) -> None:
        async def bad_fallback(*args, **kwargs):
            raise RuntimeError("fallback also broke")

        @fallback(bad_fallback)
        async def my_func() -> str:
            raise TimeoutError("primary fail")

        with pytest.raises(RuntimeError):
            await my_func()

    def test_sync_success(self) -> None:
        def my_fallback(*args, **kwargs):
            return "fallback"

        @fallback(my_fallback)
        def my_func() -> str:
            return "ok"

        assert my_func() == "ok"

    def test_sync_failure_triggers_fallback(self) -> None:
        def my_fallback(*args, **kwargs):
            return "fallback"

        @fallback(my_fallback)
        def my_func() -> str:
            raise RuntimeError("fail")

        assert my_func() == "fallback"

    def test_sync_fallback_also_fails(self) -> None:
        def bad_fallback(*args, **kwargs):
            raise RuntimeError("fallback broke")

        @fallback(bad_fallback)
        def my_func() -> str:
            raise TimeoutError("primary")

        with pytest.raises(RuntimeError):
            my_func()


class TestFallbackFunctions:
    """预定义降级函数测试。"""

    @pytest.mark.asyncio
    async def test_fallback_route_planning(self) -> None:
        result = await fallback_route_planning()
        assert result["fallback"] is True
        assert result["route"] == []
        assert "narrative" in result

    @pytest.mark.asyncio
    async def test_fallback_poi_search(self) -> None:
        result = await fallback_poi_search()
        assert result["fallback"] is True
        assert result["pois"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_fallback_narrative_generation(self) -> None:
        result = await fallback_narrative_generation()
        assert result["fallback"] is True
        assert "opening" in result
        assert "steps" in result

    @pytest.mark.asyncio
    async def test_fallback_llm_chat(self) -> None:
        result = await fallback_llm_chat()
        assert isinstance(result, str)
        assert "暂时无法" in result

    @pytest.mark.asyncio
    async def test_fallback_emotion_analysis(self) -> None:
        result = await fallback_emotion_analysis()
        assert all(0.0 <= v <= 1.0 for v in result.values())
        assert "excitement" in result
        assert "tranquility" in result


class TestFallbackError:
    """FallbackError 测试。"""

    def test_is_exception(self) -> None:
        err = FallbackError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"


# ===========================================================================
# Resilient service integration
# ===========================================================================


class TestResilientService:
    """resilient_service 模块测试。"""

    def test_get_all_circuit_breakers(self) -> None:
        from backend.services.resilient_service import get_all_circuit_breakers

        result = get_all_circuit_breakers()
        assert "llm" in result
        llm_data = result["llm"]
        assert "state" in llm_data
        assert "failure_count" in llm_data
        assert "failure_threshold" in llm_data
        assert "recovery_timeout" in llm_data
        assert "metrics" in llm_data

    def test_llm_circuit_breaker_config(self) -> None:
        from backend.services.resilient_service import llm_circuit_breaker

        assert llm_circuit_breaker.failure_threshold == 3
        assert llm_circuit_breaker.recovery_timeout == 60.0
        assert llm_circuit_breaker.name == "llm"
