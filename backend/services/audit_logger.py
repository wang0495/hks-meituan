"""CityFlow 审计日志服务。

提供审计日志的记录、查询和导出功能。
使用缓冲写入减少数据库压力，支持 JSON 和 CSV 导出。
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime  # noqa: TC003 — runtime needed
from enum import StrEnum
from functools import wraps
from typing import Any

from sqlalchemy import and_, func, select

from backend.database.base import async_session_factory
from backend.database.models import AuditLog

logger = logging.getLogger(__name__)

__all__ = [
    "AuditAction",
    "AuditLogger",
    "audit_log",
    "get_audit_logger",
]


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------


class AuditAction(StrEnum):
    """审计动作类型。"""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    PLAN_ROUTE = "plan_route"
    ADJUST_ROUTE = "adjust_route"
    SEARCH_POI = "search_poi"
    EXPORT = "export"


# ---------------------------------------------------------------------------
# 审计日志记录器
# ---------------------------------------------------------------------------


class AuditLogger:
    """审计日志记录器。

    使用内存缓冲区批量写入数据库，减少 I/O 压力。
    缓冲区满或手动调用 flush 时写入数据库。
    """

    def __init__(self, buffer_size: int = 100) -> None:
        self._buffer: list[dict[str, Any]] = []
        self._buffer_size = buffer_size

    async def log(
        self,
        user_id: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """记录一条审计日志。

        Args:
            user_id: 操作用户 ID。
            action: 审计动作类型。
            resource_type: 资源类型（如 route、poi、user）。
            resource_id: 资源 ID。
            details: 附加详情。
            ip_address: 客户端 IP。
            user_agent: 客户端 User-Agent。
        """
        entry = {
            "user_id": user_id,
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        self._buffer.append(entry)
        logger.info(
            "审计日志 | user=%s action=%s resource=%s/%s",
            user_id,
            action.value,
            resource_type,
            resource_id or "-",
        )

        if len(self._buffer) >= self._buffer_size:
            await self.flush()

    async def flush(self) -> None:
        """将缓冲区写入数据库。"""
        if not self._buffer:
            return

        entries = self._buffer[:]
        self._buffer.clear()

        try:
            async with async_session_factory() as session:
                for entry in entries:
                    log_obj = AuditLog(
                        user_id=entry["user_id"],
                        action=entry["action"],
                        resource_type=entry["resource_type"],
                        resource_id=entry["resource_id"],
                        details=entry["details"],
                        ip_address=entry["ip_address"],
                        user_agent=entry["user_agent"],
                    )
                    session.add(log_obj)
                await session.commit()
        except Exception:
            logger.exception("审计日志写入失败，丢失 %d 条记录", len(entries))

    async def query(
        self,
        user_id: str | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询审计日志。

        Args:
            user_id: 按用户 ID 过滤。
            action: 按动作类型过滤。
            resource_type: 按资源类型过滤。
            start_time: 起始时间（含）。
            end_time: 结束时间（含）。
            limit: 返回条数上限。
            offset: 偏移量。

        Returns:
            审计日志列表。
        """
        # 先刷新缓冲区，确保最新数据可查
        await self.flush()

        conditions = []
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action.value)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if start_time:
            conditions.append(AuditLog.created_at >= start_time)
        if end_time:
            conditions.append(AuditLog.created_at <= end_time)

        stmt = select(AuditLog)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

        async with async_session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [self._to_dict(row) for row in rows]

    async def count(
        self,
        user_id: str | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """统计符合条件的审计日志总数。"""
        await self.flush()

        conditions = []
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action.value)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if start_time:
            conditions.append(AuditLog.created_at >= start_time)
        if end_time:
            conditions.append(AuditLog.created_at <= end_time)

        stmt = select(func.count(AuditLog.id))
        if conditions:
            stmt = stmt.where(and_(*conditions))

        async with async_session_factory() as session:
            result = await session.execute(stmt)
            return result.scalar_one()

    async def export_json(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 10000,
    ) -> str:
        """导出审计日志为 JSON 字符串。"""
        logs = await self.query(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return json.dumps(logs, ensure_ascii=False, indent=2, default=str)

    async def export_csv(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 10000,
    ) -> str:
        """导出审计日志为 CSV 字符串。"""
        logs = await self.query(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        if not logs:
            return ""

        output = io.StringIO()
        fieldnames = [
            "id",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "details",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in logs:
            # details 转为 JSON 字符串以便 CSV 存储
            row_copy = dict(row)
            row_copy["details"] = json.dumps(row_copy["details"], ensure_ascii=False)
            writer.writerow(row_copy)

        return output.getvalue()

    @staticmethod
    def _to_dict(log: AuditLog) -> dict[str, Any]:
        """将 ORM 对象转为字典。"""
        return {
            "id": str(log.id),
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details or {},
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志记录器单例。"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------


def audit_log(action: AuditAction, resource_type: str):
    """审计日志装饰器。

    自动记录被装饰函数的调用为审计日志。
    函数的第一个参数应为 user_id (str)，或从 kwargs 中获取。

    用法::

        @audit_log(AuditAction.PLAN_ROUTE, "route")
        async def plan_route(user_id: str, ...):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # 尝试从参数中提取 user_id
            user_id = kwargs.get("user_id", "system")
            if not user_id and args:
                user_id = str(args[0]) if args[0] else "system"

            al = get_audit_logger()
            await al.log(
                user_id=str(user_id),
                action=action,
                resource_type=resource_type,
                details={
                    "function": func.__qualname__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                },
            )
            return result

        return wrapper

    return decorator
