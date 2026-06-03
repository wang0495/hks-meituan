"""CityFlow 新连接池模块测试。

覆盖 backend/pool/database.py 和 backend/pool/http.py 的核心功能。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.pool.database import DatabasePool
from backend.pool.http import HTTPPool

# ---------------------------------------------------------------------------
# DatabasePool
# ---------------------------------------------------------------------------


class TestDatabasePoolNew:
    """backend/pool/database.py 测试。"""

    @pytest.fixture()
    def mock_engine(self):
        """模拟 SQLAlchemy 异步引擎。"""
        engine = MagicMock()
        engine.dispose = AsyncMock()
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 8
        pool.checkedout.return_value = 2
        pool.overflow.return_value = 0
        engine.pool = pool

        # ping 用的 connect 上下文管理器
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        engine.connect.return_value = mock_conn

        return engine

    @pytest.fixture()
    def pool(self, mock_engine):
        """创建使用模拟引擎的连接池。"""
        with patch("backend.pool.database.create_async_engine", return_value=mock_engine):
            p = DatabasePool(
                database_url="postgresql+asyncpg://test:test@localhost/test",
                pool_size=5,
                max_overflow=10,
            )
        return p

    def test_get_pool_stats(self, pool: DatabasePool) -> None:
        stats = pool.get_pool_stats()
        assert stats["pool_size"] == 10
        assert stats["checkedin"] == 8
        assert stats["checkedout"] == 2
        assert stats["overflow"] == 0

    async def test_ping_success(self, pool: DatabasePool) -> None:
        result = await pool.ping()
        assert result is True

    async def test_ping_failure(self, pool: DatabasePool, mock_engine) -> None:
        mock_engine.connect.side_effect = ConnectionError("db down")
        result = await pool.ping()
        assert result is False

    async def test_get_session(self, pool: DatabasePool) -> None:
        session = await pool.get_session()
        assert session is not None

    async def test_session_scope_commit(self, pool: DatabasePool) -> None:
        mock_session = AsyncMock()
        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(pool, "_session_factory", mock_factory):
            async with pool.session_scope() as session:
                assert session is mock_session

        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    async def test_session_scope_rollback(self, pool: DatabasePool) -> None:
        mock_session = AsyncMock()
        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(pool, "_session_factory", mock_factory):  # noqa: SIM117
            with pytest.raises(RuntimeError):
                async with pool.session_scope():
                    raise RuntimeError("boom")

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    async def test_close(self, pool: DatabasePool, mock_engine) -> None:
        await pool.close()
        mock_engine.dispose.assert_awaited_once()

    async def test_context_manager(self) -> None:
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        with patch("backend.pool.database.create_async_engine", return_value=mock_engine):
            async with DatabasePool("postgresql+asyncpg://x") as p:
                assert p.engine is mock_engine
            mock_engine.dispose.assert_awaited_once()


# ---------------------------------------------------------------------------
# HTTPPool
# ---------------------------------------------------------------------------


class TestHTTPPoolNew:
    """backend/pool/http.py 测试。"""

    @pytest.fixture()
    def pool(self):
        return HTTPPool(
            max_connections=50,
            max_keepalive=10,
            timeout=15.0,
            max_retries=2,
            retry_backoff=0.1,
        )

    def test_lazy_init(self, pool: HTTPPool) -> None:
        """客户端应延迟初始化。"""
        assert pool._client is None

    def test_ensure_client_creates_client(self, pool: HTTPPool) -> None:
        """首次调用 _ensure_client 应创建客户端。"""
        client = pool._ensure_client()
        assert client is not None
        assert pool._client is client

    def test_ensure_client_returns_same(self, pool: HTTPPool) -> None:
        """多次调用 _ensure_client 应返回同一实例。"""
        c1 = pool._ensure_client()
        c2 = pool._ensure_client()
        assert c1 is c2

    async def test_close_without_use(self, pool: HTTPPool) -> None:
        """未使用的连接池关闭不应报错。"""
        await pool.close()  # should not raise

    async def test_close(self, pool: HTTPPool) -> None:
        """关闭应调用 aclose。"""
        client = pool._ensure_client()
        with patch.object(client, "aclose", new_callable=AsyncMock) as mock_close:
            await pool.close()
            mock_close.assert_awaited_once()
        assert pool._client is None

    async def test_get_delegates_to_request(self, pool: HTTPPool) -> None:
        """GET 请求应正确委托。"""
        mock_resp = MagicMock()
        with patch.object(pool, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await pool.get("http://example.com")
            assert result is mock_resp

    async def test_post_delegates_to_request(self, pool: HTTPPool) -> None:
        """POST 请求应正确委托。"""
        mock_resp = MagicMock()
        with patch.object(pool, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await pool.post("http://example.com", json={"a": 1})
            assert result is mock_resp

    async def test_request_retries_on_failure(self, pool: HTTPPool) -> None:
        """请求失败时应重试。"""
        client = pool._ensure_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        call_count = 0

        async def mock_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("connection refused")
            return mock_resp

        with patch.object(client, "request", side_effect=mock_request):
            result = await pool.request("GET", "http://example.com")
            assert result is mock_resp
            assert call_count == 2

    async def test_request_raises_after_max_retries(self, pool: HTTPPool) -> None:
        """超过最大重试次数后应抛出异常。"""
        client = pool._ensure_client()

        async def mock_request(method, url, **kwargs):
            raise httpx.ConnectError("connection refused")

        with patch.object(client, "request", side_effect=mock_request):  # noqa: SIM117
            with pytest.raises(httpx.ConnectError):
                await pool.request("GET", "http://example.com")

    def test_get_pool_stats_closed(self, pool: HTTPPool) -> None:
        """未初始化时应返回零值。"""
        stats = pool.get_pool_stats()
        assert stats["max_connections"] == 50
        assert stats["active"] == 0

    def test_get_pool_stats_open(self, pool: HTTPPool) -> None:
        """初始化后应能读取连接池状态。"""
        client = pool._ensure_client()
        # 模拟 httpcore 内部连接池
        mock_conn = MagicMock()
        mock_conn.is_idle.return_value = True
        mock_conn2 = MagicMock()
        mock_conn2.is_idle.return_value = False
        mock_inner_pool = MagicMock()
        mock_inner_pool._connections = [mock_conn, mock_conn2]
        client._transport._pool = mock_inner_pool

        stats = pool.get_pool_stats()
        assert stats["max_connections"] == 50
        assert stats["active"] == 1
        assert stats["keepalive"] == 1

    async def test_context_manager(self) -> None:
        """async with 应自动关闭连接池。"""
        async with HTTPPool() as p:
            client = p._ensure_client()
            assert client is not None
        # after exit, client should be closed
        assert p._client is None

    async def test_ping_failure(self, pool: HTTPPool) -> None:
        """ping 失败应返回 False。"""
        client = pool._ensure_client()
        with patch.object(
            client,
            "head",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("fail"),
        ):
            result = await pool.ping()
            assert result is False

    async def test_ping_success(self, pool: HTTPPool) -> None:
        """ping 成功应返回 True。"""
        client = pool._ensure_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(client, "head", new_callable=AsyncMock, return_value=mock_resp):
            result = await pool.ping()
            assert result is True

    async def test_ping_server_error(self, pool: HTTPPool) -> None:
        """ping 返回 5xx 应返回 False。"""
        client = pool._ensure_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch.object(client, "head", new_callable=AsyncMock, return_value=mock_resp):
            result = await pool.ping()
            assert result is False


# ---------------------------------------------------------------------------
# PoolMonitor 集成
# ---------------------------------------------------------------------------


class TestPoolMonitorIntegration:
    """PoolMonitor 与新连接池的集成测试。"""

    def test_monitor_uses_ping(self) -> None:
        """健康检查应使用 ping 方法。"""
        from backend.pool.monitor import PoolMonitor

        db_pool = MagicMock()
        db_pool.get_pool_stats.return_value = {
            "pool_size": 10,
            "checkedin": 8,
            "checkedout": 2,
            "overflow": 0,
        }
        db_pool.ping = AsyncMock(return_value=True)

        http_pool = MagicMock()
        http_pool.get_pool_stats.return_value = {
            "max_connections": 100,
            "active": 10,
            "keepalive": 5,
        }

        monitor = PoolMonitor(db_pool=db_pool, http_pool=http_pool)
        report = monitor.check_health()
        assert report.healthy is True
