"""自愈管理器单元测试。"""

from __future__ import annotations

import pytest
from backend.resilience.fault_detector import FaultDetector
from backend.resilience.self_healing import (
    DegradationLevel,
    HealingAttempt,
    HealingStatus,
    SelfHealing,
    get_self_healing,
)


@pytest.fixture
def detector() -> FaultDetector:
    return FaultDetector(threshold=3, window_sec=60.0)


@pytest.fixture
def healing(detector: FaultDetector) -> SelfHealing:
    return SelfHealing(fault_detector=detector)


class TestHealingAttempt:
    def test_to_dict(self) -> None:
        attempt = HealingAttempt(
            service="test",
            status=HealingStatus.RECOVERED,
            recovery_succeeded=True,
            degradation_level=DegradationLevel.NONE,
            latency_ms=123.45,
        )
        d = attempt.to_dict()
        assert d["service"] == "test"
        assert d["status"] == "recovered"
        assert d["recovery_succeeded"] is True
        assert d["latency_ms"] == 123.45
        assert "timestamp" in d


class TestDegradationLevel:
    def test_levels(self) -> None:
        assert DegradationLevel.NONE == "none"
        assert DegradationLevel.LIGHT == "light"
        assert DegradationLevel.HEAVY == "heavy"
        assert DegradationLevel.FULL == "full"


class TestSelfHealing:
    @pytest.mark.asyncio
    async def test_heal_no_registered_service(self, healing: SelfHealing) -> None:
        attempt = await healing.heal("unknown")
        assert attempt.status == HealingStatus.NO_ACTION

    @pytest.mark.asyncio
    async def test_heal_recovery_success(self, healing: SelfHealing) -> None:
        called = False

        async def mock_recovery() -> None:
            nonlocal called
            called = True

        healing.register_service("svc", recovery=mock_recovery)
        attempt = await healing.heal("svc")

        assert attempt.status == HealingStatus.RECOVERED
        assert attempt.recovery_succeeded is True
        assert called is True

    @pytest.mark.asyncio
    async def test_heal_recovery_failure_degrades(
        self, healing: SelfHealing, detector: FaultDetector
    ) -> None:
        degraded_level = None

        async def mock_recovery() -> None:
            raise ConnectionError("连接失败")

        async def mock_degradation(level: DegradationLevel) -> None:
            nonlocal degraded_level
            degraded_level = level

        healing.register_service("svc", recovery=mock_recovery, degradation=mock_degradation)
        attempt = await healing.heal("svc")

        assert attempt.status == HealingStatus.DEGRADED
        assert attempt.recovery_succeeded is False
        assert degraded_level is not None

    @pytest.mark.asyncio
    async def test_heal_already_degraded_skips(
        self, healing: SelfHealing, detector: FaultDetector
    ) -> None:
        async def mock_recovery() -> None:
            raise ConnectionError("fail")

        healing.register_service("svc", recovery=mock_recovery)

        # First heal -> degraded
        await healing.heal("svc")
        assert healing.is_degraded("svc")

        # Second heal -> already degraded
        attempt = await healing.heal("svc")
        assert attempt.status == HealingStatus.ALREADY_DEGRADED

    @pytest.mark.asyncio
    async def test_heal_cooldown(self, healing: SelfHealing) -> None:
        async def mock_recovery() -> None:
            pass

        healing.register_service("svc", recovery=mock_recovery, cooldown_sec=60.0)

        # First heal succeeds
        await healing.heal("svc")

        # Second heal within cooldown
        attempt = await healing.heal("svc")
        assert attempt.status == HealingStatus.SKIPPED_COOLDOWN

    @pytest.mark.asyncio
    async def test_heal_many(self, healing: SelfHealing) -> None:
        async def mock_recovery() -> None:
            pass

        healing.register_service("svc_a", recovery=mock_recovery)
        healing.register_service("svc_b", recovery=mock_recovery)

        results = await healing.heal_many(["svc_a", "svc_b"])
        assert len(results) == 2
        assert all(r.status == HealingStatus.RECOVERED for r in results)

    @pytest.mark.asyncio
    async def test_heal_many_empty(self, healing: SelfHealing) -> None:
        results = await healing.heal_many([])
        assert results == []

    @pytest.mark.asyncio
    async def test_heal_all_faulty(self, healing: SelfHealing, detector: FaultDetector) -> None:
        async def mock_recovery() -> None:
            pass

        healing.register_service("svc", recovery=mock_recovery)

        # Make service faulty
        for _ in range(3):
            detector.record_failure("svc")
        assert detector.is_faulty("svc")

        results = await healing.heal_all_faulty()
        assert len(results) == 1
        assert results[0].status == HealingStatus.RECOVERED

    def test_record_success_exits_degradation(
        self, healing: SelfHealing, detector: FaultDetector
    ) -> None:
        # Simulate degraded state
        healing._degraded_services["svc"] = DegradationLevel.HEAVY

        healing.record_success("svc")
        assert not healing.is_degraded("svc")

    def test_is_degraded_false_by_default(self, healing: SelfHealing) -> None:
        assert healing.is_degraded("svc") is False

    def test_get_degradation_level_default(self, healing: SelfHealing) -> None:
        assert healing.get_degradation_level("svc") == DegradationLevel.NONE

    def test_get_degraded_services(self, healing: SelfHealing) -> None:
        healing._degraded_services["svc"] = DegradationLevel.LIGHT
        degraded = healing.get_degraded_services()
        assert degraded == {"svc": DegradationLevel.LIGHT}

    @pytest.mark.asyncio
    async def test_probe_service_recovery(
        self, healing: SelfHealing, detector: FaultDetector
    ) -> None:
        probe_called = False

        async def mock_probe() -> bool:
            nonlocal probe_called
            probe_called = True
            return True

        healing.register_service("svc", probe=mock_probe)
        healing._degraded_services["svc"] = DegradationLevel.HEAVY

        ok = await healing.probe_service("svc")
        assert ok is True
        assert probe_called is True
        assert not healing.is_degraded("svc")

    @pytest.mark.asyncio
    async def test_probe_service_still_down(
        self, healing: SelfHealing, detector: FaultDetector
    ) -> None:
        async def mock_probe() -> bool:
            return False

        healing.register_service("svc", probe=mock_probe)
        healing._degraded_services["svc"] = DegradationLevel.HEAVY

        ok = await healing.probe_service("svc")
        assert ok is False
        assert healing.is_degraded("svc")

    @pytest.mark.asyncio
    async def test_probe_service_no_config(self, healing: SelfHealing) -> None:
        ok = await healing.probe_service("unknown")
        assert ok is False

    @pytest.mark.asyncio
    async def test_probe_service_not_degraded(self, healing: SelfHealing) -> None:
        async def mock_probe() -> bool:
            return False

        healing.register_service("svc", probe=mock_probe)

        ok = await healing.probe_service("svc")
        assert ok is True  # Not degraded, so returns True

    @pytest.mark.asyncio
    async def test_probe_all_degraded(self, healing: SelfHealing) -> None:
        async def mock_probe() -> bool:
            return True

        healing.register_service("svc", probe=mock_probe)
        healing._degraded_services["svc"] = DegradationLevel.LIGHT

        results = await healing.probe_all_degraded()
        assert results == {"svc": True}
        assert not healing.is_degraded("svc")

    def test_unregister_service(self, healing: SelfHealing) -> None:
        healing.register_service("svc")
        healing._degraded_services["svc"] = DegradationLevel.LIGHT

        healing.unregister_service("svc")
        assert "svc" not in healing._configs
        assert "svc" not in healing._degraded_services

    def test_history(self, healing: SelfHealing) -> None:
        assert healing.history == []

    def test_get_status(self, healing: SelfHealing) -> None:
        healing.register_service("svc_a")
        healing.register_service("svc_b")
        healing._degraded_services["svc_a"] = DegradationLevel.LIGHT

        status = healing.get_status()
        assert "svc_a" in status["registered_services"]
        assert "svc_b" in status["registered_services"]
        assert status["degraded_services"]["svc_a"] == "light"

    @pytest.mark.asyncio
    async def test_determine_degradation_level_faulty(
        self, healing: SelfHealing, detector: FaultDetector
    ) -> None:
        for _ in range(3):
            detector.record_failure("svc")
        level = healing._determine_degradation_level("svc")
        assert level == DegradationLevel.HEAVY

    @pytest.mark.asyncio
    async def test_determine_degradation_level_critical(
        self, healing: SelfHealing, detector: FaultDetector
    ) -> None:
        for _ in range(2):  # 2/3 = ~67%, should be WARNING not CRITICAL with threshold=3
            detector.record_failure("svc")
        level = healing._determine_degradation_level("svc")
        assert level == DegradationLevel.LIGHT


class TestGetSelfHealing:
    def test_singleton(self) -> None:
        import backend.resilience.self_healing as mod

        mod._self_healing = None

        h1 = get_self_healing()
        h2 = get_self_healing()
        assert h1 is h2

        mod._self_healing = None


class TestDegradeFunctions:
    """降级函数只是日志，确保不抛异常。"""

    @pytest.mark.asyncio
    async def test_degrade_database(self) -> None:
        from backend.resilience.self_healing import degrade_database

        for level in DegradationLevel:
            await degrade_database(level)  # Should not raise

    @pytest.mark.asyncio
    async def test_degrade_redis(self) -> None:
        from backend.resilience.self_healing import degrade_redis

        for level in DegradationLevel:
            await degrade_redis(level)

    @pytest.mark.asyncio
    async def test_degrade_llm_service(self) -> None:
        from backend.resilience.self_healing import degrade_llm_service

        for level in DegradationLevel:
            await degrade_llm_service(level)
