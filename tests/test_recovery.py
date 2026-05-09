"""恢复机制测试。

覆盖 FaultDetector、AutoRecovery、FallbackStrategy 和 RecoveryOrchestrator。
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from backend.recovery.auto_recovery import AutoRecovery
from backend.recovery.fallback import (
    FallbackStrategy,
    fallback_llm_response,
    fallback_nearby_search,
    fallback_route_planning,
)
from backend.recovery.fault_detector import FaultDetector
from backend.recovery.orchestrator import RecoveryOrchestrator


# =========================================================================
# FaultDetector
# =========================================================================


class TestFaultDetector:
    """故障检测器测试。"""

    def test_initial_state(self) -> None:
        """初始状态：无故障。"""
        det = FaultDetector()
        assert not det.is_faulty("svc")
        assert det.get_failure_count("svc") == 0

    def test_record_failure_below_threshold(self) -> None:
        """未达阈值时返回 False。"""
        det = FaultDetector(threshold=3)
        assert det.record_failure("svc") is False
        assert det.record_failure("svc") is False
        assert not det.is_faulty("svc")

    def test_record_failure_reaches_threshold(self) -> None:
        """达到阈值时返回 True 并标记故障。"""
        det = FaultDetector(threshold=3)
        det.record_failure("svc")
        det.record_failure("svc")
        assert det.record_failure("svc") is True
        assert det.is_faulty("svc")

    def test_record_success_resets_count(self) -> None:
        """成功后重置计数。"""
        det = FaultDetector(threshold=3)
        det.record_failure("svc")
        det.record_failure("svc")
        det.record_success("svc")
        assert det.get_failure_count("svc") == 0
        assert not det.is_faulty("svc")

    def test_window_expiry_resets_count(self) -> None:
        """超出时间窗口后计数重置。"""
        det = FaultDetector(threshold=2, window=timedelta(milliseconds=10))
        det.record_failure("svc")
        # 手动把 last_failure 往前推
        from datetime import datetime

        det._last_failure["svc"] = datetime.now() - timedelta(milliseconds=20)
        assert det.record_failure("svc") is False
        assert det.get_failure_count("svc") == 1

    def test_reset_service(self) -> None:
        """手动重置单个服务。"""
        det = FaultDetector(threshold=2)
        det.record_failure("svc")
        det.reset("svc")
        assert det.get_failure_count("svc") == 0
        assert not det.is_faulty("svc")

    def test_reset_all(self) -> None:
        """重置所有服务。"""
        det = FaultDetector(threshold=2)
        det.record_failure("a")
        det.record_failure("b")
        det.reset_all()
        assert det.get_failure_count("a") == 0
        assert det.get_failure_count("b") == 0

    def test_multiple_services_independent(self) -> None:
        """不同服务的计数互相独立。"""
        det = FaultDetector(threshold=2)
        det.record_failure("a")
        det.record_failure("a")
        assert det.is_faulty("a")
        assert not det.is_faulty("b")


# =========================================================================
# AutoRecovery
# =========================================================================


class TestAutoRecovery:
    """自动恢复器测试。"""

    async def test_successful_recovery(self) -> None:
        """一次成功即返回 True。"""
        rec = AutoRecovery(max_retries=3)
        action = AsyncMock()
        rec.register_recovery("svc", action)

        assert await rec.attempt_recovery("svc") is True
        action.assert_called_once()

    async def test_recovery_with_retries(self) -> None:
        """前两次失败、第三次成功。"""
        rec = AutoRecovery(max_retries=3, base_delay=0.01)
        action = AsyncMock(side_effect=[RuntimeError, RuntimeError, None])
        rec.register_recovery("svc", action)

        assert await rec.attempt_recovery("svc") is True
        assert action.call_count == 3

    async def test_recovery_exhausted(self) -> None:
        """全部重试失败返回 False。"""
        rec = AutoRecovery(max_retries=2, base_delay=0.01)
        action = AsyncMock(side_effect=RuntimeError("boom"))
        rec.register_recovery("svc", action)

        assert await rec.attempt_recovery("svc") is False
        assert action.call_count == 2

    async def test_unregistered_service(self) -> None:
        """未注册的服务返回 False。"""
        rec = AutoRecovery()
        assert await rec.attempt_recovery("unknown") is False

    def test_has_recovery(self) -> None:
        """检查注册状态。"""
        rec = AutoRecovery()
        assert not rec.has_recovery("svc")
        rec.register_recovery("svc", AsyncMock())
        assert rec.has_recovery("svc")

    def test_unregister_recovery(self) -> None:
        """移除恢复动作。"""
        rec = AutoRecovery()
        rec.register_recovery("svc", AsyncMock())
        rec.unregister_recovery("svc")
        assert not rec.has_recovery("svc")


# =========================================================================
# FallbackStrategy
# =========================================================================


class TestFallbackStrategy:
    """降级策略测试。"""

    async def test_execute_fallback(self) -> None:
        """执行已注册的降级策略。"""
        fs = FallbackStrategy()
        fallback_fn = AsyncMock(return_value={"fallback": True})
        fs.register("svc", fallback_fn)

        result = await fs.execute("svc", "arg1", key="val")
        assert result == {"fallback": True}
        fallback_fn.assert_called_once_with("arg1", key="val")

    async def test_execute_unregistered_raises(self) -> None:
        """未注册的服务抛出 KeyError。"""
        fs = FallbackStrategy()
        with pytest.raises(KeyError, match="无降级策略"):
            await fs.execute("unknown")

    def test_has_fallback(self) -> None:
        """检查注册状态。"""
        fs = FallbackStrategy()
        assert not fs.has_fallback("svc")
        fs.register("svc", AsyncMock())
        assert fs.has_fallback("svc")

    def test_unregister(self) -> None:
        """移除降级策略。"""
        fs = FallbackStrategy()
        fs.register("svc", AsyncMock())
        fs.unregister("svc")
        assert not fs.has_fallback("svc")


class TestPredefinedFallbacks:
    """预定义降级策略测试。"""

    async def test_fallback_route_planning(self) -> None:
        result = await fallback_route_planning("去珠海渔女")
        assert result["fallback"] is True
        assert result["route"] == []
        assert "请稍后重试" in result["narrative"]["opening"]
        assert result["original_input"] == "去珠海渔女"

    async def test_fallback_nearby_search(self) -> None:
        result = await fallback_nearby_search(22.27, 113.58, "美食")
        assert result["fallback"] is True
        assert result["results"] == []

    async def test_fallback_llm_response(self) -> None:
        result = await fallback_llm_response("你好")
        assert result["fallback"] is True
        assert "不可用" in result["reply"]


# =========================================================================
# RecoveryOrchestrator
# =========================================================================


class TestRecoveryOrchestrator:
    """恢复编排器测试。"""

    async def test_normal_call_success(self) -> None:
        """正常调用成功，计数不增加。"""
        orch = RecoveryOrchestrator()
        svc_fn = AsyncMock(return_value="ok")

        result = await orch.call("svc", svc_fn, "arg1")
        assert result == "ok"
        svc_fn.assert_called_once_with("arg1")
        assert orch.detector.get_failure_count("svc") == 0

    async def test_single_failure_no_recovery(self) -> None:
        """单次失败未达阈值，抛出原始异常。"""
        orch = RecoveryOrchestrator(
            fault_detector=FaultDetector(threshold=3),
        )
        svc_fn = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            await orch.call("svc", svc_fn)

        assert orch.detector.get_failure_count("svc") == 1

    async def test_threshold_reached_recovery_success(self) -> None:
        """达到阈值后恢复成功，重试调用。"""
        orch = RecoveryOrchestrator(
            fault_detector=FaultDetector(threshold=2),
        )
        recovery_fn = AsyncMock()
        orch.recovery.register_recovery("svc", recovery_fn)

        # 前两次失败，恢复成功后第三次成功
        call_count = 0

        async def svc_fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("boom")
            return "ok"

        # 先制造一次失败
        with pytest.raises(RuntimeError):
            await orch.call("svc", svc_fn)

        # 第二次失败触发恢复
        result = await orch.call("svc", svc_fn)
        assert result == "ok"
        recovery_fn.assert_called_once()

    async def test_threshold_reached_recovery_fails_uses_fallback(self) -> None:
        """达到阈值后恢复失败，走降级。"""
        orch = RecoveryOrchestrator(
            fault_detector=FaultDetector(threshold=1),
        )
        orch.recovery.register_recovery("svc", AsyncMock(side_effect=RuntimeError))
        fallback_fn = AsyncMock(return_value={"fallback": True})
        orch.fallback.register("svc", fallback_fn)

        svc_fn = AsyncMock(side_effect=RuntimeError("boom"))
        result = await orch.call("svc", svc_fn)

        assert result == {"fallback": True}
        fallback_fn.assert_called_once()

    async def test_no_fallback_raises_runtime_error(self) -> None:
        """无降级策略时抛出 RuntimeError。"""
        orch = RecoveryOrchestrator(
            fault_detector=FaultDetector(threshold=1),
        )
        orch.recovery.register_recovery("svc", AsyncMock(side_effect=RuntimeError))

        svc_fn = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="故障且无降级策略"):
            await orch.call("svc", svc_fn)

    async def test_already_faulty_tries_recovery_first(self) -> None:
        """服务已处于故障状态时，先尝试恢复。"""
        orch = RecoveryOrchestrator()
        recovery_fn = AsyncMock()
        orch.recovery.register_recovery("svc", recovery_fn)

        # 手动标记为故障
        for _ in range(5):
            orch.detector.record_failure("svc")
        assert orch.detector.is_faulty("svc")

        svc_fn = AsyncMock(return_value="ok")
        result = await orch.call("svc", svc_fn)

        assert result == "ok"
        recovery_fn.assert_called_once()
        assert not orch.detector.is_faulty("svc")

    async def test_already_faulty_recovery_fails_uses_fallback(self) -> None:
        """已故障且恢复失败，走降级。"""
        orch = RecoveryOrchestrator()
        orch.recovery.register_recovery(
            "svc", AsyncMock(side_effect=RuntimeError)
        )
        fallback_fn = AsyncMock(return_value="degraded")
        orch.fallback.register("svc", fallback_fn)

        for _ in range(5):
            orch.detector.record_failure("svc")

        svc_fn = AsyncMock(side_effect=RuntimeError("boom"))
        result = await orch.call("svc", svc_fn)

        assert result == "degraded"

    def test_register_service(self) -> None:
        """一次性注册恢复和降级。"""
        orch = RecoveryOrchestrator()
        rec_fn = AsyncMock()
        fb_fn = AsyncMock()

        orch.register_service("svc", rec_fn, fb_fn)

        assert orch.recovery.has_recovery("svc")
        assert orch.fallback.has_fallback("svc")


# =========================================================================
# 集成：完整链路
# =========================================================================


class TestRecoveryIntegration:
    """集成测试：完整恢复链路。"""

    async def test_full_recovery_chain(self) -> None:
        """完整链路：失败 → 检测 → 恢复 → 重试成功。"""
        orch = RecoveryOrchestrator(
            fault_detector=FaultDetector(threshold=2),
            auto_recovery=AutoRecovery(max_retries=2, base_delay=0.01),
        )

        recovery_called = False

        async def recovery_action() -> None:
            nonlocal recovery_called
            recovery_called = True

        async def fallback_action() -> dict:
            return {"fallback": True}

        orch.register_service("db", recovery_action, fallback_action)

        call_count = 0

        async def db_query() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("连接断开")
            return "数据"

        # 第一次调用：失败 (count=1)
        with pytest.raises(ConnectionError):
            await orch.call("db", db_query)

        # 第二次调用：失败触发恢复 (count=2 → faulty)
        result = await orch.call("db", db_query)
        assert result == "数据"
        assert recovery_called is True

    async def test_full_chain_with_fallback(self) -> None:
        """完整链路：失败 → 检测 → 恢复失败 → 降级。"""
        orch = RecoveryOrchestrator(
            fault_detector=FaultDetector(threshold=1),
            auto_recovery=AutoRecovery(max_retries=1, base_delay=0.01),
        )

        async def recovery_action() -> None:
            raise RuntimeError("恢复失败")

        async def fallback_action() -> dict:
            return {"data": "降级数据", "fallback": True}

        orch.register_service("llm", recovery_action, fallback_action)

        svc_fn = AsyncMock(side_effect=RuntimeError("LLM 超时"))
        result = await orch.call("llm", svc_fn)

        assert result["fallback"] is True
        assert result["data"] == "降级数据"
