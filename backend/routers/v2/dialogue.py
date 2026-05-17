"""V2 对话式路线调整接口（复用V1逻辑）。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.cache import route_cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v2-dialogue"])


class AdjustRequestV2(BaseModel):
    """V2 对话调整请求。"""

    instruction: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="用户调整指令",
        examples=["换掉第二个景点", "太赶了"],
    )


class DialogueResultV2(BaseModel):
    """V2 对话调整响应。"""

    reply: str = Field(..., description="系统回复文本")
    route: dict = Field(..., description="调整后的路线数据")
    changes_made: list[dict] = Field(default_factory=list, description="变更列表")


@router.post(
    "/dialogue/{session_id}",
    summary="[V2] 对话式路线调整",
    description="V2版本的对话式路线调整接口。",
    tags=["v2-dialogue"],
)
async def dialogue_v2(session_id: str, request: AdjustRequestV2) -> dict:
    """V2 版本的对话式路线调整。"""
    from backend.services.dialogue import dialogue_engine

    result = await dialogue_engine.process_instruction(session_id, request.instruction)

    if "error" in result:
        raise HTTPException(status_code=result.get("code", 400), detail=result["error"])

    if "route" in result:
        route_cache.set(session_id, result["route"])

    return result


@router.get(
    "/route/{route_id}",
    summary="[V2] 获取路线详情",
    description="V2版本的路线详情查询接口。",
    tags=["v2-dialogue"],
)
async def get_route_v2(route_id: str) -> dict:
    """V2 版本的路线详情查询。"""
    route_data = route_cache.get(route_id)
    if route_data is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route_data
