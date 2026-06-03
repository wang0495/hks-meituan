"""CityFlow 异步任务队列。

基于 asyncio.Queue 实现的内存任务队列，支持：
- 多 worker 并发执行
- 任务状态追踪（pending / running / completed / failed / cancelled）
- 任务取消
- 全局单例访问
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 任务状态枚举
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    """任务生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# 任务对象
# ---------------------------------------------------------------------------


class Task:
    """单个任务的状态容器。"""

    def __init__(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: tuple,
        kwargs: dict,
    ) -> None:
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.status: TaskStatus = TaskStatus.PENDING
        self.result: Any = None
        self.error: str | None = None
        self.created_at: datetime = datetime.now()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为 API 响应字典。"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
        }


# ---------------------------------------------------------------------------
# 任务队列
# ---------------------------------------------------------------------------


class TaskQueue:
    """基于 asyncio.Queue 的内存任务队列。"""

    def __init__(self, max_workers: int = 5) -> None:
        self._tasks: dict[str, Task] = {}
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._max_workers = max_workers
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """启动所有 worker 协程。"""
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(f"worker-{i}")) for i in range(self._max_workers)
        ]
        logger.info("任务队列启动，worker 数: %d", self._max_workers)

    async def stop(self) -> None:
        """停止所有 worker，等待正在执行的任务完成。"""
        self._running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("任务队列已停止")

    async def submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """提交一个异步任务，返回 task_id。"""
        task_id = uuid.uuid4().hex[:8]
        task = Task(task_id, func, args, kwargs)
        self._tasks[task_id] = task
        await self._queue.put(task)
        logger.info("任务已提交: %s", task_id)
        return task_id

    async def get_task(self, task_id: str) -> Task | None:
        """根据 task_id 获取任务对象。"""
        return self._tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """取消一个尚未开始执行的任务。

        Returns:
            True 表示取消成功，False 表示任务不存在或已在执行。
        """
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            logger.info("任务已取消: %s", task_id)
            return True
        return False

    async def list_tasks(self, status: TaskStatus | None = None) -> list[dict[str, Any]]:
        """列出所有任务，可按状态过滤。"""
        tasks = self._tasks.values()
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    async def _worker(self, name: str) -> None:
        """单个 worker 协程，持续从队列取任务并执行。"""
        logger.info("Worker 启动: %s", name)

        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # 跳过已取消的任务
            if task.status == TaskStatus.CANCELLED:
                continue

            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            try:
                result = await task.func(*task.args, **task.kwargs)
                task.result = result
                task.status = TaskStatus.COMPLETED
                logger.info("任务完成: %s", task.task_id)
            except Exception as exc:
                task.error = str(exc)
                task.status = TaskStatus.FAILED
                logger.error("任务失败: %s, 错误: %s", task.task_id, exc)
            finally:
                task.completed_at = datetime.now()

        logger.info("Worker 停止: %s", name)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_task_queue: TaskQueue | None = None


def get_task_queue() -> TaskQueue:
    """获取全局任务队列实例（懒初始化）。"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(max_workers=5)
    return _task_queue
