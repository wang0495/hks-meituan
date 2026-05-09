"""审计日志服务单元测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.audit_logger import (AuditAction, AuditLogger, audit_log,
                                           get_audit_logger)


class TestAuditAction:
    """审计动作枚举测试。"""

    def test_action_values(self) -> None:
        assert AuditAction.CREATE.value == "create"
        assert AuditAction.READ.value == "read"
        assert AuditAction.UPDATE.value == "update"
        assert AuditAction.DELETE.value == "delete"
        assert AuditAction.LOGIN.value == "login"
        assert AuditAction.LOGOUT.value == "logout"
        assert AuditAction.PLAN_ROUTE.value == "plan_route"
        assert AuditAction.ADJUST_ROUTE.value == "adjust_route"
        assert AuditAction.SEARCH_POI.value == "search_poi"
        assert AuditAction.EXPORT.value == "export"

    def test_action_is_string_enum(self) -> None:
        assert isinstance(AuditAction.CREATE, str)
        assert AuditAction.CREATE == "create"


class TestAuditLogger:
    """审计日志记录器测试。"""

    def test_init_default_buffer_size(self) -> None:
        al = AuditLogger()
        assert al._buffer_size == 100
        assert al._buffer == []

    def test_init_custom_buffer_size(self) -> None:
        al = AuditLogger(buffer_size=50)
        assert al._buffer_size == 50

    @pytest.mark.asyncio
    async def test_log_adds_to_buffer(self) -> None:
        al = AuditLogger(buffer_size=10)
        await al.log(
            user_id="user1",
            action=AuditAction.CREATE,
            resource_type="route",
            resource_id="route123",
        )
        assert len(al._buffer) == 1
        entry = al._buffer[0]
        assert entry["user_id"] == "user1"
        assert entry["action"] == "create"
        assert entry["resource_type"] == "route"
        assert entry["resource_id"] == "route123"
        assert entry["details"] == {}

    @pytest.mark.asyncio
    async def test_log_with_details(self) -> None:
        al = AuditLogger(buffer_size=10)
        details = {"key": "value", "count": 42}
        await al.log(
            user_id="user1",
            action=AuditAction.UPDATE,
            resource_type="user",
            details=details,
        )
        assert al._buffer[0]["details"] == details

    @pytest.mark.asyncio
    async def test_log_with_ip_and_user_agent(self) -> None:
        al = AuditLogger(buffer_size=10)
        await al.log(
            user_id="user1",
            action=AuditAction.LOGIN,
            resource_type="session",
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
        )
        entry = al._buffer[0]
        assert entry["ip_address"] == "127.0.0.1"
        assert entry["user_agent"] == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_log_flushes_when_buffer_full(self) -> None:
        al = AuditLogger(buffer_size=2)
        al.flush = AsyncMock()

        await al.log(
            user_id="user1",
            action=AuditAction.READ,
            resource_type="route",
        )
        al.flush.assert_not_called()

        await al.log(
            user_id="user2",
            action=AuditAction.READ,
            resource_type="route",
        )
        al.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_clears_buffer(self) -> None:
        al = AuditLogger(buffer_size=100)
        al._buffer = [
            {
                "user_id": "user1",
                "action": "create",
                "resource_type": "route",
                "resource_id": None,
                "details": {},
                "ip_address": None,
                "user_agent": None,
            }
        ]

        with patch(
            "backend.services.audit_logger.async_session_factory"
        ) as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await al.flush()

        assert al._buffer == []

    @pytest.mark.asyncio
    async def test_flush_noop_when_empty(self) -> None:
        al = AuditLogger()
        # 不应抛出异常
        await al.flush()

    @pytest.mark.asyncio
    async def test_query_calls_flush_first(self) -> None:
        al = AuditLogger()
        al.flush = AsyncMock()

        with patch(
            "backend.services.audit_logger.async_session_factory"
        ) as mock_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await al.query(user_id="user1")

        al.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_json_format(self) -> None:
        al = AuditLogger()
        al.query = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "user_id": "user1",
                    "action": "create",
                    "resource_type": "route",
                }
            ]
        )

        result = await al.export_json()
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["user_id"] == "user1"

    @pytest.mark.asyncio
    async def test_export_csv_format(self) -> None:
        al = AuditLogger()
        al.query = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "user_id": "user1",
                    "action": "create",
                    "resource_type": "route",
                    "resource_id": "r1",
                    "details": {"key": "value"},
                    "ip_address": "127.0.0.1",
                    "user_agent": "test",
                    "created_at": "2026-05-09T00:00:00",
                }
            ]
        )

        result = await al.export_csv()
        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert "user_id" in lines[0]
        assert "user1" in lines[1]

    @pytest.mark.asyncio
    async def test_export_csv_empty(self) -> None:
        al = AuditLogger()
        al.query = AsyncMock(return_value=[])

        result = await al.export_csv()
        assert result == ""

    def test_to_dict(self) -> None:
        mock_log = MagicMock()
        mock_log.id = "test-id"
        mock_log.user_id = "user1"
        mock_log.action = "create"
        mock_log.resource_type = "route"
        mock_log.resource_id = "r1"
        mock_log.details = {"key": "value"}
        mock_log.ip_address = "127.0.0.1"
        mock_log.user_agent = "test"
        mock_log.created_at = datetime(2026, 5, 9, tzinfo=timezone.utc)

        result = AuditLogger._to_dict(mock_log)
        assert result["id"] == "test-id"
        assert result["user_id"] == "user1"
        assert result["action"] == "create"
        assert result["created_at"] is not None


class TestGetAuditLogger:
    """全局单例测试。"""

    def test_returns_same_instance(self) -> None:
        # 重置全局状态
        import backend.services.audit_logger as mod

        mod._audit_logger = None

        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2

    def test_returns_audit_logger_instance(self) -> None:
        import backend.services.audit_logger as mod

        mod._audit_logger = None

        logger = get_audit_logger()
        assert isinstance(logger, AuditLogger)


class TestAuditLogDecorator:
    """审计日志装饰器测试。"""

    @pytest.mark.asyncio
    async def test_decorator_records_log(self) -> None:
        import backend.services.audit_logger as mod

        mod._audit_logger = None

        @audit_log(AuditAction.PLAN_ROUTE, "route")
        async def my_function(user_id: str = "system"):
            return "result"

        with patch.object(
            get_audit_logger(), "log", new_callable=AsyncMock
        ) as mock_log:
            result = await my_function(user_id="user1")

        assert result == "result"
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        assert call_kwargs.kwargs["user_id"] == "user1"
        assert call_kwargs.kwargs["action"] == AuditAction.PLAN_ROUTE
        assert call_kwargs.kwargs["resource_type"] == "route"

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_name(self) -> None:
        @audit_log(AuditAction.READ, "data")
        async def my_special_function():
            return None

        assert my_special_function.__name__ == "my_special_function"
