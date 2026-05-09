"""PerformanceAnalyzer 和 OptimizationAdvisor 单元测试。"""

from __future__ import annotations

import pytest

from backend.tools.optimization_advisor import OptimizationAdvisor, Priority
from backend.tools.performance_analyzer import (AnalysisReport, Bottleneck,
                                                Impact, PerformanceAnalyzer)

# =========================================================================
# PerformanceAnalyzer 测试
# =========================================================================


class TestPerformanceAnalyzer:
    """PerformanceAnalyzer 各维度分析测试。"""

    def setup_method(self) -> None:
        self.analyzer = PerformanceAnalyzer()

    # -- 响应时间 ----------------------------------------------------------

    def test_response_time_normal(self) -> None:
        metrics = {"avg_response_time": 100, "p95_response_time": 200}
        bottlenecks = self.analyzer.analyze_response_times(metrics)
        assert bottlenecks == []

    def test_response_time_warning(self) -> None:
        metrics = {"avg_response_time": 600, "p95_response_time": 800}
        bottlenecks = self.analyzer.analyze_response_times(metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.MEDIUM
        assert "偏高" in bottlenecks[0].name

    def test_response_time_critical(self) -> None:
        metrics = {"avg_response_time": 1500, "p95_response_time": 2500}
        bottlenecks = self.analyzer.analyze_response_times(metrics)
        assert len(bottlenecks) == 2  # avg + p95
        assert all(b.impact == Impact.HIGH for b in bottlenecks)

    def test_response_time_p95_tail_latency(self) -> None:
        metrics = {"avg_response_time": 200, "p95_response_time": 3000}
        bottlenecks = self.analyzer.analyze_response_times(metrics)
        assert len(bottlenecks) == 1
        assert "尾部延迟" in bottlenecks[0].name

    def test_response_time_missing_fields(self) -> None:
        bottlenecks = self.analyzer.analyze_response_times({})
        assert bottlenecks == []

    # -- 内存使用 ----------------------------------------------------------

    def test_memory_normal(self) -> None:
        bottlenecks = self.analyzer.analyze_memory_usage({"memory_usage": 50})
        assert bottlenecks == []

    def test_memory_warning(self) -> None:
        bottlenecks = self.analyzer.analyze_memory_usage({"memory_usage": 75})
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.MEDIUM

    def test_memory_critical(self) -> None:
        bottlenecks = self.analyzer.analyze_memory_usage({"memory_usage": 90})
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.HIGH

    # -- 缓存命中率 --------------------------------------------------------

    def test_cache_hitrate_normal(self) -> None:
        bottlenecks = self.analyzer.analyze_cache_hitrate({"cache_hitrate": 85})
        assert bottlenecks == []

    def test_cache_hitrate_warning(self) -> None:
        bottlenecks = self.analyzer.analyze_cache_hitrate({"cache_hitrate": 50})
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.MEDIUM

    def test_cache_hitrate_critical(self) -> None:
        bottlenecks = self.analyzer.analyze_cache_hitrate({"cache_hitrate": 30})
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.HIGH

    def test_cache_hitrate_default_100(self) -> None:
        """缺失字段默认 100%，不触发瓶颈。"""
        bottlenecks = self.analyzer.analyze_cache_hitrate({})
        assert bottlenecks == []

    # -- 错误率 ------------------------------------------------------------

    def test_error_rate_normal(self) -> None:
        metrics = {"error_rate": 0.5, "total_requests": 1000}
        bottlenecks = self.analyzer.analyze_error_rate(metrics)
        assert bottlenecks == []

    def test_error_rate_warning(self) -> None:
        metrics = {"error_rate": 3, "total_requests": 1000}
        bottlenecks = self.analyzer.analyze_error_rate(metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.MEDIUM

    def test_error_rate_critical(self) -> None:
        metrics = {"error_rate": 10, "total_requests": 1000}
        bottlenecks = self.analyzer.analyze_error_rate(metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.HIGH

    def test_error_rate_low_traffic_ignored(self) -> None:
        """请求数 < 100 时不判断错误率。"""
        metrics = {"error_rate": 50, "total_requests": 10}
        bottlenecks = self.analyzer.analyze_error_rate(metrics)
        assert bottlenecks == []

    # -- 数据库查询 --------------------------------------------------------

    def test_db_query_normal(self) -> None:
        metrics = {"avg_db_query_time": 50, "slow_query_count": 5}
        bottlenecks = self.analyzer.analyze_db_queries(metrics)
        assert bottlenecks == []

    def test_db_query_warning(self) -> None:
        metrics = {"avg_db_query_time": 200, "slow_query_count": 10}
        bottlenecks = self.analyzer.analyze_db_queries(metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].impact == Impact.MEDIUM

    def test_db_query_critical(self) -> None:
        metrics = {"avg_db_query_time": 600, "slow_query_count": 100}
        bottlenecks = self.analyzer.analyze_db_queries(metrics)
        assert len(bottlenecks) == 2  # avg_time + slow_query_count
        assert all(b.impact == Impact.HIGH for b in bottlenecks)

    def test_db_slow_query_count_only(self) -> None:
        metrics = {"avg_db_query_time": 50, "slow_query_count": 60}
        bottlenecks = self.analyzer.analyze_db_queries(metrics)
        assert len(bottlenecks) == 1
        assert "慢查询" in bottlenecks[0].name

    # -- 汇总分析 ----------------------------------------------------------

    def test_analyze_all_no_issues(self) -> None:
        metrics = {
            "avg_response_time": 100,
            "p95_response_time": 200,
            "memory_usage": 50,
            "cache_hitrate": 90,
            "error_rate": 0.5,
            "total_requests": 1000,
            "avg_db_query_time": 30,
            "slow_query_count": 0,
        }
        report = self.analyzer.analyze_all(metrics)
        assert report.total == 0
        assert report.has_critical_issues is False

    def test_analyze_all_multiple_issues(self) -> None:
        metrics = {
            "avg_response_time": 1500,
            "memory_usage": 90,
            "cache_hitrate": 30,
            "error_rate": 10,
            "total_requests": 1000,
            "avg_db_query_time": 600,
            "slow_query_count": 60,
        }
        report = self.analyzer.analyze_all(metrics)
        assert report.total > 5
        assert report.has_critical_issues is True
        assert report.high_impact_count > 0

    def test_analyze_all_returns_fresh_report(self) -> None:
        """两次调用不互相污染。"""
        self.analyzer.analyze_all({"avg_response_time": 1500})
        report = self.analyzer.analyze_all({})
        assert report.total == 0


# =========================================================================
# AnalysisReport 测试
# =========================================================================


class TestAnalysisReport:
    """AnalysisReport 数据结构测试。"""

    def test_empty_report(self) -> None:
        report = AnalysisReport()
        assert report.total == 0
        assert report.high_impact_count == 0
        assert report.has_critical_issues is False
        d = report.to_dict()
        assert d["summary"]["total"] == 0

    def test_report_with_bottlenecks(self) -> None:
        bottlenecks = [
            Bottleneck("A", "desc", Impact.HIGH, "fix"),
            Bottleneck("B", "desc", Impact.MEDIUM, "fix"),
            Bottleneck("C", "desc", Impact.LOW, "fix"),
        ]
        report = AnalysisReport(bottlenecks=bottlenecks)
        assert report.total == 3
        assert report.high_impact_count == 1
        assert report.has_critical_issues is True
        d = report.to_dict()
        assert d["summary"]["high_impact"] == 1
        assert d["summary"]["medium_impact"] == 1
        assert d["summary"]["low_impact"] == 1

    def test_bottleneck_to_dict(self) -> None:
        b = Bottleneck("test", "desc", Impact.HIGH, "fix")
        d = b.to_dict()
        assert d["name"] == "test"
        assert d["impact"] == "high"


# =========================================================================
# OptimizationAdvisor 测试
# =========================================================================


class TestOptimizationAdvisor:
    """OptimizationAdvisor 建议生成测试。"""

    def setup_method(self) -> None:
        self.advisor = OptimizationAdvisor()

    def test_empty_analysis(self) -> None:
        recs = self.advisor.get_recommendations({"bottlenecks": []})
        assert recs == []

    def test_single_bottleneck_recommendation(self) -> None:
        analysis = {
            "bottlenecks": [
                {"name": "高平均响应时间", "impact": "high", "suggestion": "fix"}
            ]
        }
        recs = self.advisor.get_recommendations(analysis)
        assert len(recs) == 1
        assert recs[0].priority == Priority.CRITICAL
        assert "EXPLAIN ANALYZE" in recs[0].action

    def test_sorted_by_priority(self) -> None:
        analysis = {
            "bottlenecks": [
                {"name": "内存使用偏高", "impact": "medium", "suggestion": "fix"},
                {"name": "高平均响应时间", "impact": "high", "suggestion": "fix"},
                {"name": "缓存命中率偏低", "impact": "low", "suggestion": "fix"},
            ]
        }
        recs = self.advisor.get_recommendations(analysis)
        assert recs[0].priority < recs[1].priority < recs[2].priority

    def test_unknown_bottleneck_fallback(self) -> None:
        """未知瓶颈回退到自带建议。"""
        analysis = {
            "bottlenecks": [
                {"name": "未知瓶颈", "impact": "high", "suggestion": "自定义建议"}
            ]
        }
        recs = self.advisor.get_recommendations(analysis)
        assert len(recs) == 1
        assert recs[0].action == "自定义建议"
        assert recs[0].expected_improvement == "显著提升"

    def test_get_top_n(self) -> None:
        analysis = {
            "bottlenecks": [
                {"name": "高平均响应时间", "impact": "high", "suggestion": ""},
                {"name": "高内存使用", "impact": "high", "suggestion": ""},
                {"name": "缓存命中率过低", "impact": "high", "suggestion": ""},
                {"name": "错误率偏高", "impact": "medium", "suggestion": ""},
            ]
        }
        top2 = self.advisor.get_top_n(analysis, n=2)
        assert len(top2) == 2
        assert all(r.priority == Priority.CRITICAL for r in top2)

    def test_get_summary(self) -> None:
        analysis = {
            "bottlenecks": [
                {"name": "高平均响应时间", "impact": "high", "suggestion": ""},
                {"name": "内存使用偏高", "impact": "medium", "suggestion": ""},
            ]
        }
        summary = self.advisor.get_summary(analysis)
        assert summary["total_recommendations"] == 2
        assert summary["critical"] == 1
        assert summary["medium"] == 1
        assert len(summary["top_actions"]) == 2

    def test_recommendation_to_dict(self) -> None:
        analysis = {
            "bottlenecks": [
                {"name": "高平均响应时间", "impact": "high", "suggestion": ""}
            ]
        }
        recs = self.advisor.get_recommendations(analysis)
        d = recs[0].to_dict()
        assert d["priority"] == 1
        assert d["priority_label"] == "critical"
        assert "area" in d
        assert "action" in d
        assert "tags" in d

    @pytest.mark.parametrize(
        "name,impact,expected_tags",
        [
            ("高平均响应时间", "high", ["database", "cache", "async"]),
            ("缓存命中率过低", "high", ["cache", "redis"]),
            ("数据库查询过慢", "high", ["database", "infrastructure"]),
        ],
    )
    def test_catalog_tags(
        self, name: str, impact: str, expected_tags: list[str]
    ) -> None:
        analysis = {"bottlenecks": [{"name": name, "impact": impact, "suggestion": ""}]}
        recs = self.advisor.get_recommendations(analysis)
        assert recs[0].tags == expected_tags


# =========================================================================
# 端到端集成测试
# =========================================================================


class TestAnalyzerAdvisorIntegration:
    """分析器 -> 建议器端到端测试。"""

    def test_full_pipeline(self) -> None:
        """模拟完整分析流程：指标 -> 瓶颈 -> 建议。"""
        metrics = {
            "avg_response_time": 1200,
            "p95_response_time": 3500,
            "memory_usage": 85,
            "cache_hitrate": 35,
            "error_rate": 8,
            "total_requests": 5000,
            "avg_db_query_time": 400,
            "slow_query_count": 70,
        }

        analyzer = PerformanceAnalyzer()
        report = analyzer.analyze_all(metrics)
        assert report.has_critical_issues

        advisor = OptimizationAdvisor()
        recommendations = advisor.get_recommendations(report.to_dict())
        assert len(recommendations) > 0
        assert recommendations[0].priority == Priority.CRITICAL

        summary = advisor.get_summary(report.to_dict())
        assert summary["critical"] > 0

    def test_healthy_system_no_recommendations(self) -> None:
        """健康系统不产生建议。"""
        metrics = {
            "avg_response_time": 50,
            "p95_response_time": 100,
            "memory_usage": 30,
            "cache_hitrate": 95,
            "error_rate": 0.1,
            "total_requests": 10000,
            "avg_db_query_time": 20,
            "slow_query_count": 0,
        }

        analyzer = PerformanceAnalyzer()
        report = analyzer.analyze_all(metrics)
        assert not report.has_critical_issues

        advisor = OptimizationAdvisor()
        recommendations = advisor.get_recommendations(report.to_dict())
        assert recommendations == []
