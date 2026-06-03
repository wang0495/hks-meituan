"""CityFlow 后台任务 API。

提供任务提交、状态查询、取消、列表等接口。
通过函数白名单机制控制可执行的后台任务。
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.errors import CityFlowException, ErrorCode
from backend.services.task_queue import TaskStatus, get_task_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["任务"])


# ---------------------------------------------------------------------------
# 白名单：允许通过 API 提交的后台函数
# ---------------------------------------------------------------------------
# key = API 中使用的函数别名
# value = Python 模块路径 + 函数名（用 "." 连接）

ALLOWED_FUNCTIONS: dict[str, str] = {
    # 按需注册后台任务函数，例如：
    # "warmup_cache": "backend.services.cache_warmup.warmup_cache",
    # "generate_report": "backend.services.report.generate_report",
}


def _resolve_function(func_name: str) -> Any:
    """从白名单中查找并导入函数。

    Returns:
        可调用的函数对象，找不到时返回 None。
    """
    module_path = ALLOWED_FUNCTIONS.get(func_name)
    if module_path is None:
        return None

    module_name, attr_name = module_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_name)
        return getattr(module, attr_name, None)
    except (ImportError, AttributeError):
        logger.warning("无法导入函数: %s", module_path)
        return None


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class SubmitTaskRequest(BaseModel):
    """提交任务请求体。"""

    args: list[Any] = Field(default_factory=list, description="位置参数列表")
    kwargs: dict[str, Any] = Field(default_factory=dict, description="关键字参数字典")


class TaskResponse(BaseModel):
    """任务状态响应。"""

    task_id: str
    status: str
    result: Any = None
    error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class TaskListResponse(BaseModel):
    """任务列表响应。"""

    total: int
    tasks: list[TaskResponse]


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------


@router.post(
    "/{func_name}",
    summary="提交后台任务",
    description=(
        "通过函数别名提交一个异步后台任务。\n\n"
        "函数必须在 `ALLOWED_FUNCTIONS` 白名单中注册，否则返回 404。\n\n"
        "提交后立即返回 `task_id`，可通过 `GET /api/tasks/{task_id}` 查询执行状态。"
    ),
    response_description="task_id 和初始状态",
)
async def submit_task(func_name: str, request: SubmitTaskRequest) -> dict:
    """提交后台任务。"""
    func = _resolve_function(func_name)
    if func is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message=f"函数不存在: {func_name}",
            details={
                "func_name": func_name,
                "available": list(ALLOWED_FUNCTIONS.keys()),
            },
        )

    queue = get_task_queue()
    task_id = await queue.submit(func, *request.args, **request.kwargs)

    return {"task_id": task_id, "status": "submitted"}


@router.get(
    "/{task_id}",
    summary="查询任务状态",
    description="根据 task_id 查询任务的当前状态、结果或错误信息。",
    response_model=TaskResponse,
    responses={
        200: {"description": "任务详情"},
        404: {"description": "任务不存在"},
    },
)
async def get_task_status(task_id: str) -> dict:
    """查询任务状态。"""
    queue = get_task_queue()
    task = await queue.get_task(task_id)

    if task is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="任务不存在",
            details={"task_id": task_id},
        )

    return task.to_dict()


@router.delete(
    "/{task_id}",
    summary="取消任务",
    description="取消一个尚未开始执行的任务。已在运行中的任务无法取消。",
    responses={
        200: {"description": "取消成功"},
        400: {"description": "任务无法取消（不存在或已在运行）"},
    },
)
async def cancel_task(task_id: str) -> dict:
    """取消任务。"""
    queue = get_task_queue()
    success = await queue.cancel_task(task_id)

    if not success:
        raise CityFlowException(
            code=ErrorCode.INVALID_REQUEST,
            message="无法取消任务（不存在或已在执行中）",
            details={"task_id": task_id},
        )

    return {"message": "任务已取消", "task_id": task_id}


@router.get(
    "/",
    summary="列出所有任务",
    description="列出所有任务，支持按状态过滤。",
    response_model=TaskListResponse,
)
async def list_tasks(
    status: str | None = Query(
        None,
        description="按状态过滤: pending / running / completed / failed / cancelled",
    ),
) -> dict:
    """列出所有任务。"""
    queue = get_task_queue()

    filter_status = None
    if status:
        try:
            filter_status = TaskStatus(status)
        except ValueError:
            raise CityFlowException(
                code=ErrorCode.INVALID_REQUEST,
                message=f"无效的状态值: {status}",
                details={"valid_values": [s.value for s in TaskStatus]},
            ) from None

    tasks = await queue.list_tasks(status=filter_status)
    return {"total": len(tasks), "tasks": tasks}
