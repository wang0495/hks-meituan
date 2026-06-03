"""CityFlow 审计日志 API。

提供审计日志的查询和导出接口。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, Response

from backend.services.audit_logger import AuditAction, get_audit_logger

router = APIRouter(prefix="/api/audit", tags=["审计日志"])


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /api/audit/logs -- 查询审计日志
# ---------------------------------------------------------------------------


@router.get(
    "/logs",
    summary="查询审计日志",
    description=(
        "按条件查询审计日志记录。\n\n"
        "支持按用户 ID、动作类型、资源类型和时间范围过滤。\n"
        "结果按时间倒序排列。"
    ),
    response_description="审计日志列表及总数",
)
async def get_audit_logs(
    user_id: str | None = Query(None, description="按用户 ID 过滤"),
    action: AuditAction | None = Query(None, description="按动作类型过滤"),
    resource_type: str | None = Query(None, description="按资源类型过滤"),
    start_time: datetime | None = Query(None, description="起始时间（ISO 8601）"),
    end_time: datetime | None = Query(None, description="结束时间（ISO 8601）"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数上限"),
    offset: int = Query(0, ge=0, description="偏移量"),
) -> dict:
    """查询审计日志。"""
    al = get_audit_logger()

    logs = await al.query(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    total = await al.count(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time,
    )

    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# GET /api/audit/export -- 导出审计日志
# ---------------------------------------------------------------------------


@router.get(
    "/export",
    summary="导出审计日志",
    description=(
        "导出审计日志为 JSON 或 CSV 格式。\n\n" "支持按时间范围筛选，最多导出 10000 条记录。"
    ),
)
async def export_audit_logs(
    format: Literal["json", "csv"] = Query("json", description="导出格式"),
    start_time: datetime | None = Query(None, description="起始时间（ISO 8601）"),
    end_time: datetime | None = Query(None, description="结束时间（ISO 8601）"),
    limit: int = Query(10000, ge=1, le=10000, description="最大导出条数"),
) -> Response:
    """导出审计日志。"""
    al = get_audit_logger()

    # 记录导出操作本身
    await al.log(
        user_id="system",
        action=AuditAction.EXPORT,
        resource_type="audit_log",
        details={"format": format, "limit": limit},
    )

    if format == "csv":
        content = await al.export_csv(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
        )
    else:
        content = await al.export_json(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return PlainTextResponse(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
        )


# ---------------------------------------------------------------------------
# GET /api/audit/stats -- 审计日志统计
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    summary="审计日志统计",
    description="返回审计日志的动作类型分布统计。",
    response_description="各动作类型的日志数量",
)
async def get_audit_stats(
    start_time: datetime | None = Query(None, description="起始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
) -> dict:
    """审计日志统计。"""
    al = get_audit_logger()

    stats: dict[str, int] = {}
    for action in AuditAction:
        count = await al.count(
            action=action,
            start_time=start_time,
            end_time=end_time,
        )
        if count > 0:
            stats[action.value] = count

    total = await al.count(start_time=start_time, end_time=end_time)

    return {
        "total": total,
        "by_action": stats,
    }
