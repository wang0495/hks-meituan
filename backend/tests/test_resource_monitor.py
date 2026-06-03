"""资源监控器单元测试。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import patch

import pytest

from backend.services.resource_monitor import (
    AlertEvent,
    AlertRule,
    AlertSeverity,
    ResourceMetrics,
    ResourceMonitor,
    collect_metrics,
    get_resource_monitor,
    reset_resource_monitor,
)

# ---------------------------------------------------------------------------
# 数据结构测试
# ---------------------------------------------------------------------------


class TestResourceMetrics:
    def test_to_dict_rounds_values(self) -> None:
        m = ResourceMetrics(
            cpu_percent=55.123,
            memory_percent=60.0,
            memory_used_mb=4096.789,
            memory_total_mb=8192.0,
            disk_percent=45.5,
            disk_used_gb=120.456,
            disk_total_gb=500.0,
            net_bytes_sent=1024,
            net_bytes_recv=2048,
        )
        d = m.to_dict()
        assert d["memory_used_mb"] == 4096.8
        assert d["disk_used_gb"] == 120.46
        assert d["cpu_percent"] == 55.123

    def test_to_dict_has_timestamp(self) -> None:
        m = ResourceMetrics(
            cpu_percent=0,
            memory_percent=0,
            memory_used_mb=0,
            memory_total_mb=0,
            disk_percent=0,
            disk_used_gb=0,
            disk_total_gb=0,
            net_bytes_sent=0,
            net_bytes_recv=0,
        )
        d = m.to_dict()
        assert "timestamp" in d
        # isoformat 字符串
        datetime.fromisoformat(d["timestamp"])


class TestAlertEvent:
    def test_to_dict(self) -> None:
        event = AlertEvent(
            rule_name="high_cpu",
            metric="cpu_percent",
            current_value=90.0,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            message="test message",
        )
        d = event.to_dict()
        assert d["rule_name"] == "high_cpu"
        assert d["current_value"] == 90.0
        assert d["severity"] == AlertSeverity.WARNING


# ---------------------------------------------------------------------------
# 比较运算符测试
# ---------------------------------------------------------------------------


class TestComparisonOperator:
    @pytest.mark.parametrize(
        ("op", "a", "b", "expected"),
        [
            (">", 10.0, 5.0, True),
            (">", 5.0, 10.0, False),
            (">=", 10.0, 10.0, True),
            (">=", 9.0, 10.0, False),
            ("<", 5.0, 10.0, True),
            ("<", 10.0, 5.0, False),
            ("<=", 10.0, 10.0, True),
            ("<=", 11.0, 10.0, False),
            ("==", 5.0, 5.0, True),
            ("==", 5.0, 6.0, False),
            ("!=", 5.0, 6.0, True),
            ("!=", 5.0, 5.0, False),
        ],
    )
    def test_comparison_operators(self, op: str, a: float, b: float, expected: bool) -> None:
        rule = AlertRule(name="test", metric="x", threshold=b, operator=op)
        from backend.services.resource_monitor import _COMPARISON_TABLE

        compare = _COMPARISON_TABLE[rule.operator]
        assert compare(a, b) is expected


# ---------------------------------------------------------------------------
# collect_metrics 测试
# ---------------------------------------------------------------------------


class TestCollectMetrics:
    @patch("backend.services.resource_monitor.psutil")
    def test_collect_returns_resource_metrics(self, mock_psutil: object) -> None:
        # mock psutil 返回值

        mock_mem = type("Mem", (), {"percent": 45.0, "used": 4 * 1024**3, "total": 8 * 1024**3})()
        mock_disk = type(
            "Disk", (), {"percent": 60.0, "used": 300 * 1024**3, "total": 500 * 1024**3}
        )()
        mock_net = type(
            "Net",
            (),
            {
                "bytes_sent": 1000,
                "bytes_recv": 2000,
                "_asdict": lambda self: {"bytes_sent": 1000, "bytes_recv": 2000},
            },
        )()

        mock_psutil.cpu_percent.return_value = 25.0
        mock_psutil.virtual_memory.return_value = mock_mem
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.net_io_counters.return_value = mock_net

        from backend.services.resource_monitor import collect_metrics

        metrics = collect_metrics()
        assert metrics.cpu_percent == 25.0
        assert metrics.memory_percent == 45.0
        assert metrics.disk_percent == 60.0


# ---------------------------------------------------------------------------
# ResourceMonitor 测试
# ---------------------------------------------------------------------------


class TestResourceMonitor:
    def setup_method(self) -> None:
        self.monitor = ResourceMonitor()

    def test_add_rule(self) -> None:
        rule = AlertRule(name="test", metric="cpu_percent", threshold=80.0)
        self.monitor.add_rule(rule)
        assert len(self.monitor.get_rules()) == 1
        assert self.monitor.get_rules()[0].name == "test"

    def test_add_rule_overwrites_same_name(self) -> None:
        rule1 = AlertRule(name="test", metric="cpu_percent", threshold=80.0)
        rule2 = AlertRule(name="test", metric="cpu_percent", threshold=90.0)
        self.monitor.add_rule(rule1)
        self.monitor.add_rule(rule2)
        assert len(self.monitor.get_rules()) == 1
        assert self.monitor.get_rules()[0].threshold == 90.0

    def test_remove_rule(self) -> None:
        rule = AlertRule(name="test", metric="cpu_percent", threshold=80.0)
        self.monitor.add_rule(rule)
        assert self.monitor.remove_rule("test") is True
        assert len(self.monitor.get_rules()) == 0

    def test_remove_nonexistent_rule(self) -> None:
        assert self.monitor.remove_rule("nonexistent") is False

    def test_add_callback(self) -> None:
        async def my_callback(event: AlertEvent) -> None:
            pass

        self.monitor.add_callback(my_callback)
        assert self.monitor._callbacks == [my_callback]

    def test_initial_state(self) -> None:
        assert self.monitor.is_running is False
        assert self.monitor.latest_metrics is None
        assert self.monitor.get_rules() == []

    def test_get_status(self) -> None:
        status = self.monitor.get_status()
        assert status["running"] is False
        assert status["rules_count"] == 0
        assert status["callbacks_count"] == 0
        assert status["latest_metrics"] is None


class TestResourceMonitorEvaluateRules:
    """测试告警规则评估逻辑。"""

    def setup_method(self) -> None:
        self.monitor = ResourceMonitor()
        self.triggered_events: list[AlertEvent] = []

    async def _record_callback(self, event: AlertEvent) -> None:
        self.triggered_events.append(event)

    @pytest.mark.asyncio
    async def test_rule_triggers_when_threshold_exceeded(self) -> None:
        rule = AlertRule(name="high_cpu", metric="cpu_percent", threshold=80.0, operator=">")
        self.monitor.add_rule(rule)
        self.monitor.add_callback(self._record_callback)

        metrics = ResourceMetrics(
            cpu_percent=90.0,
            memory_percent=50.0,
            memory_used_mb=4096,
            memory_total_mb=8192,
            disk_percent=40.0,
            disk_used_gb=200,
            disk_total_gb=500,
            net_bytes_sent=1000,
            net_bytes_recv=2000,
        )
        await self.monitor._evaluate_rules(metrics)

        assert len(self.triggered_events) == 1
        assert self.triggered_events[0].rule_name == "high_cpu"
        assert self.triggered_events[0].current_value == 90.0

    @pytest.mark.asyncio
    async def test_rule_does_not_trigger_below_threshold(self) -> None:
        rule = AlertRule(name="high_cpu", metric="cpu_percent", threshold=80.0, operator=">")
        self.monitor.add_rule(rule)
        self.monitor.add_callback(self._record_callback)

        metrics = ResourceMetrics(
            cpu_percent=70.0,
            memory_percent=50.0,
            memory_used_mb=4096,
            memory_total_mb=8192,
            disk_percent=40.0,
            disk_used_gb=200,
            disk_total_gb=500,
            net_bytes_sent=1000,
            net_bytes_recv=2000,
        )
        await self.monitor._evaluate_rules(metrics)

        assert len(self.triggered_events) == 0

    @pytest.mark.asyncio
    async def test_cooldown_prevents_duplicate_alerts(self) -> None:
        rule = AlertRule(
            name="high_cpu",
            metric="cpu_percent",
            threshold=80.0,
            operator=">",
            cooldown_seconds=300.0,
        )
        self.monitor.add_rule(rule)
        self.monitor.add_callback(self._record_callback)

        metrics = ResourceMetrics(
            cpu_percent=90.0,
            memory_percent=50.0,
            memory_used_mb=4096,
            memory_total_mb=8192,
            disk_percent=40.0,
            disk_used_gb=200,
            disk_total_gb=500,
            net_bytes_sent=1000,
            net_bytes_recv=2000,
        )

        # 第一次触发
        await self.monitor._evaluate_rules(metrics)
        assert len(self.triggered_events) == 1

        # 第二次在冷却期内，不应触发
        await self.monitor._evaluate_rules(metrics)
        assert len(self.triggered_events) == 1

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_block_others(self) -> None:
        """单个回调异常不应阻止其他回调执行。"""
        captured: list[AlertEvent] = []

        async def failing_callback(event: AlertEvent) -> None:
            raise RuntimeError("callback failed")

        async def ok_callback(event: AlertEvent) -> None:
            captured.append(event)

        self.monitor.add_callback(failing_callback)
        self.monitor.add_callback(ok_callback)

        rule = AlertRule(name="high_cpu", metric="cpu_percent", threshold=80.0, operator=">")
        self.monitor.add_rule(rule)

        metrics = ResourceMetrics(
            cpu_percent=90.0,
            memory_percent=50.0,
            memory_used_mb=4096,
            memory_total_mb=8192,
            disk_percent=40.0,
            disk_used_gb=200,
            disk_total_gb=500,
            net_bytes_sent=1000,
            net_bytes_recv=2000,
        )
        await self.monitor._evaluate_rules(metrics)

        # ok_callback 仍然被执行
        assert len(captured) == 1

    @pytest.mark.asyncio
    async def test_multiple_rules_evaluate_independently(self) -> None:
        rule_cpu = AlertRule(name="high_cpu", metric="cpu_percent", threshold=80.0)
        rule_mem = AlertRule(name="high_mem", metric="memory_percent", threshold=85.0)
        self.monitor.add_rule(rule_cpu)
        self.monitor.add_rule(rule_mem)
        self.monitor.add_callback(self._record_callback)

        metrics = ResourceMetrics(
            cpu_percent=90.0,
            memory_percent=90.0,
            memory_used_mb=7000,
            memory_total_mb=8192,
            disk_percent=40.0,
            disk_used_gb=200,
            disk_total_gb=500,
            net_bytes_sent=1000,
            net_bytes_recv=2000,
        )
        await self.monitor._evaluate_rules(metrics)

        assert len(self.triggered_events) == 2
        names = {e.rule_name for e in self.triggered_events}
        assert names == {"high_cpu", "high_mem"}


class TestResourceMonitorStartStop:
    """测试启动和停止监控循环。"""

    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        monitor = ResourceMonitor()
        collected: list[ResourceMetrics] = []

        original_collect = collect_metrics

        def mock_collect(disk_path: str = "/") -> ResourceMetrics:
            m = original_collect(disk_path)
            collected.append(m)
            return m

        with patch(
            "backend.services.resource_monitor.collect_metrics",
            side_effect=mock_collect,
        ):
            await monitor.start_monitoring(interval=1)
            assert monitor.is_running is True

            # 等待至少一次采集
            await asyncio.sleep(1.5)
            assert len(collected) >= 1

            await monitor.stop_monitoring()
            assert monitor.is_running is False

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self) -> None:
        monitor = ResourceMonitor()
        await monitor.start_monitoring(interval=60)
        assert monitor.is_running is True

        # 再次调用不应创建新任务
        await monitor.start_monitoring(interval=60)
        assert monitor._task is not None

        await monitor.stop_monitoring()


# ---------------------------------------------------------------------------
# 预定义规则测试
# ---------------------------------------------------------------------------


class TestDefaultRules:
    def test_default_rules_loaded(self) -> None:
        reset_resource_monitor()
        try:
            monitor = get_resource_monitor()
            rules = monitor.get_rules()
            names = {r.name for r in rules}
            assert "high_cpu" in names
            assert "high_memory" in names
            assert "high_disk" in names
            assert "critical_cpu" in names
            assert "critical_memory" in names
            assert "critical_disk" in names
        finally:
            reset_resource_monitor()

    def test_singleton_returns_same_instance(self) -> None:
        reset_resource_monitor()
        try:
            m1 = get_resource_monitor()
            m2 = get_resource_monitor()
            assert m1 is m2
        finally:
            reset_resource_monitor()

    def test_reset_creates_new_instance(self) -> None:
        reset_resource_monitor()
        try:
            m1 = get_resource_monitor()
            reset_resource_monitor()
            m2 = get_resource_monitor()
            assert m1 is not m2
        finally:
            reset_resource_monitor()
