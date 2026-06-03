"""自适应限流器单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.adaptive_rate_limiter import (
    AdaptiveRateLimiter,
    LoadLevel,
    MetricsCollector,
    SystemMetrics,
    get_adaptive_limiter,
)


class TestSystemMetrics:
    def test_load_score_low(self) -> None:
        metrics = SystemMetrics(
            cpu_percent=10.0,
            memory_percent=20.0,
            avg_response_ms=100.0,
            error_rate=0.01,
        )
        score = metrics.load_score
        assert score < 40
        assert metrics.level == LoadLevel.LOW

    def test_load_score_normal(self) -> None:
        # score = 0.3*50 + 0.2*40 + 0.3*10 + 0.2*(500/1000*100) = 33 -> LOW
        # 加大参数: 0.3*80 + 0.2*70 + 0.3*15 + 0.2*60 = 24+14+4.5+12 = 54.5
        metrics = SystemMetrics(
            cpu_percent=80.0,
            memory_percent=70.0,
            avg_response_ms=600.0,
            error_rate=0.15,
        )
        score = metrics.load_score
        assert 30 <= score < 60
        assert metrics.level == LoadLevel.NORMAL

    def test_load_score_high(self) -> None:
        # 0.3*95 + 0.2*90 + 0.3*30 + 0.2*80 = 28.5+18+9+16 = 71.5
        metrics = SystemMetrics(
            cpu_percent=95.0,
            memory_percent=90.0,
            avg_response_ms=800.0,
            error_rate=0.30,
        )
        score = metrics.load_score
        assert 60 <= score < 85
        assert metrics.level == LoadLevel.HIGH

    def test_load_score_critical(self) -> None:
        # 0.3*99 + 0.2*99 + 0.3*60 + 0.2*100 = 29.7+19.8+18+20 = 87.5
        metrics = SystemMetrics(
            cpu_percent=99.0,
            memory_percent=99.0,
            avg_response_ms=2000.0,
            error_rate=0.60,
        )
        score = metrics.load_score
        assert score >= 85
        assert metrics.level == LoadLevel.CRITICAL

    def test_latency_factor_capped_at_1s(self) -> None:
        # 响应时间超过 1s 应该被封顶（latency_factor 最大 100）
        high_latency = SystemMetrics(avg_response_ms=5000.0)
        low_latency = SystemMetrics(avg_response_ms=500.0)
        # 5000ms 和 2000ms 的 latency_factor 都是 100（封顶）
        assert high_latency.load_score == SystemMetrics(avg_response_ms=2000.0).load_score
        # 500ms 的 latency_factor 是 50
        assert low_latency.load_score < high_latency.load_score

    def test_zero_metrics(self) -> None:
        metrics = SystemMetrics()
        assert metrics.load_score == 0.0
        assert metrics.level == LoadLevel.LOW


class TestMetricsCollector:
    def test_collect_returns_metrics(self) -> None:
        collector = MetricsCollector()
        metrics = collector.collect()
        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0

    def test_record_response_tracks_latency(self) -> None:
        collector = MetricsCollector()
        collector.record_response(100.0, is_error=False)
        collector.record_response(200.0, is_error=False)

        metrics = collector.collect()
        assert metrics.avg_response_ms == 150.0

    def test_record_response_tracks_errors(self) -> None:
        collector = MetricsCollector()
        collector.record_response(100.0, is_error=False)
        collector.record_response(100.0, is_error=True)

        metrics = collector.collect()
        assert metrics.error_rate == 0.5

    def test_reset_clears_state(self) -> None:
        collector = MetricsCollector()
        collector.record_response(500.0, is_error=True)
        collector.reset()

        metrics = collector.collect()
        assert metrics.avg_response_ms == 0.0
        assert metrics.error_rate == 0.0

    def test_sliding_window_limit(self) -> None:
        collector = MetricsCollector()
        # 添加超过 max_window 的记录
        for i in range(1100):
            collector.record_response(float(i), is_error=False)

        # 只保留最后 1000 条
        assert len(collector._response_times) == 1000


class TestAdaptiveRateLimiter:
    def test_default_multiplier_is_one(self) -> None:
        limiter = AdaptiveRateLimiter()
        assert limiter.get_multiplier() == 1.0

    def test_manual_multiplier_override(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.set_manual_multiplier(2.5)
        assert limiter.get_multiplier() == 2.5

        limiter.set_manual_multiplier(None)
        assert limiter.get_multiplier() == 1.0

    def test_force_update_changes_multiplier_for_high_load(self) -> None:
        limiter = AdaptiveRateLimiter()
        # 手动注入高负载指标（score ~71.5 -> HIGH）
        limiter._current_metrics = SystemMetrics(
            cpu_percent=95.0,
            memory_percent=90.0,
            avg_response_ms=800.0,
            error_rate=0.30,
        )
        # 直接调用 _update_multiplier，因为 force_update 会用 collector 覆盖
        limiter._update_multiplier()
        # 高负载应该收紧倍率（HIGH -> 0.5）
        assert limiter.get_multiplier() < 1.0

    def test_force_update_increases_multiplier_for_low_load(self) -> None:
        limiter = AdaptiveRateLimiter()
        # 先设置低倍率
        limiter._current_multiplier = 0.5
        # 注入低负载指标
        limiter._current_metrics = SystemMetrics(
            cpu_percent=5.0,
            memory_percent=10.0,
            avg_response_ms=50.0,
            error_rate=0.0,
        )
        # 多次 force_update 让渐进恢复生效
        for _ in range(50):
            limiter.force_update()

        # 低负载应该放宽倍率（渐进恢复）
        assert limiter.get_multiplier() > 0.5

    def test_multiplier_clamped_to_range(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.set_manual_multiplier(10.0)
        # set_manual_multiplier 不做限制，但 get_multiplier 不应超出范围
        # （手动模式下不做限制，自动模式下有限制）
        limiter.set_manual_multiplier(None)

        # 极端低负载多次 force_update
        limiter._current_metrics = SystemMetrics()
        for _ in range(200):
            limiter.force_update()
        assert limiter.get_multiplier() <= 3.0

    def test_record_response_updates_metrics(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.record_response(50.0, is_error=False)
        limiter.record_response(100.0, is_error=True)
        limiter.record_response(200.0, is_error=False)

        metrics = limiter.force_update()
        assert metrics.avg_response_ms > 0
        assert metrics.error_rate > 0

    def test_get_status_returns_dict(self) -> None:
        limiter = AdaptiveRateLimiter()
        status = limiter.get_status()

        assert "load_level" in status
        assert "load_score" in status
        assert "multiplier" in status
        assert "mode" in status
        assert "metrics" in status
        assert "thresholds" in status
        assert status["mode"] == "auto"

    def test_get_status_manual_mode(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.set_manual_multiplier(0.3)
        status = limiter.get_status()
        assert status["mode"] == "manual"

    @pytest.mark.asyncio
    async def test_start_and_stop_monitoring(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter._monitor_interval = 0.1  # 加快测试

        await limiter.start_monitoring()
        assert limiter._monitor_task is not None

        await asyncio.sleep(0.3)
        await limiter.stop_monitoring()
        assert limiter._monitor_task is None

    @pytest.mark.asyncio
    async def test_start_monitoring_idempotent(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter._monitor_interval = 0.1

        await limiter.start_monitoring()
        task1 = limiter._monitor_task
        await limiter.start_monitoring()  # 第二次不应创建新任务
        task2 = limiter._monitor_task
        assert task1 is task2

        await limiter.stop_monitoring()

    def test_load_level_property(self) -> None:
        limiter = AdaptiveRateLimiter()
        # 默认零负载 -> LOW
        assert limiter.load_level == LoadLevel.LOW

        # 0.3*99 + 0.2*99 + 0.3*60 + 0.2*100 = 87.5 -> CRITICAL
        limiter._current_metrics = SystemMetrics(
            cpu_percent=99.0,
            memory_percent=99.0,
            avg_response_ms=2000.0,
            error_rate=0.60,
        )
        assert limiter.load_level == LoadLevel.CRITICAL


class TestGetAdaptiveLimiter:
    def test_singleton(self) -> None:
        # 清除全局单例
        import backend.services.adaptive_rate_limiter as mod

        mod._adaptive = None

        limiter1 = get_adaptive_limiter()
        limiter2 = get_adaptive_limiter()
        assert limiter1 is limiter2

        # 恢复
        mod._adaptive = None
