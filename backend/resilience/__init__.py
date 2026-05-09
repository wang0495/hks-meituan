"""CityFlow 自愈（Resilience）包。

提供故障检测、自动恢复和降级策略的统一入口。

快速开始：
    from backend.resilience import get_fault_detector, get_self_healing

    # 故障检测
    detector = get_fault_detector()
    detector.record_failure("llm")
    if detector.is_faulty("llm"):
        ...

    # 自愈管理
    healing = get_self_healing()
    healing.register_service(
        service="database",
        recovery=recover_database,
        degradation=degrade_database,
    )
    await healing.heal("database")

与 backend/services/ 中现有模块的关系：
    - circuit_breaker.py: 连续失败快速熔断（请求级）
    - retry.py: 指数退避重试（请求级）
    - fallback.py: 函数级降级装饰器
    - health_checker.py: 定期健康检查
    - auto_recovery.py: 单服务恢复执行

    本包是更上层的编排：
    - fault_detector: 滑动窗口故障频率检测（比熔断器更宽松）
    - self_healing: 编排检测 -> 恢复 -> 降级 -> 探测的完整闭环
"""

from __future__ import annotations

from backend.resilience.fault_detector import (FaultDetector, FaultEvent,
                                               FaultLevel, get_fault_detector)
from backend.resilience.self_healing import (DegradationLevel, HealingAttempt,
                                             HealingStatus, SelfHealing,
                                             degrade_database,
                                             degrade_llm_service,
                                             degrade_redis, get_self_healing)

__all__ = [
    # 故障检测
    "FaultDetector",
    "FaultEvent",
    "FaultLevel",
    "get_fault_detector",
    # 自愈管理
    "SelfHealing",
    "HealingStatus",
    "HealingAttempt",
    "DegradationLevel",
    "get_self_healing",
    # 预定义降级函数
    "degrade_database",
    "degrade_redis",
    "degrade_llm_service",
]
