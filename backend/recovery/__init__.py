"""CityFlow 恢复机制模块。

提供故障检测、自动恢复和降级策略三大核心能力，
以及将三者串联的恢复编排器。
"""

from backend.recovery.auto_recovery import AutoRecovery
from backend.recovery.fallback import FallbackStrategy
from backend.recovery.fault_detector import FaultDetector
from backend.recovery.orchestrator import RecoveryOrchestrator

__all__ = [
    "FaultDetector",
    "AutoRecovery",
    "FallbackStrategy",
    "RecoveryOrchestrator",
]
