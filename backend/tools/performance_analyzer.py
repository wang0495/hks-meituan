"""CityFlow 性能分析器。

对系统运行指标进行多维度分析，识别性能瓶颈并生成诊断报告。
分析维度包括：响应时间、内存使用、数据库查询、缓存命中率、错误率等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Impact(StrEnum):
    """瓶颈影响程度。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Bottleneck:
    """性能瓶颈。"""

    name: str
    description: str
    impact: Impact
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "name": self.name,
            "description": self.description,
            "impact": self.impact.value,
            "suggestion": self.suggestion,
        }


@dataclass
class AnalysisReport:
    """性能分析报告。"""

    bottlenecks: list[Bottleneck] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.bottlenecks)

    @property
    def high_impact_count(self) -> int:
        return sum(1 for b in self.bottlenecks if b.impact == Impact.HIGH)

    @property
    def has_critical_issues(self) -> bool:
        """是否存在高影响瓶颈。"""
        return self.high_impact_count > 0

    def to_dict(self) -> dict[str, Any]:
        """转换为 API 响应字典。"""
        return {
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "summary": {
                "total": self.total,
                "high_impact": self.high_impact_count,
                "medium_impact": sum(
                    1 for b in self.bottlenecks if b.impact == Impact.MEDIUM
                ),
                "low_impact": sum(
                    1 for b in self.bottlenecks if b.impact == Impact.LOW
                ),
            },
        }


# ---------------------------------------------------------------------------
# 阈值常量
# ---------------------------------------------------------------------------

# 响应时间 (ms)
_RESPONSE_TIME_WARN_MS = 500
_RESPONSE_TIME_CRITICAL_MS = 1000

# 内存使用率 (%)
_MEMORY_WARN_PCT = 70
_MEMORY_CRITICAL_PCT = 80

# 缓存命中率 (%)
_CACHE_HITRATE_WARN_PCT = 60
_CACHE_HITRATE_CRITICAL_PCT = 40

# 错误率 (%)
_ERROR_RATE_WARN_PCT = 1
_ERROR_RATE_CRITICAL_PCT = 5

# 数据库查询平均耗时 (ms)
_DB_QUERY_WARN_MS = 100
_DB_QUERY_CRITICAL_MS = 500


class PerformanceAnalyzer:
    """性能分析器。

    对各维度指标进行阈值检测，收集瓶颈并生成诊断报告。

    用法::

        analyzer = PerformanceAnalyzer()
        report = analyzer.analyze_all(metrics_dict)
        print(report.to_dict())
    """

    def __init__(self) -> None:
        self._bottlenecks: list[Bottleneck] = []

    # ------------------------------------------------------------------
    # 各维度分析
    # ------------------------------------------------------------------

    def analyze_response_times(self, metrics: dict[str, Any]) -> list[Bottleneck]:
        """分析响应时间指标。

        Args:
            metrics: 包含 avg_response_time (ms)、p95_response_time (ms) 等字段。

        Returns:
            检测到的瓶颈列表。
        """
        bottlenecks: list[Bottleneck] = []
        avg_time = metrics.get("avg_response_time", 0)
        p95_time = metrics.get("p95_response_time", 0)

        if avg_time > _RESPONSE_TIME_CRITICAL_MS:
            bottlenecks.append(
                Bottleneck(
                    name="高平均响应时间",
                    description=f"平均响应时间 {avg_time:.0f}ms 超过 {_RESPONSE_TIME_CRITICAL_MS}ms 阈值",
                    impact=Impact.HIGH,
                    suggestion="优化数据库查询、添加 Redis 缓存、检查 N+1 查询问题",
                )
            )
        elif avg_time > _RESPONSE_TIME_WARN_MS:
            bottlenecks.append(
                Bottleneck(
                    name="平均响应时间偏高",
                    description=f"平均响应时间 {avg_time:.0f}ms 超过 {_RESPONSE_TIME_WARN_MS}ms 预警线",
                    impact=Impact.MEDIUM,
                    suggestion="关注慢查询日志，考虑预加载热点数据",
                )
            )

        if p95_time > _RESPONSE_TIME_CRITICAL_MS * 2:
            bottlenecks.append(
                Bottleneck(
                    name="P95 尾部延迟过高",
                    description=f"P95 响应时间 {p95_time:.0f}ms，存在长尾请求",
                    impact=Impact.HIGH,
                    suggestion="排查慢请求路径，添加请求超时和熔断机制",
                )
            )

        return bottlenecks

    def analyze_memory_usage(self, metrics: dict[str, Any]) -> list[Bottleneck]:
        """分析内存使用率。

        Args:
            metrics: 包含 memory_usage (%) 字段。

        Returns:
            检测到的瓶颈列表。
        """
        bottlenecks: list[Bottleneck] = []
        memory_usage = metrics.get("memory_usage", 0)

        if memory_usage > _MEMORY_CRITICAL_PCT:
            bottlenecks.append(
                Bottleneck(
                    name="高内存使用",
                    description=f"内存使用率 {memory_usage:.1f}% 超过 {_MEMORY_CRITICAL_PCT}% 阈值",
                    impact=Impact.HIGH,
                    suggestion="检查内存泄漏、优化缓存 TTL、限制并发连接数",
                )
            )
        elif memory_usage > _MEMORY_WARN_PCT:
            bottlenecks.append(
                Bottleneck(
                    name="内存使用偏高",
                    description=f"内存使用率 {memory_usage:.1f}% 超过 {_MEMORY_WARN_PCT}% 预警线",
                    impact=Impact.MEDIUM,
                    suggestion="监控内存增长趋势，考虑设置缓存大小上限",
                )
            )

        return bottlenecks

    def analyze_cache_hitrate(self, metrics: dict[str, Any]) -> list[Bottleneck]:
        """分析缓存命中率。

        Args:
            metrics: 包含 cache_hitrate (%) 字段。

        Returns:
            检测到的瓶颈列表。
        """
        bottlenecks: list[Bottleneck] = []
        hitrate = metrics.get("cache_hitrate", 100)

        if hitrate < _CACHE_HITRATE_CRITICAL_PCT:
            bottlenecks.append(
                Bottleneck(
                    name="缓存命中率过低",
                    description=f"缓存命中率 {hitrate:.1f}% 低于 {_CACHE_HITRATE_CRITICAL_PCT}% 阈值",
                    impact=Impact.HIGH,
                    suggestion="检查缓存键设计、延长热点数据 TTL、启用缓存预热",
                )
            )
        elif hitrate < _CACHE_HITRATE_WARN_PCT:
            bottlenecks.append(
                Bottleneck(
                    name="缓存命中率偏低",
                    description=f"缓存命中率 {hitrate:.1f}% 低于 {_CACHE_HITRATE_WARN_PCT}% 预警线",
                    impact=Impact.MEDIUM,
                    suggestion="分析缓存失效模式，考虑调整缓存策略",
                )
            )

        return bottlenecks

    def analyze_error_rate(self, metrics: dict[str, Any]) -> list[Bottleneck]:
        """分析错误率。

        Args:
            metrics: 包含 error_rate (%) 和 total_requests 字段。

        Returns:
            检测到的瓶颈列表。
        """
        bottlenecks: list[Bottleneck] = []
        error_rate = metrics.get("error_rate", 0)
        total_requests = metrics.get("total_requests", 0)

        # 请求数过少时不做错误率判断
        if total_requests < 100:
            return bottlenecks

        if error_rate > _ERROR_RATE_CRITICAL_PCT:
            bottlenecks.append(
                Bottleneck(
                    name="错误率过高",
                    description=f"错误率 {error_rate:.1f}% 超过 {_ERROR_RATE_CRITICAL_PCT}% 阈值",
                    impact=Impact.HIGH,
                    suggestion="检查上游服务健康状态、排查异常日志、启用熔断降级",
                )
            )
        elif error_rate > _ERROR_RATE_WARN_PCT:
            bottlenecks.append(
                Bottleneck(
                    name="错误率偏高",
                    description=f"错误率 {error_rate:.1f}% 超过 {_ERROR_RATE_WARN_PCT}% 预警线",
                    impact=Impact.MEDIUM,
                    suggestion="排查高频错误类型，优化错误重试策略",
                )
            )

        return bottlenecks

    def analyze_db_queries(self, metrics: dict[str, Any]) -> list[Bottleneck]:
        """分析数据库查询性能。

        Args:
            metrics: 包含 avg_db_query_time (ms) 和 slow_query_count 字段。

        Returns:
            检测到的瓶颈列表。
        """
        bottlenecks: list[Bottleneck] = []
        avg_query_time = metrics.get("avg_db_query_time", 0)
        slow_queries = metrics.get("slow_query_count", 0)

        if avg_query_time > _DB_QUERY_CRITICAL_MS:
            bottlenecks.append(
                Bottleneck(
                    name="数据库查询过慢",
                    description=f"平均查询耗时 {avg_query_time:.0f}ms 超过 {_DB_QUERY_CRITICAL_MS}ms 阈值",
                    impact=Impact.HIGH,
                    suggestion="添加索引、优化 JOIN 查询、引入查询结果缓存",
                )
            )
        elif avg_query_time > _DB_QUERY_WARN_MS:
            bottlenecks.append(
                Bottleneck(
                    name="数据库查询偏慢",
                    description=f"平均查询耗时 {avg_query_time:.0f}ms 超过 {_DB_QUERY_WARN_MS}ms 预警线",
                    impact=Impact.MEDIUM,
                    suggestion="使用 EXPLAIN ANALYZE 排查慢查询，检查缺失索引",
                )
            )

        if slow_queries > 50:
            bottlenecks.append(
                Bottleneck(
                    name="慢查询数量过多",
                    description=f"检测到 {slow_queries} 条慢查询",
                    impact=Impact.HIGH,
                    suggestion="批量优化高频慢查询，考虑读写分离",
                )
            )

        return bottlenecks

    # ------------------------------------------------------------------
    # 汇总分析
    # ------------------------------------------------------------------

    def analyze_all(self, metrics: dict[str, Any]) -> AnalysisReport:
        """执行全部维度分析并返回汇总报告。

        Args:
            metrics: 包含各维度指标的字典。

        Returns:
            分析报告。
        """
        self._bottlenecks = []
        self._bottlenecks.extend(self.analyze_response_times(metrics))
        self._bottlenecks.extend(self.analyze_memory_usage(metrics))
        self._bottlenecks.extend(self.analyze_cache_hitrate(metrics))
        self._bottlenecks.extend(self.analyze_error_rate(metrics))
        self._bottlenecks.extend(self.analyze_db_queries(metrics))
        return AnalysisReport(bottlenecks=list(self._bottlenecks))

    def generate_report(self) -> dict[str, Any]:
        """生成报告字典（兼容旧接口）。

        Returns:
            包含瓶颈列表和摘要的字典。
        """
        return AnalysisReport(bottlenecks=list(self._bottlenecks)).to_dict()
