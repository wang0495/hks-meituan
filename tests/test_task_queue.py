"""异步任务队列测试。"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.task_queue import TaskQueue, TaskStatus, get_task_queue

# ---------------------------------------------------------------------------
# TaskQueue 基本功能
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_and_complete():
    """提交任务并等待完成。"""
    queue = TaskQueue(max_workers=2)
    await queue.start()

    async def add(a: int, b: int) -> int:
        return a + b

    task_id = await queue.submit(add, 1, 2)
    assert len(task_id) == 8  # uuid 前8位

    # 等待 worker 处理
    await asyncio.sleep(0.3)

    task = await queue.get_task(task_id)
    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert task.result == 3
    assert task.error is None

    await queue.stop()


@pytest.mark.asyncio
async def test_task_failure():
    """任务执行失败时状态为 FAILED。"""
    queue = TaskQueue(max_workers=1)
    await queue.start()

    async def boom():
        raise ValueError("boom")

    task_id = await queue.submit(boom)
    await asyncio.sleep(0.3)

    task = await queue.get_task(task_id)
    assert task is not None
    assert task.status == TaskStatus.FAILED
    assert "boom" in task.error

    await queue.stop()


@pytest.mark.asyncio
async def test_cancel_pending_task():
    """取消尚未执行的任务。"""
    queue = TaskQueue(max_workers=1)
    await queue.start()

    # 用一个 blocker 占住唯一的 worker
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocker():
        started.set()
        await release.wait()

    await queue.submit(blocker)
    await asyncio.sleep(0.1)
    await started.wait()

    # 提交第二个任务，它会排队
    async def fast():
        return "ok"

    task_id = await queue.submit(fast)
    success = await queue.cancel_task(task_id)
    assert success is True

    task = await queue.get_task(task_id)
    assert task.status == TaskStatus.CANCELLED

    release.set()
    await asyncio.sleep(0.2)
    await queue.stop()


@pytest.mark.asyncio
async def test_cancel_running_task_fails():
    """无法取消已经在运行的任务。"""
    queue = TaskQueue(max_workers=1)
    await queue.start()

    started = asyncio.Event()
    release = asyncio.Event()

    async def blocker():
        started.set()
        await release.wait()

    task_id = await queue.submit(blocker)
    await asyncio.sleep(0.1)
    await started.wait()

    success = await queue.cancel_task(task_id)
    assert success is False

    release.set()
    await asyncio.sleep(0.1)
    await queue.stop()


@pytest.mark.asyncio
async def test_list_tasks():
    """列出任务并按状态过滤。"""
    queue = TaskQueue(max_workers=2)
    await queue.start()

    async def ok():
        return True

    async def boom():
        raise RuntimeError("err")

    await queue.submit(ok)
    await queue.submit(ok)
    await queue.submit(boom)

    await asyncio.sleep(0.3)

    all_tasks = await queue.list_tasks()
    assert len(all_tasks) == 3

    completed = await queue.list_tasks(status=TaskStatus.COMPLETED)
    assert len(completed) == 2

    failed = await queue.list_tasks(status=TaskStatus.FAILED)
    assert len(failed) == 1

    await queue.stop()


@pytest.mark.asyncio
async def test_task_to_dict():
    """Task.to_dict 返回完整字段。"""
    queue = TaskQueue(max_workers=1)
    await queue.start()

    async def hello():
        return "world"

    task_id = await queue.submit(hello)
    await asyncio.sleep(0.3)

    task = await queue.get_task(task_id)
    d = task.to_dict()

    assert d["task_id"] == task_id
    assert d["status"] == "completed"
    assert d["result"] == "world"
    assert d["error"] is None
    assert d["created_at"] is not None
    assert d["started_at"] is not None
    assert d["completed_at"] is not None

    await queue.stop()


@pytest.mark.asyncio
async def test_get_nonexistent_task():
    """查询不存在的任务返回 None。"""
    queue = TaskQueue(max_workers=1)
    task = await queue.get_task("nonexist")
    assert task is None


@pytest.mark.asyncio
async def test_multiple_workers_concurrent():
    """多个 worker 并发执行任务。"""
    queue = TaskQueue(max_workers=3)
    await queue.start()

    call_order = []

    async def slow_task(n: int):
        await asyncio.sleep(0.1)
        call_order.append(n)
        return n

    ids = []
    for i in range(3):
        tid = await queue.submit(slow_task, i)
        ids.append(tid)

    await asyncio.sleep(0.5)

    for tid in ids:
        task = await queue.get_task(tid)
        assert task.status == TaskStatus.COMPLETED

    assert len(call_order) == 3
    await queue.stop()


@pytest.mark.asyncio
async def test_double_start_noop():
    """重复 start 不会创建额外 worker。"""
    queue = TaskQueue(max_workers=2)
    await queue.start()
    worker_count = len(queue._workers)

    await queue.start()  # 应该是 no-op
    assert len(queue._workers) == worker_count

    await queue.stop()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------


def test_get_task_queue_singleton():
    """get_task_queue 返回同一个实例。"""
    import backend.services.task_queue as mod

    # 重置全局实例
    mod._task_queue = None

    q1 = get_task_queue()
    q2 = get_task_queue()
    assert q1 is q2

    # 清理
    mod._task_queue = None


# ---------------------------------------------------------------------------
# API 路由测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_list_tasks(client):
    """GET /api/tasks/ 返回任务列表。"""
    resp = await client.get("/api/tasks/")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "tasks" in data


@pytest.mark.asyncio
async def test_api_get_nonexistent_task(client):
    """GET /api/tasks/{id} 对不存在的任务返回 404。"""
    resp = await client.get("/api/tasks/nonexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_submit_unknown_func(client):
    """POST /api/tasks/{func} 对未知函数返回 404。"""
    resp = await client.post("/api/tasks/unknown_func", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_cancel_nonexistent(client):
    """DELETE /api/tasks/{id} 对不存在的任务返回 400。"""
    resp = await client.delete("/api/tasks/nonexist")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_list_with_invalid_status(client):
    """GET /api/tasks/?status=xxx 返回 400。"""
    resp = await client.get("/api/tasks/?status=invalid")
    assert resp.status_code == 400
