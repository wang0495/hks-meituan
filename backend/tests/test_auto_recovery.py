"""自动恢复模块单元测试。"""

from __future__ import annotations

import pytest

from backend.services.auto_recovery import (AutoRecovery, RecoveryAttempt,
                                            RecoveryResult, RecoveryStatus)


class TestRecoveryAttempt:
    def test_to_dict(self) -> None:
        attempt = RecoveryAttempt(
            service="database",
            status=RecoveryStatus.SUCCESS,
            attempt=1,
            latency_ms=50.0,
        )
        d = attempt.to_dict()
        assert d["service"] == "database"
        assert d["status"] == "success"
        assert d["attempt"] == 1
        assert d["latency_ms"] == 50.0

    def test_to_dict_with_error(self) -> None:
        attempt = RecoveryAttempt(
            service="redis",
            status=RecoveryStatus.FAILED,
            error="timeout",
        )
        d = attempt.to_dict()
        assert d["error"] == "timeout"


class TestRecoveryResult:
    def test_all_succeeded_true(self) -> None:
        result = RecoveryResult(
            attempts=[
                RecoveryAttempt(service="a", status=RecoveryStatus.SUCCESS),
                RecoveryAttempt(service="b", status=RecoveryStatus.SUCCESS),
            ]
        )
        assert result.all_succeeded is True

    def test_all_succeeded_false(self) -> None:
        result = RecoveryResult(
            attempts=[
                RecoveryAttempt(service="a", status=RecoveryStatus.SUCCESS),
                RecoveryAttempt(service="b", status=RecoveryStatus.FAILED),
            ]
        )
        assert result.all_succeeded is False

    def test_empty_is_success(self) -> None:
        result = RecoveryResult(attempts=[])
        assert result.all_succeeded is True

    def test_to_dict(self) -> None:
        result = RecoveryResult(
            attempts=[
                RecoveryAttempt(service="a", status=RecoveryStatus.SUCCESS),
            ]
        )
        d = result.to_dict()
        assert d["all_succeeded"] is True
        assert len(d["attempts"]) == 1


class TestAutoRecovery:
    @pytest.mark.asyncio
    async def test_no_action_for_unregistered(self) -> None:
        recovery = AutoRecovery()
        result = await recovery.attempt("unknown")
        assert result.status == RecoveryStatus.NO_ACTION

    @pytest.mark.asyncio
    async def test_success_on_first_try(self) -> None:
        recovery = AutoRecovery(cooldown=0)
        called = False

        async def do_recover() -> None:
            nonlocal called
            called = True

        recovery.register("test", do_recover)
        result = await recovery.attempt("test")

        assert result.status == RecoveryStatus.SUCCESS
        assert result.attempt == 1
        assert called is True
        assert recovery.get_retry_count("test") == 0

    @pytest.mark.asyncio
    async def test_failure_increments_retry(self) -> None:
        recovery = AutoRecovery(cooldown=0, base_delay=0.01)

        async def always_fail() -> None:
            raise ConnectionError("refused")

        recovery.register("test", always_fail)

        result = await recovery.attempt("test")
        assert result.status == RecoveryStatus.FAILED
        assert result.attempt == 1
        assert recovery.get_retry_count("test") == 1

    @pytest.mark.asyncio
    async def test_max_retries_skips(self) -> None:
        recovery = AutoRecovery(max_retries=2, cooldown=0, base_delay=0.01)

        async def always_fail() -> None:
            raise RuntimeError("down")

        recovery.register("test", always_fail)

        # 消耗重试次数
        await recovery.attempt("test")  # 1st
        await recovery.attempt("test")  # 2nd

        # 第 3 次应被跳过
        result = await recovery.attempt("test")
        assert result.status == RecoveryStatus.SKIPPED_MAX_RETRIES
        assert "最大重试次数" in result.error  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_cooldown_skips(self) -> None:
        recovery = AutoRecovery(cooldown=999.0)

        async def do_recover() -> None:
            pass

        recovery.register("test", do_recover)

        # 第一次成功
        await recovery.attempt("test")

        # 冷却期内第二次应跳过
        result = await recovery.attempt("test")
        assert result.status == RecoveryStatus.SKIPPED_COOLDOWN

    @pytest.mark.asyncio
    async def test_success_resets_retry_count(self) -> None:
        recovery = AutoRecovery(cooldown=0, base_delay=0.01)
        call_count = 0

        async def fail_then_succeed() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fail")

        recovery.register("test", fail_then_succeed)

        await recovery.attempt("test")  # fail
        assert recovery.get_retry_count("test") == 1

        await recovery.attempt("test")  # succeed
        assert recovery.get_retry_count("test") == 0

    @pytest.mark.asyncio
    async def test_attempt_many_parallel(self) -> None:
        recovery = AutoRecovery(cooldown=0)

        async def ok_a() -> None:
            pass

        async def ok_b() -> None:
            pass

        recovery.register("a", ok_a)
        recovery.register("b", ok_b)

        result = await recovery.attempt_many(["a", "b"])
        assert result.all_succeeded is True
        assert len(result.attempts) == 2

    @pytest.mark.asyncio
    async def test_attempt_many_empty(self) -> None:
        recovery = AutoRecovery()
        result = await recovery.attempt_many([])
        assert result.all_succeeded is True
        assert result.attempts == []

    @pytest.mark.asyncio
    async def test_attempt_many_partial_failure(self) -> None:
        recovery = AutoRecovery(cooldown=0)

        async def ok() -> None:
            pass

        async def fail() -> None:
            raise RuntimeError("boom")

        recovery.register("good", ok)
        recovery.register("bad", fail)

        result = await recovery.attempt_many(["good", "bad"])
        assert result.all_succeeded is False

        statuses = {a.service: a.status for a in result.attempts}
        assert statuses["good"] == RecoveryStatus.SUCCESS
        assert statuses["bad"] == RecoveryStatus.FAILED

    @pytest.mark.asyncio
    async def test_handle_unhealthy(self) -> None:
        recovery = AutoRecovery(cooldown=0)
        called = False

        async def do_recover() -> None:
            nonlocal called
            called = True

        recovery.register("database", do_recover)

        # 模拟 HealthReport
        class FakeReport:
            unhealthy_names = ["database", "redis"]

        result = await recovery.handle_unhealthy(FakeReport())
        assert called is True
        assert len(result.attempts) == 1  # redis 未注册，不恢复
        assert result.attempts[0].service == "database"

    @pytest.mark.asyncio
    async def test_handle_unhealthy_no_registered(self) -> None:
        recovery = AutoRecovery()

        class FakeReport:
            unhealthy_names = ["unknown"]

        result = await recovery.handle_unhealthy(FakeReport())
        assert result.attempts == []

    @pytest.mark.asyncio
    async def test_history_recorded(self) -> None:
        recovery = AutoRecovery(cooldown=0)

        async def ok() -> None:
            pass

        recovery.register("test", ok)
        await recovery.attempt("test")

        assert len(recovery.history) == 1
        assert recovery.history[0].status == RecoveryStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_get_service_history(self) -> None:
        recovery = AutoRecovery(cooldown=0, base_delay=0.01)

        async def ok() -> None:
            pass

        recovery.register("a", ok)
        recovery.register("b", ok)

        await recovery.attempt("a")
        await recovery.attempt("b")
        await recovery.attempt("a")

        a_history = recovery.get_service_history("a")
        assert len(a_history) == 2
        assert all(h.service == "a" for h in a_history)

    def test_reset_retry_count(self) -> None:
        recovery = AutoRecovery()
        recovery._retry_counts["test"] = 5
        recovery.reset_retry_count("test")
        assert recovery.get_retry_count("test") == 0

    def test_reset_all(self) -> None:
        recovery = AutoRecovery()
        recovery._retry_counts["a"] = 1
        recovery._retry_counts["b"] = 2
        recovery.reset_all()
        assert recovery.get_retry_count("a") == 0
        assert recovery.get_retry_count("b") == 0

    def test_unregister(self) -> None:
        recovery = AutoRecovery()

        async def ok() -> None:
            pass

        recovery.register("test", ok)
        recovery._retry_counts["test"] = 3

        recovery.unregister("test")
        assert "test" not in recovery._actions
        assert "test" not in recovery._retry_counts


class TestExponentialBackoff:
    @pytest.mark.asyncio
    async def test_delay_increases(self) -> None:
        """验证多次失败时等待时间递增。"""
        import time

        recovery = AutoRecovery(
            max_retries=3,
            base_delay=0.05,
            max_delay=1.0,
            cooldown=0,
        )

        async def always_fail() -> None:
            raise RuntimeError("fail")

        recovery.register("test", always_fail)

        # 第 1 次无等待（首次尝试）
        start = time.monotonic()
        await recovery.attempt("test")
        first = time.monotonic() - start

        # 第 2 次有等待（约 0.05s）
        start = time.monotonic()
        await recovery.attempt("test")
        second = time.monotonic() - start

        # 第 2 次应该比第 1 次慢（因为有退避等待）
        assert second > first
