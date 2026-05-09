"""CityFlow 连接池监控器测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.pool.monitor import (AlertSeverity, AlertThresholds, PoolAlert,
                                  PoolMonitor, reset_pool_monitor)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """每个测试后重置全局单例。"""
    yield
    reset_pool_monitor()


@pytest.fixture
def mock_db_pool():
    """模拟数据库连接池。"""
    pool = MagicMock()
    pool.get_pool_stats.return_value = {
        "pool_size": 10,
        "checkedin": 8,
        "checkedout": 2,
        "overflow": 0,
    }
    return pool


@pytest.fixture
def mock_http_pool():
    """模拟 HTTP 连接池。"""
    pool = MagicMock()
    pool.get_pool_stats.return_value = {
        "max_connections": 100,
        "active": 10,
        "keepalive": 5,
    }
    return pool


@pytest.fixture
def monitor(mock_db_pool, mock_http_pool):
    """创建监控器实例。"""
    return PoolMonitor(
        db_pool=mock_db_pool,
        http_pool=mock_http_pool,
    )


# ------------------------------------------------------------------
# 统计
# ------------------------------------------------------------------


class TestGetStats:
    """get_stats 测试。"""

    def test_returns_both_pools(self, monitor: PoolMonitor) -> None:
        stats = monitor.get_stats()
        assert "database" in stats
        assert "http" in stats
        assert stats["database"]["pool_size"] == 10
        assert stats["http"]["max_connections"] == 100

    def test_no_pools(self) -> None:
        monitor = PoolMonitor()
        stats = monitor.get_stats()
        assert stats == {}

    def test_db_pool_error(self, mock_http_pool) -> None:
        mock_db = MagicMock()
        mock_db.get_pool_stats.side_effect = RuntimeError("boom")
        monitor = PoolMonitor(db_pool=mock_db, http_pool=mock_http_pool)
        stats = monitor.get_stats()
        assert stats["database"] == {"error": "获取失败"}
        assert "http" in stats


# ------------------------------------------------------------------
# 告警
# ------------------------------------------------------------------


class TestCheckAlerts:
    """check_alerts 测试。"""

    def test_no_alerts_when_healthy(self, monitor: PoolMonitor) -> None:
        alerts = monitor.check_alerts()
        assert alerts == []

    def test_db_utilization_warning(self, mock_http_pool) -> None:
        mock_db = MagicMock()
        mock_db.get_pool_stats.return_value = {
            "pool_size": 10,
            "checkedin": 3,
            "checkedout": 7,
            "overflow": 0,
        }
        monitor = PoolMonitor(
            db_pool=mock_db,
            http_pool=mock_http_pool,
            thresholds=AlertThresholds(db_utilization_warn=0.5),
        )
        alerts = monitor.check_alerts()
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING
        assert alerts[0].pool_type == "database"

    def test_db_utilization_critical(self, mock_http_pool) -> None:
        mock_db = MagicMock()
        mock_db.get_pool_stats.return_value = {
            "pool_size": 10,
            "checkedin": 0,
            "checkedout": 10,
            "overflow": 0,
        }
        monitor = PoolMonitor(
            db_pool=mock_db,
            http_pool=mock_http_pool,
            thresholds=AlertThresholds(db_utilization_critical=0.8),
        )
        alerts = monitor.check_alerts()
        assert any(a.severity == AlertSeverity.CRITICAL for a in alerts)

    def test_http_utilization_warning(self, mock_db_pool) -> None:
        mock_http = MagicMock()
        mock_http.get_pool_stats.return_value = {
            "max_connections": 100,
            "active": 85,
            "keepalive": 5,
        }
        monitor = PoolMonitor(
            db_pool=mock_db_pool,
            http_pool=mock_http,
            thresholds=AlertThresholds(http_active_warn=0.8),
        )
        alerts = monitor.check_alerts()
        assert any(a.pool_type == "http" for a in alerts)


# ------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------


class TestCheckHealth:
    """check_health 测试。"""

    def test_healthy(self, monitor: PoolMonitor) -> None:
        report = monitor.check_health()
        assert report.healthy is True
        assert report.issues == []

    def test_unhealthy_db_critical_alert(self, mock_http_pool) -> None:
        mock_db = MagicMock()
        mock_db.get_pool_stats.return_value = {
            "pool_size": 10,
            "checkedin": 0,
            "checkedout": 15,
            "overflow": 5,
        }
        monitor = PoolMonitor(db_pool=mock_db, http_pool=mock_http_pool)
        report = monitor.check_health()
        # utilization = 15 / (10 + 5) = 100%, triggers critical alert
        assert report.healthy is False
        assert any("严重过高" in issue for issue in report.issues)

    def test_report_to_dict(self, monitor: PoolMonitor) -> None:
        report = monitor.check_health()
        d = report.to_dict()
        assert "healthy" in d
        assert "issues" in d
        assert "database" in d
        assert "http" in d
        assert "alerts" in d


# ------------------------------------------------------------------
# 历史
# ------------------------------------------------------------------


class TestHistory:
    """历史采集测试。"""

    def test_collect_and_get(self, monitor: PoolMonitor) -> None:
        monitor.collect_history()
        history = monitor.get_history(last_n=10)
        assert len(history) == 1
        assert "timestamp" in history[0]
        assert "db_utilization" in history[0]

    def test_history_max_size(self, monitor: PoolMonitor) -> None:
        monitor._history_max = 3
        for _ in range(5):
            monitor.collect_history()
        assert len(monitor._history) == 3

    def test_get_history_all(self, monitor: PoolMonitor) -> None:
        for _ in range(5):
            monitor.collect_history()
        history = monitor.get_history(last_n=0)
        assert len(history) == 5


# ------------------------------------------------------------------
# 仪表盘
# ------------------------------------------------------------------


class TestDashboard:
    """get_dashboard 测试。"""

    def test_dashboard_structure(self, monitor: PoolMonitor) -> None:
        dashboard = monitor.get_dashboard()
        assert "stats" in dashboard
        assert "alerts" in dashboard
        assert "health" in dashboard
        assert "history" in dashboard
        assert "thresholds" in dashboard
        assert "db_utilization_warn" in dashboard["thresholds"]


# ------------------------------------------------------------------
# 告警数据结构
# ------------------------------------------------------------------


class TestPoolAlert:
    """PoolAlert 测试。"""

    def test_to_dict(self) -> None:
        alert = PoolAlert(
            pool_type="database",
            message="test",
            severity=AlertSeverity.WARNING,
            metric_name="utilization",
            metric_value=0.85,
            threshold=0.8,
        )
        d = alert.to_dict()
        assert d["pool_type"] == "database"
        assert d["severity"] == "warning"
        assert d["metric_value"] == 0.85
