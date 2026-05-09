"""CityFlow 优化建议生成器。

基于性能分析结果，按优先级生成可执行的优化建议。
涵盖：数据库优化、缓存策略、并发处理、资源管理、代码层面等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Priority(IntEnum):
    """优化优先级（数值越小越优先）。"""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Recommendation:
    """单条优化建议。"""

    priority: Priority
    area: str
    action: str
    expected_improvement: str
    effort: str = "medium"  # low / medium / high
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "priority": self.priority.value,
            "priority_label": self.priority.name.lower(),
            "area": self.area,
            "action": self.action,
            "expected_improvement": self.expected_improvement,
            "effort": self.effort,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# 预置优化方案库
# ---------------------------------------------------------------------------

_OPTIMIZATION_CATALOG: dict[str, dict[str, Any]] = {
    "高平均响应时间": {
        "action": "1) 用 EXPLAIN ANALYZE 排查慢查询并添加索引\n"
        "2) 对热点查询结果启用 Redis 缓存 (TTL 300s)\n"
        "3) 将同步 LLM 调用改为异步 + 连接池",
        "improvement": "响应时间降低 40-60%",
        "effort": "high",
        "tags": ["database", "cache", "async"],
    },
    "平均响应时间偏高": {
        "action": "1) 检查 N+1 查询，改用 selectinload / joinedload\n"
        "2) 对 POI 搜索启用内存缓存",
        "improvement": "响应时间降低 20-30%",
        "effort": "medium",
        "tags": ["database", "cache"],
    },
    "P95 尾部延迟过高": {
        "action": "1) 为外部 HTTP 调用设置 connect/read 超时\n"
        "2) 引入熔断器 (circuit_breaker) 快速失败\n"
        "3) 排查 GC 停顿或事件循环阻塞",
        "improvement": "P95 延迟降低 50%+",
        "effort": "medium",
        "tags": ["resilience", "async"],
    },
    "高内存使用": {
        "action": "1) 用 tracemalloc 定位内存热点\n"
        "2) 限制 LRU 缓存 maxsize\n"
        "3) 检查大对象是否被意外持有引用",
        "improvement": "内存使用降低 20-40%",
        "effort": "high",
        "tags": ["memory", "cache"],
    },
    "内存使用偏高": {
        "action": "1) 定期调用 gc.collect()\n" "2) 将大列表改为生成器处理",
        "improvement": "内存使用降低 10-20%",
        "effort": "low",
        "tags": ["memory"],
    },
    "缓存命中率过低": {
        "action": "1) 检查缓存键是否包含随机或时间戳字段\n"
        "2) 启动时预加载热点 POI 和路线数据\n"
        "3) 增大 maxmemory 配置",
        "improvement": "缓存命中率提升至 80%+",
        "effort": "medium",
        "tags": ["cache", "redis"],
    },
    "缓存命中率偏低": {
        "action": "1) 分析 Top-N 缓存 miss 的键\n" "2) 延长稳定数据的 TTL",
        "improvement": "缓存命中率提升 15-25%",
        "effort": "low",
        "tags": ["cache"],
    },
    "错误率过高": {
        "action": "1) 检查上游 LLM / 地图 API 健康状态\n"
        "2) 启用 fallback 降级策略\n"
        "3) 增加重试间隔 (指数退避)",
        "improvement": "错误率降低至 1% 以下",
        "effort": "high",
        "tags": ["resilience", "monitoring"],
    },
    "错误率偏高": {
        "action": "1) 按错误码分类排查高频错误\n" "2) 优化输入校验减少 4xx 错误",
        "improvement": "错误率降低 30-50%",
        "effort": "medium",
        "tags": ["resilience"],
    },
    "数据库查询过慢": {
        "action": "1) 添加缺失的数据库索引\n"
        "2) 将大事务拆分为小批次\n"
        "3) 考虑读写分离 (主从复制)",
        "improvement": "查询耗时降低 60-80%",
        "effort": "high",
        "tags": ["database", "infrastructure"],
    },
    "数据库查询偏慢": {
        "action": "1) 用 pg_stat_statements 找 Top 耗时查询\n" "2) 检查是否有全表扫描",
        "improvement": "查询耗时降低 20-40%",
        "effort": "medium",
        "tags": ["database"],
    },
    "慢查询数量过多": {
        "action": "1) 批量为高频慢查询添加复合索引\n"
        "2) 引入查询缓存层\n"
        "3) 评估是否需要分库分表",
        "improvement": "慢查询数量降低 70%+",
        "effort": "high",
        "tags": ["database", "cache"],
    },
}

# 影响等级 -> 优先级映射
_IMPACT_TO_PRIORITY: dict[str, Priority] = {
    "high": Priority.CRITICAL,
    "medium": Priority.MEDIUM,
    "low": Priority.LOW,
}

# 影响等级 -> 改进预期描述
_IMPACT_TO_IMPROVEMENT: dict[str, str] = {
    "high": "显著提升",
    "medium": "中等提升",
    "low": "轻微提升",
}


class OptimizationAdvisor:
    """优化建议生成器。

    根据性能分析器产出的瓶颈列表，匹配预置优化方案，
    按优先级排序后返回可执行的建议。

    用法::

        from backend.tools.performance_analyzer import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer()
        report = analyzer.analyze_all(metrics).to_dict()

        advisor = OptimizationAdvisor()
        recommendations = advisor.get_recommendations(report)
        for rec in recommendations:
            print(rec.to_dict())
    """

    def get_recommendations(self, analysis: dict[str, Any]) -> list[Recommendation]:
        """根据分析报告生成优化建议列表。

        Args:
            analysis: PerformanceAnalyzer.generate_report() 的输出。

        Returns:
            按优先级排序的建议列表。
        """
        recommendations: list[Recommendation] = []

        for bottleneck in analysis.get("bottlenecks", []):
            name = bottleneck["name"]
            impact = bottleneck["impact"]

            # 优先从预置方案库匹配
            catalog_entry = _OPTIMIZATION_CATALOG.get(name)
            if catalog_entry:
                rec = Recommendation(
                    priority=_IMPACT_TO_PRIORITY.get(impact, Priority.LOW),
                    area=name,
                    action=catalog_entry["action"],
                    expected_improvement=catalog_entry["improvement"],
                    effort=catalog_entry["effort"],
                    tags=list(catalog_entry["tags"]),
                )
            else:
                # 回退到瓶颈自带的建议
                rec = Recommendation(
                    priority=_IMPACT_TO_PRIORITY.get(impact, Priority.LOW),
                    area=name,
                    action=bottleneck.get("suggestion", "暂无具体建议"),
                    expected_improvement=_IMPACT_TO_IMPROVEMENT.get(impact, "未知"),
                )

            recommendations.append(rec)

        return sorted(recommendations, key=lambda r: r.priority)

    def get_top_n(self, analysis: dict[str, Any], n: int = 3) -> list[Recommendation]:
        """获取优先级最高的 N 条建议。

        Args:
            analysis: 性能分析报告。
            n: 返回建议数量，默认 3。

        Returns:
            优先级最高的 N 条建议。
        """
        return self.get_recommendations(analysis)[:n]

    def get_summary(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """生成优化建议摘要。

        Args:
            analysis: 性能分析报告。

        Returns:
            包含建议总数、各优先级数量、Top 建议的摘要。
        """
        recs = self.get_recommendations(analysis)
        return {
            "total_recommendations": len(recs),
            "critical": sum(1 for r in recs if r.priority == Priority.CRITICAL),
            "high": sum(1 for r in recs if r.priority == Priority.HIGH),
            "medium": sum(1 for r in recs if r.priority == Priority.MEDIUM),
            "low": sum(1 for r in recs if r.priority == Priority.LOW),
            "top_actions": [r.to_dict() for r in recs[:3]],
        }
