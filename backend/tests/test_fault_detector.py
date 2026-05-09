"""故障检测器单元测试。"""

from __future__ import annotations

import time

import pytest

from backend.resilience.fault_detector import (FaultDetector, FaultEvent,
                                               FaultLevel, get_fault_detector)


class TestFaultLevel:
    def test_levels_exist(self) -> None:
        assert FaultLevel.HEALTHY == "healthy"
        assert FaultLevel.WARNING == "warning"
        assert FaultLevel.CRITICAL == "critical"
        assert FaultLevel.FAULTY == "faulty"


class TestFaultEvent:
    def test_to_dict(self) -> None:
        event = FaultEvent(
            service="test",
            level=FaultLevel.WARNING,
            failure_count=3,
            threshold=5,
        )
        d = event.to_dict()
        assert d["service"] == "test"
        assert d["level"] == "warning"
        assert d["failure_count"] == 3
        assert d["threshold"] == 5
        assert "timestamp" in d


class TestFaultDetector:
    def test_initial_state_healthy(self) -> None:
        detector = FaultDetector(threshold=5)
        assert detector.get_level("any") == FaultLevel.HEALTHY
        assert detector.is_faulty("any") is False
        assert detector.get_failure_count("any") == 0

    def test_record_failure_increments_count(self) -> None:
        detector = FaultDetector(threshold=5)
        detector.record_failure("svc")
        assert detector.get_failure_count("svc") == 1
        detector.record_failure("svc")
        assert detector.get_failure_count("svc") == 2

    def test_warning_at_half_threshold(self) -> None:
        detector = FaultDetector(threshold=10)
        for _ in range(5):  # 50% of 10
            detector.record_failure("svc")
        assert detector.get_level("svc") == FaultLevel.WARNING

    def test_critical_at_eighty_percent(self) -> None:
        detector = FaultDetector(threshold=10)
        for _ in range(8):  # 80% of 10
            detector.record_failure("svc")
        assert detector.get_level("svc") == FaultLevel.CRITICAL

    def test_faulty_at_threshold(self) -> None:
        detector = FaultDetector(threshold=5)
        for _ in range(5):
            detector.record_failure("svc")
        assert detector.is_faulty("svc") is True
        assert detector.get_level("svc") == FaultLevel.FAULTY

    def test_record_success_resets_count(self) -> None:
        detector = FaultDetector(threshold=5)
        for _ in range(4):
            detector.record_failure("svc")
        assert detector.get_failure_count("svc") == 4

        detector.record_success("svc")
        assert detector.get_failure_count("svc") == 0
        assert detector.get_level("svc") == FaultLevel.HEALTHY

    def test_window_expiration(self) -> None:
        detector = FaultDetector(threshold=5, window_sec=0.1)
        for _ in range(4):
            detector.record_failure("svc")
        assert detector.get_failure_count("svc") == 4

        # 等待窗口过期
        time.sleep(0.15)
        assert detector.get_failure_count("svc") == 0

    def test_different_services_independent(self) -> None:
        detector = FaultDetector(threshold=3)
        for _ in range(3):
            detector.record_failure("svc_a")
        assert detector.is_faulty("svc_a") is True
        assert detector.is_faulty("svc_b") is False

    def test_events_recorded_on_level_change(self) -> None:
        detector = FaultDetector(threshold=5)
        for _ in range(3):
            detector.record_failure("svc")

        events = detector.get_service_events("svc")
        # WARNING 级别的事件
        assert any(e.level == FaultLevel.WARNING for e in events)

    def test_no_duplicate_events_same_level(self) -> None:
        detector = FaultDetector(threshold=10)
        for _ in range(5):
            detector.record_failure("svc")
        events_count_after_warning = len(detector.get_service_events("svc"))

        # 再记录一次同级别的失败，不应产生新事件
        detector.record_failure("svc")
        assert len(detector.get_service_events("svc")) == events_count_after_warning

    def test_reset_single_service(self) -> None:
        detector = FaultDetector(threshold=5)
        for _ in range(4):
            detector.record_failure("svc")
        detector.reset("svc")
        assert detector.get_failure_count("svc") == 0

    def test_reset_all(self) -> None:
        detector = FaultDetector(threshold=5)
        for _ in range(4):
            detector.record_failure("svc_a")
            detector.record_failure("svc_b")
        detector.reset()
        assert detector.get_failure_count("svc_a") == 0
        assert detector.get_failure_count("svc_b") == 0

    def test_get_all_statuses(self) -> None:
        detector = FaultDetector(threshold=5)
        detector.record_failure("svc_a")
        detector.record_failure("svc_a")
        detector.record_failure("svc_b")

        statuses = detector.get_all_statuses()
        assert "svc_a" in statuses
        assert "svc_b" in statuses
        assert statuses["svc_a"]["failure_count"] == 2
        assert statuses["svc_b"]["failure_count"] == 1

    def test_threshold_setter_validation(self) -> None:
        detector = FaultDetector(threshold=5)
        with pytest.raises(ValueError, match="threshold"):
            detector.threshold = 0

    def test_window_sec_setter_validation(self) -> None:
        detector = FaultDetector(threshold=5)
        with pytest.raises(ValueError, match="window_sec"):
            detector.window_sec = 0

    def test_events_history(self) -> None:
        detector = FaultDetector(threshold=3, history_size=10)
        for _ in range(3):
            detector.record_failure("svc")
        assert len(detector.events) > 0
        assert all(isinstance(e, FaultEvent) for e in detector.events)


class TestGetFaultDetector:
    def test_singleton(self) -> None:
        # Reset global state
        import backend.resilience.fault_detector as mod

        mod._fault_detector = None

        d1 = get_fault_detector()
        d2 = get_fault_detector()
        assert d1 is d2

        # Cleanup
        mod._fault_detector = None
