"""消息队列单元测试。

使用 fakeredis 模拟 Redis，不依赖真实 Redis 服务。
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.services.message_queue import Message, MessageQueue

# ---------------------------------------------------------------------------
# Message 模型测试
# ---------------------------------------------------------------------------


class TestMessage:
    """Message 信封对象测试。"""

    def test_create_with_defaults(self):
        """默认生成 message_id 和 created_at。"""
        msg = Message(queue="test", payload={"key": "value"})
        assert msg.queue == "test"
        assert msg.payload == {"key": "value"}
        assert len(msg.message_id) == 12
        assert msg.retry_count == 0
        assert msg.created_at is not None

    def test_create_with_custom_id(self):
        """支持自定义 message_id。"""
        msg = Message(queue="q", payload={}, message_id="custom-id")
        assert msg.message_id == "custom-id"

    def test_to_json_roundtrip(self):
        """序列化 -> 反序列化后字段一致。"""
        original = Message(queue="my_queue", payload={"a": 1, "b": "text"})
        json_str = original.to_json()

        restored = Message.from_json(json_str)
        assert restored.queue == original.queue
        assert restored.payload == original.payload
        assert restored.message_id == original.message_id
        assert restored.retry_count == 0

    def test_to_json_contains_all_fields(self):
        """JSON 字符串包含所有必要字段。"""
        msg = Message(queue="q", payload={"x": 1})
        obj = json.loads(msg.to_json())
        assert "message_id" in obj
        assert "queue" in obj
        assert "payload" in obj
        assert "retry_count" in obj
        assert "created_at" in obj

    def test_retry_count_preserved(self):
        """重试次数在序列化/反序列化中保留。"""
        msg = Message(queue="q", payload={}, retry_count=3)
        restored = Message.from_json(msg.to_json())
        assert restored.retry_count == 3


# ---------------------------------------------------------------------------
# MessageQueue 核心逻辑测试（使用 fakeredis）
# ---------------------------------------------------------------------------


@pytest.fixture
async def mq():
    """创建一个使用 fakeredis 的 MessageQueue 实例。"""
    try:
        import fakeredis.aioredis
    except ImportError:
        pytest.skip("fakeredis 未安装，跳过集成测试")

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    queue = MessageQueue.__new__(MessageQueue)
    queue._redis = fake_redis
    queue._prefix = "test:mq:"
    queue._max_retries = 2
    queue._consumers = {}
    queue._running = False
    yield queue
    await fake_redis.aclose()


@pytest.mark.asyncio
async def test_publish_and_read(mq: MessageQueue):
    """发布消息后能从 Redis 中读取。"""
    msg = await mq.publish("orders", {"item": "coffee", "qty": 2})
    assert msg.queue == "orders"
    assert msg.payload == {"item": "coffee", "qty": 2}

    length = await mq.queue_length("orders")
    assert length == 1


@pytest.mark.asyncio
async def test_publish_many(mq: MessageQueue):
    """批量发布消息。"""
    payloads = [{"i": i} for i in range(5)]
    messages = await mq.publish_many("batch_queue", payloads)
    assert len(messages) == 5

    length = await mq.queue_length("batch_queue")
    assert length == 5


@pytest.mark.asyncio
async def test_consume_single_message(mq: MessageQueue):
    """消费者能正确消费单条消息。"""
    await mq.publish("work", {"task": "process"})

    received: list[dict] = []
    mq._running = True

    async def handler(payload: dict) -> None:
        received.append(payload)
        mq._running = False  # 消费一条后停止

    await mq.consume("work", handler, timeout=1)
    assert len(received) == 1
    assert received[0] == {"task": "process"}


@pytest.mark.asyncio
async def test_consume_retries_on_failure(mq: MessageQueue):
    """消息处理失败时自动重试。"""
    await mq.publish("retry_q", {"data": "fail"})

    call_count = 0
    mq._running = True

    async def failing_handler(payload: dict) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("临时错误")
        # 第3次成功，停止
        mq._running = False

    await mq.consume("retry_q", failing_handler, timeout=1)
    assert call_count == 3


@pytest.mark.asyncio
async def test_consume_sends_to_dlq_after_max_retries(mq: MessageQueue):
    """超过最大重试次数后消息进入死信队列。"""
    await mq.publish("dlq_q", {"data": "always_fail"})

    call_count = 0
    mq._running = True

    async def always_fail(payload: dict) -> None:
        nonlocal call_count
        call_count += 1
        if call_count > mq._max_retries:
            mq._running = False
        raise RuntimeError("永久错误")

    await mq.consume("dlq_q", always_fail, timeout=1)

    # 验证死信队列
    dlq_len = await mq._redis.llen("test:mq:dlq:dlq_q")
    assert dlq_len == 1


@pytest.mark.asyncio
async def test_queue_length(mq: MessageQueue):
    """队列长度查询正确。"""
    assert await mq.queue_length("empty") == 0

    await mq.publish("empty", {"a": 1})
    assert await mq.queue_length("empty") == 1

    await mq.publish("empty", {"b": 2})
    assert await mq.queue_length("empty") == 2


@pytest.mark.asyncio
async def test_clear_queue(mq: MessageQueue):
    """清空队列。"""
    for i in range(3):
        await mq.publish("to_clear", {"i": i})

    assert await mq.queue_length("to_clear") == 3
    deleted = await mq.clear_queue("to_clear")
    assert deleted == 3
    assert await mq.queue_length("to_clear") == 0


@pytest.mark.asyncio
async def test_start_consumer_creates_task(mq: MessageQueue):
    """start_consumer 创建后台 asyncio.Task。"""

    async def noop_handler(payload: dict) -> None:
        pass

    mq._running = True
    task = mq.start_consumer("test_q", noop_handler)
    assert isinstance(task, asyncio.Task)
    assert "test_q" in mq._consumers

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_stop_cancels_all_consumers(mq: MessageQueue):
    """stop() 取消所有消费者 task 并关闭连接。"""

    async def noop_handler(payload: dict) -> None:
        pass

    mq._running = True
    t1 = mq.start_consumer("q1", noop_handler)
    t2 = mq.start_consumer("q2", noop_handler)

    await mq.stop()

    assert t1.cancelled() or t1.done()
    assert t2.cancelled() or t2.done()
    assert len(mq._consumers) == 0


# ---------------------------------------------------------------------------
# 全局单例测试
# ---------------------------------------------------------------------------


def test_get_message_queue_singleton():
    """get_message_queue 返回同一个实例。"""
    import backend.services.message_queue as mod

    mod._mq = None
    from backend.services.message_queue import get_message_queue

    q1 = get_message_queue()
    q2 = get_message_queue()
    assert q1 is q2
    mod._mq = None  # 清理


# ---------------------------------------------------------------------------
# 消息处理器测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_notification():
    """通知处理器正确调用 notify_personal。"""
    from backend.services.message_handlers import handle_notification

    with patch(
        "backend.services.notification.notify_personal", new_callable=AsyncMock
    ) as mock_notify:
        await handle_notification(
            {"session_id": "s1", "content": "hello", "msg_type": "info"}
        )
        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args[0][0] == "s1"
        assert call_args[0][1]["content"] == "hello"


@pytest.mark.asyncio
async def test_handle_analytics_logs(caplog):
    """分析处理器记录日志。"""
    import logging

    from backend.services.message_handlers import handle_analytics

    with caplog.at_level(logging.INFO):
        await handle_analytics({"event_type": "click", "data": {"page": "home"}})

    assert "click" in caplog.text


def test_handler_registry():
    """处理器注册表包含所有内置处理器。"""
    from backend.services.message_handlers import HANDLER_REGISTRY, get_handler

    assert "route_planning" in HANDLER_REGISTRY
    assert "notification" in HANDLER_REGISTRY
    assert "analytics" in HANDLER_REGISTRY

    assert get_handler("notification") is not None
    assert get_handler("nonexistent") is None


# ---------------------------------------------------------------------------
# API 路由测试
# ---------------------------------------------------------------------------


@pytest.fixture
async def mq_client():
    """带 MQ 路由的测试客户端，Session 中间件 Mock 化。"""
    from backend.main import app
    from backend.services.session import get_session_manager

    # Mock session manager 避免连接真实 Redis
    mock_session = AsyncMock()
    mock_session.create_session.return_value = "test-session-id"
    mock_session.get_session.return_value = {"id": "test-session-id"}
    mock_session.close = AsyncMock()

    app.dependency_overrides[get_session_manager] = lambda: mock_session

    # 同时 patch middleware 用到的 session manager
    with patch(
        "backend.middleware.session.get_session_manager", return_value=mock_session
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_publish_message(mq_client: AsyncClient):
    """POST /api/mq/publish/{queue} 发布消息。"""
    with patch("backend.routers.mq.get_message_queue") as mock_get:
        mock_mq = AsyncMock()
        mock_msg = Message(queue="test", payload={"x": 1})
        mock_mq.publish.return_value = mock_msg
        mock_get.return_value = mock_mq

        resp = await mq_client.post("/api/mq/publish/test", json={"payload": {"x": 1}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["queue"] == "test"
        assert "message_id" in data


@pytest.mark.asyncio
async def test_api_publish_batch(mq_client: AsyncClient):
    """POST /api/mq/publish/{queue}/batch 批量发布。"""
    with patch("backend.routers.mq.get_message_queue") as mock_get:
        mock_mq = AsyncMock()
        msgs = [Message(queue="b", payload={"i": i}) for i in range(3)]
        mock_mq.publish_many.return_value = msgs
        mock_get.return_value = mock_mq

        resp = await mq_client.post(
            "/api/mq/publish/b/batch",
            json={"payloads": [{"i": 0}, {"i": 1}, {"i": 2}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["message_ids"]) == 3


@pytest.mark.asyncio
async def test_api_start_consumer_unknown_handler(mq_client: AsyncClient):
    """启动不存在的处理器返回 400。"""
    resp = await mq_client.post(
        "/api/mq/consume/test",
        json={"handler_name": "nonexistent"},
    )
    assert resp.status_code == 400
    assert "处理器不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_queue_status(mq_client: AsyncClient):
    """GET /api/mq/status/{queue} 查询队列状态。"""
    with patch("backend.routers.mq.get_message_queue") as mock_get:
        mock_mq = AsyncMock()
        mock_mq.queue_length.return_value = 42
        mock_get.return_value = mock_mq

        resp = await mq_client.get("/api/mq/status/my_queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["queue"] == "my_queue"
        assert data["length"] == 42


@pytest.mark.asyncio
async def test_api_clear_queue(mq_client: AsyncClient):
    """DELETE /api/mq/{queue} 清空队列。"""
    with patch("backend.routers.mq.get_message_queue") as mock_get:
        mock_mq = AsyncMock()
        mock_mq.clear_queue.return_value = 10
        mock_get.return_value = mock_mq

        resp = await mq_client.delete("/api/mq/my_queue")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 10


@pytest.mark.asyncio
async def test_api_list_handlers(mq_client: AsyncClient):
    """GET /api/mq/handlers 列出已注册处理器。"""
    resp = await mq_client.get("/api/mq/handlers")
    assert resp.status_code == 200
    handlers = resp.json()["handlers"]
    assert "route_planning" in handlers
    assert "notification" in handlers
    assert "analytics" in handlers
