"""CityFlow 资源优化器。

实时采集 CPU、内存、磁盘使用指标，按阈值生成优化建议。
依赖 psutil 获取系统级资源数据。

使用方式：
    from backend.tools.resource_optimizer import ResourceOptimizer

    optimizer = ResourceOptimizer()
    report = optimizer.get_optimization_report()
    print(report.to_dict())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import psutil

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 枚举与数据结构
# ---------------------------------------------------------------------------


class ResourceType(StrEnum):
    """资源类型。"""

    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"


class Severity(StrEnum):
    """问题严重程度。"""

    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ResourceRecommendation:
    """单条资源优化建议。"""

    resource: ResourceType
    severity: Severity
    issue: str
    suggestion: str

    def to_dict(self) -> dict[str, str]:
        """转换为字典。"""
        return {
            "resource": self.resource.value,
            "severity": self.severity.value,
            "issue": self.issue,
            "suggestion": self.suggestion,
        }


@dataclass
class CpuReport:
    """CPU 分析结果。"""

    usage_percent: float
    cores: int
    recommendations: list[ResourceRecommendation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "usage_percent": self.usage_percent,
            "cores": self.cores,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


@dataclass
class MemoryReport:
    """内存分析结果。"""

    usage_percent: float
    total_bytes: int
    available_bytes: int
    recommendations: list[ResourceRecommendation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "usage_percent": self.usage_percent,
            "total_mb": round(self.total_bytes / (1024 * 1024), 1),
            "available_mb": round(self.available_bytes / (1024 * 1024), 1),
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


@dataclass
class DiskReport:
    """磁盘分析结果。"""

    usage_percent: float
    total_bytes: int
    free_bytes: int
    path: str
    recommendations: list[ResourceRecommendation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "usage_percent": self.usage_percent,
            "total_mb": round(self.total_bytes / (1024 * 1024), 1),
            "free_mb": round(self.free_bytes / (1024 * 1024), 1),
            "path": self.path,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


@dataclass
class OptimizationReport:
    """综合资源优化报告。"""

    cpu: CpuReport
    memory: MemoryReport
    disk: DiskReport
    total_recommendations: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu": self.cpu.to_dict(),
            "memory": self.memory.to_dict(),
            "disk": self.disk.to_dict(),
            "total_recommendations": self.total_recommendations,
        }


# ---------------------------------------------------------------------------
# 阈值常量
# ---------------------------------------------------------------------------

# CPU 使用率 (%)
_CPU_WARN_PCT = 70
_CPU_CRITICAL_PCT = 85

# 内存使用率 (%)
_MEMORY_WARN_PCT = 70
_MEMORY_CRITICAL_PCT = 85

# 磁盘使用率 (%)
_DISK_WARN_PCT = 70
_DISK_CRITICAL_PCT = 85


# ---------------------------------------------------------------------------
# 核心类
# ---------------------------------------------------------------------------


class ResourceOptimizer:
    """资源优化器。

    采集 CPU、内存、磁盘指标，与阈值比对后生成优化建议。

    用法::

        optimizer = ResourceOptimizer()
        report = optimizer.get_optimization_report()
        for rec in report.cpu.recommendations:
            print(rec.to_dict())
    """

    def analyze_cpu(self, interval: float = 1.0) -> CpuReport:
        """分析 CPU 使用情况。

        Args:
            interval: 采样间隔（秒），默认 1.0。

        Returns:
            CPU 分析报告。
        """
        usage = psutil.cpu_percent(interval=interval)
        cores = psutil.cpu_count(logical=True) or 1

        recommendations: list[ResourceRecommendation] = []

        if usage >= _CPU_CRITICAL_PCT:
            recommendations.append(
                ResourceRecommendation(
                    resource=ResourceType.CPU,
                    severity=Severity.CRITICAL,
                    issue=f"CPU 使用率过高: {usage:.1f}%",
                    suggestion=(
                        "优化计算密集型任务，使用异步处理；排查热点函数，考虑多进程并行"
                    ),
                )
            )
        elif usage >= _CPU_WARN_PCT:
            recommendations.append(
                ResourceRecommendation(
                    resource=ResourceType.CPU,
                    severity=Severity.WARNING,
                    issue=f"CPU 使用率偏高: {usage:.1f}%",
                    suggestion="关注 CPU 增长趋势，检查是否有异常进程",
                )
            )

        logger.debug("CPU 分析完成: %.1f%%, %d 核", usage, cores)
        return CpuReport(
            usage_percent=usage,
            cores=cores,
            recommendations=recommendations,
        )

    def analyze_memory(self) -> MemoryReport:
        """分析内存使用情况。

        Returns:
            内存分析报告。
        """
        mem = psutil.virtual_memory()

        recommendations: list[ResourceRecommendation] = []

        if mem.percent >= _MEMORY_CRITICAL_PCT:
            recommendations.append(
                ResourceRecommendation(
                    resource=ResourceType.MEMORY,
                    severity=Severity.CRITICAL,
                    issue=f"内存使用率过高: {mem.percent:.1f}%",
                    suggestion=(
                        "检查内存泄漏 (tracemalloc)；"
                        "限制 LRU 缓存 maxsize；"
                        "将大列表改为生成器处理"
                    ),
                )
            )
        elif mem.percent >= _MEMORY_WARN_PCT:
            recommendations.append(
                ResourceRecommendation(
                    resource=ResourceType.MEMORY,
                    severity=Severity.WARNING,
                    issue=f"内存使用率偏高: {mem.percent:.1f}%",
                    suggestion="监控内存增长趋势，考虑定期 gc.collect()",
                )
            )

        logger.debug("内存分析完成: %.1f%%", mem.percent)
        return MemoryReport(
            usage_percent=mem.percent,
            total_bytes=mem.total,
            available_bytes=mem.available,
            recommendations=recommendations,
        )

    def analyze_disk(self, path: str = "/") -> DiskReport:
        """分析磁盘使用情况。

        Args:
            path: 磁盘挂载路径，默认 '/'。
                  Windows 下会自动映射到当前盘符根目录。

        Returns:
            磁盘分析报告。
        """
        usage = psutil.disk_usage(path)

        recommendations: list[ResourceRecommendation] = []

        if usage.percent >= _DISK_CRITICAL_PCT:
            recommendations.append(
                ResourceRecommendation(
                    resource=ResourceType.DISK,
                    severity=Severity.CRITICAL,
                    issue=f"磁盘使用率过高: {usage.percent:.1f}%",
                    suggestion=(
                        "清理日志文件和临时文件；"
                        "压缩旧数据；"
                        "使用 ResourceCleaner 清理缓存"
                    ),
                )
            )
        elif usage.percent >= _DISK_WARN_PCT:
            recommendations.append(
                ResourceRecommendation(
                    resource=ResourceType.DISK,
                    severity=Severity.WARNING,
                    issue=f"磁盘使用率偏高: {usage.percent:.1f}%",
                    suggestion="定期清理日志和缓存，监控磁盘增长趋势",
                )
            )

        logger.debug("磁盘分析完成: %.1f%% (%s)", usage.percent, path)
        return DiskReport(
            usage_percent=usage.percent,
            total_bytes=usage.total,
            free_bytes=usage.free,
            path=path,
            recommendations=recommendations,
        )

    def get_optimization_report(
        self,
        cpu_interval: float = 1.0,
        disk_path: str = "/",
    ) -> OptimizationReport:
        """生成综合资源优化报告。

        Args:
            cpu_interval: CPU 采样间隔（秒）。
            disk_path: 磁盘挂载路径。

        Returns:
            包含 CPU、内存、磁盘分析及建议总数的报告。
        """
        cpu = self.analyze_cpu(interval=cpu_interval)
        memory = self.analyze_memory()
        disk = self.analyze_disk(path=disk_path)

        total = (
            len(cpu.recommendations)
            + len(memory.recommendations)
            + len(disk.recommendations)
        )

        logger.info(
            "资源分析完成: CPU %.1f%%, 内存 %.1f%%, 磁盘 %.1f%%, 建议 %d 条",
            cpu.usage_percent,
            memory.usage_percent,
            disk.usage_percent,
            total,
        )

        return OptimizationReport(
            cpu=cpu,
            memory=memory,
            disk=disk,
            total_recommendations=total,
        )
