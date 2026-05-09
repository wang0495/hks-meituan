"""对话持久化测试。

测试场景：
- DialogueState 序列化/反序列化 roundtrip
- DialoguePersistence save/load/delete
- DialogueEngine + Redis 持久化集成
- 重启后恢复会话
- Redis 不可用时回退到内存模式
"""

from __future__ import annotations

import pytest

from backend.services.dialogue import (
    DialogueEngine,
    DialoguePersistence,
    DialogueState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_redis_url() -> str:
    """返回 fakeredis 的模拟 URL（不会真正连接）。"""
    return "redis://localhost:63799/0"  # fakeredis 不校验连接


@pytest.fixture()
def persistence(fake_redis_url: str) -> DialoguePersistence:
    """新建 DialoguePersistence 实例（用 fakeredis）。"""
    return DialoguePersistence(redis_url=fake_redis_url)


@pytest.fixture()
def engine_with_persistence(persistence: DialoguePersistence) -> DialogueEngine:
    """带持久化的对话引擎。"""
    return DialogueEngine(persistence=persistence)


def _make_poi(poi_id: str, name: str, category: str = "文化", **kwargs) -> dict:
    """快速构建测试 POI。"""
    base = {
        "id": poi_id,
        "name": name,
        "category": category,
        "rating": 4.5,
        "avg_price": 30,
        "lat": 22.27,
        "lng": 113.58,
        "business_hours": "09:00-18:00",
        "tags": [],
        "queue_prone": False,
        "avg_stay_min": 60,
        "emotion_tags": {
            "excitement": 0.3,
            "tranquility": 0.7,
            "sociability": 0.3,
            "culture_depth": 0.5,
            "surprise": 0.2,
            "physical_demand": 0.3,
        },
        "constraints": {
            "accessible": True,
            "pet_friendly": False,
            "queue_time_min": 0,
            "opening_hours": "09:00-18:00",
            "has_restroom": True,
        },
    }
    base.update(kwargs)
    return base


def _build_route(pois_list: list[dict]) -> dict:
    """构建模拟路线。"""
    from datetime import datetime, timedelta

    route_steps = []
    current = datetime.strptime("09:00", "%H:%M")
    prev_poi = None

    for poi in pois_list:
        travel = 15 if prev_poi else 0
        arrival = current + timedelta(minutes=travel)
        stay = poi.get("avg_stay_min", 60)
        departure = arrival + timedelta(minutes=stay)

        route_steps.append(
            {
                "poi": poi,
                "arrival_time": arrival.strftime("%H:%M"),
                "departure_time": departure.strftime("%H:%M"),
                "travel_from_prev": {"distance_m": 1000, "time_min": travel},
            }
        )
        current = departure
        prev_poi = poi

    return {
        "route": route_steps,
        "emotion_curve": [],
        "total_cost": {"time_min": 300, "budget_used": 200, "step_estimate": 5000},
        "unused_candidates": [],
        "breathing_spots": [],
    }


def _sample_intent() -> dict:
    return {
        "time": {"period": "全天", "start": "09:00", "end": "18:00"},
        "budget": {"per_person": 100, "type": "弹性"},
        "group": {"size": 2, "type": "情侣"},
        "preferences": {"culture": 0.6, "food": 0.4, "nature": 0.7, "social": 0.3},
        "pace": "平衡型",
        "hard_constraints": [],
    }


# ---------------------------------------------------------------------------
# DialogueState 序列化
# ---------------------------------------------------------------------------


class TestDialogueStateSerialization:
    """T-F002-01: DialogueState 序列化/反序列化。"""

    def test_to_dict_roundtrip(self) -> None:
        """to_dict() → from_dict() 应完整恢复所有字段。"""
        route = _build_route([_make_poi("p1", "珠海渔女")])
        original = DialogueState("sid_001", route, _sample_intent())
        original.add_message("user", "你好")
        original.add_message("assistant", "你好！")
        original.turn_count = 3

        d = original.to_dict()
        restored = DialogueState.from_dict(d)

        assert restored.session_id == "sid_001"
        assert restored.turn_count == 3
        assert len(restored.history) == 2
        assert restored.history[0]["content"] == "你好"
        assert restored.route["route"][0]["poi"]["name"] == "珠海渔女"
        assert restored.created_at == original.created_at

    def test_from_dict_minimal(self) -> None:
        """from_dict 应能处理最小数据集（无 history、turn_count = 0）。"""
        route = _build_route([_make_poi("p1", "test")])
        data = {
            "session_id": "sid_min",
            "route": route,
            "user_intent": _sample_intent(),
        }
        state = DialogueState.from_dict(data)
        assert state.session_id == "sid_min"
        assert state.turn_count == 0
        assert state.history == []

    def test_to_dict_includes_timestamps(self) -> None:
        """to_dict 应包含 created_at 和 last_active。"""
        route = _build_route([_make_poi("p1", "test")])
        state = DialogueState("sid_ts", route, _sample_intent())
        d = state.to_dict()
        assert "created_at" in d
        assert "last_active" in d


# ---------------------------------------------------------------------------
# DialoguePersistence
# ---------------------------------------------------------------------------


class TestDialoguePersistence:
    """T-F002-02 / T-F002-03: Redis 持久化 + 回退。"""

    @pytest.mark.asyncio
    async def test_save_and_load(self, persistence: DialoguePersistence) -> None:
        """保存后应能从 Redis 读取。"""
        # 需要先 connect（fakeredis 模式下会成功）
        from fakeredis.aioredis import FakeRedis

        persistence._redis = FakeRedis(decode_responses=True)
        persistence._connected = True

        route = _build_route([_make_poi("p1", "test")])
        state = DialogueState("s_test", route, _sample_intent())
        state.add_message("user", "你好")

        ok = await persistence.save("s_test", state)
        assert ok is True

        data = await persistence.load("s_test")
        assert data is not None
        assert data["session_id"] == "s_test"
        assert len(data["history"]) == 1

    @pytest.mark.asyncio
    async def test_delete(self, persistence: DialoguePersistence) -> None:
        """删除后应返回 None。"""
        from fakeredis.aioredis import FakeRedis

        persistence._redis = FakeRedis(decode_responses=True)
        persistence._connected = True

        route = _build_route([_make_poi("p1", "test")])
        state = DialogueState("s_del", route, _sample_intent())
        await persistence.save("s_del", state)
        await persistence.delete("s_del")

        assert await persistence.load("s_del") is None

    @pytest.mark.asyncio
    async def test_fallback_on_no_redis(self, persistence: DialoguePersistence) -> None:
        """无 Redis 时 save/load 返回 False/None，不抛异常。"""
        # 不连接 Redis → _get_redis 返回 None
        ok = await persistence.save("s_none", DialogueState("s_none", {}, {}))
        assert ok is False
        assert persistence.is_fallback

        data = await persistence.load("s_none")
        assert data is None

    @pytest.mark.asyncio
    async def test_fallback_flag_reset(self, persistence: DialoguePersistence) -> None:
        """fallback 状态下不重试连接（避免重复失败）。"""
        persistence._fallback = True
        # 不应尝试连接
        r = await persistence._get_redis()
        assert r is None


# ---------------------------------------------------------------------------
# DialogueEngine + 持久化集成
# ---------------------------------------------------------------------------


class TestDialogueEngineWithPersistence:
    """T-F002-02: DialogueEngine + Redis 持久化集成。"""

    @pytest.mark.asyncio
    async def test_create_saves_to_redis(
        self, engine_with_persistence: DialogueEngine
    ) -> None:
        """创建会话时应持久化到 Redis。"""
        from fakeredis.aioredis import FakeRedis

        eng = engine_with_persistence
        # 注入 fakeredis
        eng._persistence._redis = FakeRedis(decode_responses=True)
        eng._persistence._connected = True

        route = _build_route([_make_poi("p1", "test")])
        await eng.create_session("s1", route, _sample_intent())

        # 验证 Redis 中已保存
        data = await eng._persistence.load("s1")
        assert data is not None
        assert data["session_id"] == "s1"

    @pytest.mark.asyncio
    async def test_restore_after_restart(
        self, engine_with_persistence: DialogueEngine
    ) -> None:
        """清理内存后，能从 Redis 恢复会话。"""
        from fakeredis.aioredis import FakeRedis

        eng = engine_with_persistence
        eng._persistence._redis = FakeRedis(decode_responses=True)
        eng._persistence._connected = True

        route = _build_route([_make_poi("p1", "test")])
        await eng.create_session("s_restore", route, _sample_intent())

        # 模拟重启（清理内存）
        eng.sessions.clear()

        # 恢复
        state = await eng.get_session("s_restore")
        assert state is not None
        assert state.session_id == "s_restore"

    @pytest.mark.asyncio
    async def test_process_instruction_persists(
        self, engine_with_persistence: DialogueEngine
    ) -> None:
        """处理指令后状态应持久化到 Redis。"""
        from fakeredis.aioredis import FakeRedis

        eng = engine_with_persistence
        eng._persistence._redis = FakeRedis(decode_responses=True)
        eng._persistence._connected = True

        route = _build_route([_make_poi("p1", "test")])
        await eng.create_session("s_proc", route, _sample_intent())

        # 处理一条指令
        await eng.process_instruction("s_proc", "早一点出发")

        # 验证 Redis 中 turn_count 递增
        data = await eng._persistence.load("s_proc")
        assert data is not None
        assert data["turn_count"] >= 1

    @pytest.mark.asyncio
    async def test_engine_fallback_on_redis_fail(
        self, engine_with_persistence: DialogueEngine
    ) -> None:
        """Redis 不可用时引擎应回退到内存模式。"""
        eng = engine_with_persistence
        # 不注入 fakeredis → 连接失败 → fallback
        route = _build_route([_make_poi("p1", "test")])

        # 即使没有 Redis，创建会话仍应工作
        await eng.create_session("s_fallback", route, _sample_intent())
        state = await eng.get_session("s_fallback")
        assert state is not None
        assert state.session_id == "s_fallback"
