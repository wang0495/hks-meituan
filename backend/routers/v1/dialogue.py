"""V1 对话式路线调整接口。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.cache import route_cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1-dialogue"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class AdjustRequestV1(BaseModel):
    """V1 对话调整请求。"""

    instruction: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="用户调整指令",
        examples=["换掉第二个景点", "太赶了"],
    )


class DialogueResultV1(BaseModel):
    """V1 对话调整响应。"""

    reply: str = Field(..., description="系统回复文本")
    route: dict = Field(..., description="调整后的路线数据")
    changes_made: list[dict] = Field(default_factory=list, description="变更列表")


# ---------------------------------------------------------------------------
# API 实现
# ---------------------------------------------------------------------------


@router.post(
    "/dialogue/{session_id}",
    summary="[V1] 对话式路线调整",
    description="V1版本的对话式路线调整接口。",
    tags=["v1-dialogue"],
)
async def dialogue_v1(session_id: str, request: AdjustRequestV1):
    """V1 版本的对话式路线调整。"""
    from backend.services.dialogue import dialogue_engine

    result = await dialogue_engine.process_instruction(session_id, request.instruction)

    if "error" in result:
        raise HTTPException(status_code=result.get("code", 400), detail=result["error"])

    if "route" in result:
        route_cache.set(session_id, result["route"])

    return result


@router.get(
    "/route/{route_id}",
    summary="[V1] 获取路线详情",
    description="V1版本的路线详情查询接口。",
    tags=["v1-dialogue"],
)
async def get_route_v1(route_id: str):
    """V1 版本的路线详情查询。"""
    route_data = route_cache.get(route_id)
    if route_data is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route_data
