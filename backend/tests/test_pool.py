"""连接池管理单元测试。

覆盖：
- DatabasePool 生命周期与统计
- HTTPPool 生命周期与统计
- PoolMonitor 健康检查与报告
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.database.pool import DatabasePool, PoolStats
from backend.services.http_pool import HTTPPool, HTTPPoolStats
from backend.services.pool_monitor import PoolMonitor

# ---------------------------------------------------------------------------
# PoolStats
# ---------------------------------------------------------------------------


class TestPoolStats:
    def test_utilization_normal(self) -> None:
        stats = PoolStats(pool_size=5, checked_in=2, checked_out=3, overflow=0)
        assert stats.utilization == pytest.approx(0.6)

    def test_utilization_zero_pool(self) -> None:
        stats = PoolStats(pool_size=0, checked_in=0, checked_out=0, overflow=0)
        assert stats.utilization == 0.0

    def test_utilization_full(self) -> None:
        stats = PoolStats(pool_size=5, checked_in=0, checked_out=5, overflow=0)
        assert stats.utilization == pytest.approx(1.0)

    def test_utilization_with_overflow(self) -> None:
        stats = PoolStats(pool_size=5, checked_in=0, checked_out=12, overflow=3)
        assert stats.utilization == pytest.approx(12 / 8)


# ---------------------------------------------------------------------------
# DatabasePool
# ---------------------------------------------------------------------------


class TestDatabasePool:
    @pytest.fixture()
    def pool(self) -> DatabasePool:
        return DatabasePool(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            pool_size=3,
            max_overflow=5,
            pool_recycle=1800,
        )

    def test_initial_state(self, pool: DatabasePool) -> None:
        assert pool._started is False

    async def test_start_idempotent(self, pool: DatabasePool) -> None:
        with patch("backend.database.pool.create_async_engine") as mock_engine:
            mock_engine.return_value = MagicMock()
            await pool.start()
            assert pool._started is True
            await pool.start()  # second call should be no-op
            assert mock_engine.call_count == 1

    async def test_close_without_start(self, pool: DatabasePool) -> None:
        # should not raise
        await pool.close()
        assert pool._started is False

    async def test_close_disposes_engine(self, pool: DatabasePool) -> None:
        with patch("backend.database.pool.create_async_engine") as mock_engine:
            mock_engine.return_value = AsyncMock()
            await pool.start()
            await pool.close()
            pool.engine.dispose.assert_awaited_once()  # type: ignore[union-attr]
            assert pool._started is False

    async def test_get_session_yields_session(self, pool: DatabasePool) -> None:
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.database.pool.create_async_engine"):
            await pool.start()
            pool.session_factory = mock_factory

            async for session in pool.get_session():
                assert session is mock_session

            mock_session.commit.assert_awaited_once()

    async def test_get_session_rollback_on_error(self, pool: DatabasePool) -> None:
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.database.pool.create_async_engine"):
            await pool.start()
            pool.session_factory = mock_factory

            gen = pool.get_session()
            session = await gen.__anext__()
            assert session is mock_session

            with pytest.raises(RuntimeError):
                await gen.athrow(RuntimeError("boom"))

            mock_session.rollback.assert_awaited_once()

    async def test_ping_success(self, pool: DatabasePool) -> None:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch("backend.database.pool.create_async_engine"):
            await pool.start()
            pool.engine = mock_engine

            result = await pool.ping()
            assert result is True

    async def test_ping_failure(self, pool: DatabasePool) -> None:
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = ConnectionError("db down")

        with patch("backend.database.pool.create_async_engine"):
            await pool.start()
            pool.engine = mock_engine

            result = await pool.ping()
            assert result is False

    async def test_ping_before_start(self, pool: DatabasePool) -> None:
        result = await pool.ping()
        assert result is False

    def test_get_stats(self, pool: DatabasePool) -> None:
        mock_pool = MagicMock()
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 3
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0

        mock_engine = MagicMock()
        mock_engine.pool = mock_pool
        pool.engine = mock_engine
        pool._started = True

        stats = pool.get_stats()
        assert stats.pool_size == 5
        assert stats.checked_in == 3
        assert stats.checked_out == 2
        assert stats.overflow == 0

    def test_get_stats_dict(self, pool: DatabasePool) -> None:
        mock_pool = MagicMock()
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 3
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0

        mock_engine = MagicMock()
        mock_engine.pool = mock_pool
        pool.engine = mock_engine
        pool._started = True

        d = pool.get_stats_dict()
        assert d["pool_size"] == 5
        assert d["utilization"] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# HTTPPoolStats
# ---------------------------------------------------------------------------


class TestHTTPPoolStats:
    def test_create(self) -> None:
        stats = HTTPPoolStats(max_connections=10, max_keepalive_connections=5)
        assert stats.max_connections == 10
        assert stats.max_keepalive_connections == 5


# ---------------------------------------------------------------------------
# HTTPPool
# ---------------------------------------------------------------------------


class TestHTTPPool:
    @pytest.fixture()
    def pool(self) -> HTTPPool:
        return HTTPPool(max_connections=10, max_keepalive_connections=5, timeout=15.0)

    def test_initial_state(self, pool: HTTPPool) -> None:
        assert pool._started is False

    async def test_start_creates_client(self, pool: HTTPPool) -> None:
        await pool.start()
        assert pool._started is True
        assert pool._client is not None

    async def test_start_idempotent(self, pool: HTTPPool) -> None:
        await pool.start()
        client1 = pool._client
        await pool.start()
        assert pool._client is client1

    async def test_close(self, pool: HTTPPool) -> None:
        await pool.start()
        assert pool._client is not None
        await pool.close()
        assert pool._started is False

    async def test_close_without_start(self, pool: HTTPPool) -> None:
        await pool.close()  # should not raise
        assert pool._started is False

    async def test_get_stats(self, pool: HTTPPool) -> None:
        stats = pool.get_stats()
        assert stats.max_connections == 10
        assert stats.max_keepalive_connections == 5

    async def test_get_stats_dict_closed(self, pool: HTTPPool) -> None:
        d = pool.get_stats_dict()
        assert d["is_closed"] is True

    async def test_get_stats_dict_started(self, pool: HTTPPool) -> None:
        await pool.start()
        d = pool.get_stats_dict()
        assert d["is_closed"] is False

    async def test_http_methods_delegate_to_client(self, pool: HTTPPool) -> None:
        """各 HTTP 方法应正确委托给底层 client。"""
        await pool.start()

        mock_response = MagicMock()
        with patch.object(
            pool._client, "get", new_callable=AsyncMock, return_value=mock_response
        ) as m:
            result = await pool.get("http://example.com")
            m.assert_awaited_once_with("http://example.com")
            assert result is mock_response

        with patch.object(
            pool._client, "post", new_callable=AsyncMock, return_value=mock_response
        ) as m:
            result = await pool.post("http://example.com", json={"a": 1})
            m.assert_awaited_once_with("http://example.com", json={"a": 1})

        with patch.object(
            pool._client, "put", new_callable=AsyncMock, return_value=mock_response
        ) as m:
            result = await pool.put("http://example.com")
            m.assert_awaited_once_with("http://example.com")

        with patch.object(
            pool._client, "patch", new_callable=AsyncMock, return_value=mock_response
        ) as m:
            result = await pool.patch("http://example.com")
            m.assert_awaited_once_with("http://example.com")

        with patch.object(
            pool._client, "delete", new_callable=AsyncMock, return_value=mock_response
        ) as m:
            result = await pool.delete("http://example.com")
            m.assert_awaited_once_with("http://example.com")

    async def test_request_delegates(self, pool: HTTPPool) -> None:
        await pool.start()
        mock_response = MagicMock()
        with patch.object(
            pool._client, "request", new_callable=AsyncMock, return_value=mock_response
        ) as m:
            result = await pool.request("HEAD", "http://example.com")
            m.assert_awaited_once_with("HEAD", "http://example.com")
            assert result is mock_response


# ---------------------------------------------------------------------------
# PoolMonitor
# ---------------------------------------------------------------------------


class TestPoolMonitor:
    @pytest.fixture()
    def monitor(self) -> PoolMonitor:
        db_pool = MagicMock(spec=DatabasePool)
        http_pool = MagicMock(spec=HTTPPool)
        return PoolMonitor(db_pool=db_pool, http_pool=http_pool)  # type: ignore[arg-type]

    async def test_get_stats(self, monitor: PoolMonitor) -> None:
        monitor._db_pool.get_stats_dict.return_value = {"pool_size": 5}  # type: ignore[union-attr]
        monitor._http_pool.get_stats_dict.return_value = {"max_connections": 10}  # type: ignore[union-attr]

        stats = await monitor.get_stats()
        assert stats["database"]["pool_size"] == 5
        assert stats["http"]["max_connections"] == 10

    async def test_check_health_all_ok(self, monitor: PoolMonitor) -> None:
        monitor._db_pool.ping = AsyncMock(return_value=True)  # type: ignore[assignment]
        monitor._db_pool.get_stats.return_value = PoolStats(  # type: ignore[union-attr]
            pool_size=5, checked_in=4, checked_out=1, overflow=0
        )
        monitor._http_pool.get_stats.return_value = HTTPPoolStats(  # type: ignore[union-attr]
            max_connections=10, max_keepalive_connections=5
        )
        monitor._http_pool._client = MagicMock()
        monitor._http_pool._client.is_closed = False

        report = await monitor.check_health()
        assert report.all_healthy is True
        assert report.warnings == []

    async def test_check_health_db_down(self, monitor: PoolMonitor) -> None:
        monitor._db_pool.ping = AsyncMock(return_value=False)  # type: ignore[assignment]
        monitor._db_pool.get_stats.return_value = PoolStats(  # type: ignore[union-attr]
            pool_size=5, checked_in=0, checked_out=0, overflow=0
        )
        monitor._http_pool.get_stats.return_value = HTTPPoolStats(  # type: ignore[union-attr]
            max_connections=10, max_keepalive_connections=5
        )
        monitor._http_pool._client = MagicMock()
        monitor._http_pool._client.is_closed = False

        report = await monitor.check_health()
        assert report.database_healthy is False
        assert report.all_healthy is False
        assert "数据库连接 ping 失败" in report.warnings

    async def test_check_health_high_utilization_warning(
        self, monitor: PoolMonitor
    ) -> None:
        monitor._db_pool.ping = AsyncMock(return_value=True)  # type: ignore[assignment]
        monitor._db_pool.get_stats.return_value = PoolStats(  # type: ignore[union-attr]
            pool_size=5, checked_in=1, checked_out=4, overflow=0
        )
        monitor._http_pool.get_stats.return_value = HTTPPoolStats(  # type: ignore[union-attr]
            max_connections=10, max_keepalive_connections=5
        )
        monitor._http_pool._client = MagicMock()
        monitor._http_pool._client.is_closed = False

        report = await monitor.check_health()
        assert report.database_healthy is True
        assert len(report.warnings) == 1
        assert "使用率过高" in report.warnings[0]

    def test_report_no_warnings(self, monitor: PoolMonitor) -> None:
        monitor._db_pool.get_stats.return_value = PoolStats(  # type: ignore[union-attr]
            pool_size=5, checked_in=3, checked_out=2, overflow=0
        )
        monitor._db_pool.get_stats_dict.return_value = {"pool_size": 5}  # type: ignore[union-attr]
        monitor._http_pool.get_stats_dict.return_value = {"max_connections": 10}  # type: ignore[union-attr]

        result = monitor.report()
        assert result["warnings"] == []

    def test_report_with_warning(self, monitor: PoolMonitor) -> None:
        monitor._db_pool.get_stats.return_value = PoolStats(  # type: ignore[union-attr]
            pool_size=5, checked_in=0, checked_out=5, overflow=0
        )
        monitor._db_pool.get_stats_dict.return_value = {"pool_size": 5}  # type: ignore[union-attr]
        monitor._http_pool.get_stats_dict.return_value = {"max_connections": 10}  # type: ignore[union-attr]

        result = monitor.report()
        assert len(result["warnings"]) == 1
        assert "使用率" in result["warnings"][0]
