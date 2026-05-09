"""CityFlow 会话 API。

提供会话的 CRUD 接口和统计查询。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.session import get_session_manager

router = APIRouter(prefix="/api/session", tags=["会话"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """创建会话请求。"""

    user_id: str | None = None


class UpdateSessionRequest(BaseModel):
    """更新会话请求。"""

    data: dict[str, Any]


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.post("/", summary="创建会话")
async def create_session(body: CreateSessionRequest | None = None) -> dict[str, str]:
    """创建新会话，返回 session_id。"""
    session_manager = get_session_manager()
    user_id = body.user_id if body else None
    session_id = await session_manager.create_session(user_id=user_id)
    return {"session_id": session_id}


@router.get("/stats", summary="会话统计")
async def get_session_stats() -> dict[str, int]:
    """获取会话统计信息（总数、有用户绑定的、匿名的）。"""
    session_manager = get_session_manager()
    return await session_manager.get_stats()


@router.get("/{session_id}", summary="获取会话")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取指定会话的完整数据。"""
    session_manager = get_session_manager()
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    return session


@router.put("/{session_id}", summary="更新会话")
async def update_session(session_id: str, body: UpdateSessionRequest) -> dict[str, str]:
    """更新会话数据（合并写入）。"""
    session_manager = get_session_manager()
    success = await session_manager.update_session(session_id, body.data)

    if not success:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    return {"message": "会话已更新"}


@router.delete("/{session_id}", summary="删除会话")
async def delete_session(session_id: str) -> dict[str, str]:
    """删除指定会话。"""
    session_manager = get_session_manager()
    success = await session_manager.delete_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {"message": "会话已删除"}


@router.post("/{session_id}/refresh", summary="刷新会话")
async def refresh_session(session_id: str) -> dict[str, str]:
    """刷新会话过期时间（续期）。"""
    session_manager = get_session_manager()
    success = await session_manager.refresh_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    return {"message": "会话已续期"}


@router.get("/user/{user_id}/list", summary="获取用户会话列表")
async def get_user_sessions(user_id: str) -> dict[str, Any]:
    """获取指定用户的所有活跃会话。"""
    session_manager = get_session_manager()
    sessions = await session_manager.get_user_sessions(user_id)
    return {"user_id": user_id, "sessions": sessions, "count": len(sessions)}
