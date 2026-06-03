"""F004 三层记忆系统测试。

测试场景:
- L1 WorkingMemory: set/get/get_all/clear + fallback
- L2 ShortTermMemory: add_trip/get_recent_trips/trimming + fallback
- L3 LongTermMemory: get_profile/update_preference/record_visit + fallback
- PsychologyRules: peak_end/hedonic_adaptation/loss_aversion/choice_overload
- MemoryOrchestrator: on_trip_completed/apply_psychology
"""

from __future__ import annotations

import pytest

from backend.services.memory import MemoryOrchestrator
from backend.services.memory.long_term import LongTermMemory
from backend.services.memory.psychology import PsychologyRules
from backend.services.memory.short_term import ShortTermMemory
from backend.services.memory.working_memory import WorkingMemory

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_step(
    name: str,
    excitement: float = 0.5,
    price: int = 50,
    category: str = "文化",
    **extra_emotions,
) -> dict:
    """构建模拟路线步骤。"""
    poi = {
        "id": f"poi_{name}",
        "name": name,
        "category": category,
        "avg_price": price,
        "emotion_tags": {
            "excitement": excitement,
            "tranquility": 0.5,
            "sociability": 0.5,
            "culture_depth": 0.5,
            "surprise": 0.5,
            "physical_demand": 0.5,
            **extra_emotions,
        },
    }
    return {
        "poi": poi,
        "arrival_time": "09:00",
        "departure_time": "10:00",
        "travel_from_prev": {"distance_m": 1000, "time_min": 15},
    }


def _trip_summary(destination: str = "珠海") -> dict:
    """构建模拟行程摘要。"""
    return {
        "destination": destination,
        "date": "2026-05-09",
        "pois_visited": ["POI_A", "POI_B"],
        "emotion_summary": {"excitement": 0.6, "tranquility": 0.4},
        "route": [
            _make_step("POI_A", excitement=0.7, price=30, category="自然"),
            _make_step("POI_B", excitement=0.4, price=80, category="美食"),
        ],
    }


# ---------------------------------------------------------------------------
# L1: WorkingMemory
# ---------------------------------------------------------------------------


class TestWorkingMemory:
    """T-F004-01: WorkingMemory 基本操作。"""

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        """设置后应能读取到相同值。"""
        wm = WorkingMemory()
        await wm.set("session_1", "last_intent", "想去海边")
        value = await wm.get("session_1", "last_intent")
        assert value == "想去海边"

    @pytest.mark.asyncio
    async def test_get_all(self) -> None:
        """get_all 返回所有字段。"""
        wm = WorkingMemory()
        await wm.set("session_1", "key1", "val1")
        await wm.set("session_1", "key2", 42)
        await wm.set("session_1", "key3", {"nested": True})
        all_data = await wm.get_all("session_1")
        assert all_data == {"key1": "val1", "key2": 42, "key3": {"nested": True}}

    @pytest.mark.asyncio
    async def test_get_nonexistent(self) -> None:
        """不存在的 key 返回 None。"""
        wm = WorkingMemory()
        value = await wm.get("session_1", "nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """clear 后 get_all 返回空。"""
        wm = WorkingMemory()
        await wm.set("session_1", "key", "val")
        await wm.clear("session_1")
        all_data = await wm.get_all("session_1")
        assert all_data == {}

    @pytest.mark.asyncio
    async def test_session_isolation(self) -> None:
        """不同 session 的数据应隔离。"""
        wm = WorkingMemory()
        await wm.set("session_a", "key", "value_a")
        await wm.set("session_b", "key", "value_b")
        assert await wm.get("session_a", "key") == "value_a"
        assert await wm.get("session_b", "key") == "value_b"

    @pytest.mark.asyncio
    async def test_fallback_on_no_redis(self) -> None:
        """无 Redis 时 set/get 正常工作（内存回退）。"""
        wm = WorkingMemory()
        await wm.set("sess", "key", "fallback_val")
        value = await wm.get("sess", "key")
        assert value == "fallback_val"
        assert wm.is_fallback is False  # 没有 redis_url 不算 fallback，只是不使用

    @pytest.mark.asyncio
    async def test_redis_operations(self) -> None:
        """使用 FakeRedis 时，set/get/clear 正常工作。"""
        from fakeredis.aioredis import FakeRedis

        wm = WorkingMemory()
        wm._redis = FakeRedis(decode_responses=True)
        wm._connected = True

        await wm.set("s_redis", "intent", "测试意图")
        value = await wm.get("s_redis", "intent")
        assert value == "测试意图"

        all_data = await wm.get_all("s_redis")
        assert all_data == {"intent": "测试意图"}

        await wm.clear("s_redis")
        assert await wm.get_all("s_redis") == {}

    @pytest.mark.asyncio
    async def test_redis_complex_value(self) -> None:
        """FakeRedis 模式下 JSON 序列化/反序列化正常工作。"""
        from fakeredis.aioredis import FakeRedis

        wm = WorkingMemory()
        wm._redis = FakeRedis(decode_responses=True)
        wm._connected = True

        complex_val = {
            "preferences": {"culture": 0.8, "food": 0.6},
            "emotion": {"excitement": 0.7},
        }
        await wm.set("s_complex", "profile", complex_val)
        value = await wm.get("s_complex", "profile")
        assert value == complex_val


# ---------------------------------------------------------------------------
# L2: ShortTermMemory
# ---------------------------------------------------------------------------


class TestShortTermMemory:
    """T-F004-02: ShortTermMemory 基本操作。"""

    @pytest.mark.asyncio
    async def test_add_and_get_recent(self) -> None:
        """添加行程后应能获取到最近的行程。"""
        stm = ShortTermMemory()
        trip1 = _trip_summary("珠海")
        trip2 = _trip_summary("广州")

        await stm.add_trip("user_1", trip1)
        await stm.add_trip("user_1", trip2)

        trips = await stm.get_recent_trips("user_1", n=2)
        assert len(trips) == 2
        # 最近添加的在最前面
        assert trips[0]["destination"] == "广州"
        assert trips[1]["destination"] == "珠海"

    @pytest.mark.asyncio
    async def test_get_last_trip(self) -> None:
        """get_last_trip 返回最近一次行程。"""
        stm = ShortTermMemory()
        trip1 = _trip_summary("珠海")
        trip2 = _trip_summary("广州")

        await stm.add_trip("user_1", trip1)
        await stm.add_trip("user_1", trip2)

        last = await stm.get_last_trip("user_1")
        assert last is not None
        assert last["destination"] == "广州"

    @pytest.mark.asyncio
    async def test_get_last_trip_empty(self) -> None:
        """无行程时 get_last_trip 返回 None。"""
        stm = ShortTermMemory()
        assert await stm.get_last_trip("no_user") is None

    @pytest.mark.asyncio
    async def test_get_recent_empty(self) -> None:
        """无行程时 get_recent_trips 返回空列表。"""
        stm = ShortTermMemory()
        assert await stm.get_recent_trips("no_user") == []

    @pytest.mark.asyncio
    async def test_trimming_at_five(self) -> None:
        """添加超过 5 次行程时，最旧的应被裁剪。"""
        stm = ShortTermMemory()

        for i in range(7):
            await stm.add_trip("user_trim", _trip_summary(f"Trip_{i}"))

        trips = await stm.get_recent_trips("user_trim", n=10)
        assert len(trips) == 5
        # 最近 5 个：Trip_6, Trip_5, Trip_4, Trip_3, Trip_2
        assert trips[0]["destination"] == "Trip_6"
        assert trips[-1]["destination"] == "Trip_2"

    @pytest.mark.asyncio
    async def test_get_recent_n(self) -> None:
        """get_recent_trips(2) 只返回最近 2 个。"""
        stm = ShortTermMemory()
        for i in range(4):
            await stm.add_trip("user_n", _trip_summary(f"Trip_{i}"))

        trips = await stm.get_recent_trips("user_n", n=2)
        assert len(trips) == 2
        assert trips[0]["destination"] == "Trip_3"
        assert trips[1]["destination"] == "Trip_2"

    @pytest.mark.asyncio
    async def test_redis_operations(self) -> None:
        """使用 FakeRedis 时，add_trip/get_recent 正常工作。"""
        from fakeredis.aioredis import FakeRedis

        stm = ShortTermMemory()
        stm._redis = FakeRedis(decode_responses=True)
        stm._connected = True

        await stm.add_trip("user_r", _trip_summary("First"))
        await stm.add_trip("user_r", _trip_summary("Second"))

        trips = await stm.get_recent_trips("user_r", n=5)
        assert len(trips) == 2
        assert trips[0]["destination"] == "Second"
        assert trips[1]["destination"] == "First"

    @pytest.mark.asyncio
    async def test_redis_trimming(self) -> None:
        """FakeRedis 模式下，自动裁剪到 5 条。"""
        from fakeredis.aioredis import FakeRedis

        stm = ShortTermMemory()
        stm._redis = FakeRedis(decode_responses=True)
        stm._connected = True

        for i in range(8):
            await stm.add_trip("user_trim_r", _trip_summary(f"T{i}"))

        trips = await stm.get_recent_trips("user_trim_r", n=10)
        assert len(trips) == 5

    @pytest.mark.asyncio
    async def test_redis_last_trip(self) -> None:
        """FakeRedis 模式下，get_last_trip 正确返回。"""
        from fakeredis.aioredis import FakeRedis

        stm = ShortTermMemory()
        stm._redis = FakeRedis(decode_responses=True)
        stm._connected = True

        await stm.add_trip("user_lr", _trip_summary("Trip_A"))
        await stm.add_trip("user_lr", _trip_summary("Trip_B"))

        last = await stm.get_last_trip("user_lr")
        assert last is not None
        assert last["destination"] == "Trip_B"


# ---------------------------------------------------------------------------
# L3: LongTermMemory
# ---------------------------------------------------------------------------


class TestLongTermMemory:
    """T-F004-03: LongTermMemory 基本操作。"""

    @pytest.mark.asyncio
    async def test_get_profile_new_user(self) -> None:
        """新用户应返回默认画像。"""
        ltm = LongTermMemory()
        profile = await ltm.get_profile("new_user")
        assert profile["preferences"] == {}
        assert profile["category_visits"] == {}
        assert profile["visit_count"] == 0
        assert profile["total_spent"] == 0
        assert profile["emotion_history"] == []

    @pytest.mark.asyncio
    async def test_update_preference(self) -> None:
        """更新偏好后应能读取到新值。"""
        ltm = LongTermMemory()
        await ltm.update_preference("user_pref", "culture", 0.85)
        await ltm.update_preference("user_pref", "food", 0.6)

        profile = await ltm.get_profile("user_pref")
        assert profile["preferences"]["culture"] == 0.85
        assert profile["preferences"]["food"] == 0.6

    @pytest.mark.asyncio
    async def test_record_visit(self) -> None:
        """记录访问后统计信息应更新。"""
        ltm = LongTermMemory()
        await ltm.record_visit("user_v", "文化", 50, "culture_depth")

        profile = await ltm.get_profile("user_v")
        assert profile["visit_count"] == 1
        assert profile["total_spent"] == 50
        assert profile["category_visits"]["文化"] == 1
        assert len(profile["emotion_history"]) == 1

    @pytest.mark.asyncio
    async def test_record_multiple_visits(self) -> None:
        """多次访问应正确累计。"""
        ltm = LongTermMemory()
        await ltm.record_visit("user_m", "自然", 0, "tranquility")
        await ltm.record_visit("user_m", "美食", 80, "excitement")
        await ltm.record_visit("user_m", "美食", 60, "excitement")

        profile = await ltm.get_profile("user_m")
        assert profile["visit_count"] == 3
        assert profile["total_spent"] == 140
        assert profile["category_visits"] == {"自然": 1, "美食": 2}

    @pytest.mark.asyncio
    async def test_get_statistics(self) -> None:
        """get_statistics 返回正确的统计摘要。"""
        ltm = LongTermMemory()
        await ltm.record_visit("user_s", "自然", 0, "tranquility")
        await ltm.record_visit("user_s", "美食", 80, "excitement")
        await ltm.record_visit("user_s", "美食", 60, "excitement")

        stats = await ltm.get_statistics("user_s")
        assert stats["visit_count"] == 3
        assert stats["total_spent"] == 140
        assert stats["most_visited_category"] == "美食"
        assert stats["average_spending"] == round(140 / 3, 2)

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self) -> None:
        """无访问记录时统计值应为 0。"""
        ltm = LongTermMemory()
        stats = await ltm.get_statistics("empty_user")
        assert stats["visit_count"] == 0
        assert stats["total_spent"] == 0
        assert stats["most_visited_category"] is None
        assert stats["average_spending"] == 0.0

    @pytest.mark.asyncio
    async def test_redis_operations(self) -> None:
        """使用 FakeRedis 时，get_profile/record_visit 正常工作。"""
        from fakeredis.aioredis import FakeRedis

        ltm = LongTermMemory()
        ltm._redis = FakeRedis(decode_responses=True)
        ltm._connected = True

        # 新用户
        profile = await ltm.get_profile("redis_user")
        assert profile["visit_count"] == 0

        # 记录访问
        await ltm.record_visit("redis_user", "文化", 30, "culture_depth")
        await ltm.record_visit("redis_user", "自然", 0, "tranquility")

        profile = await ltm.get_profile("redis_user")
        assert profile["visit_count"] == 2
        assert profile["total_spent"] == 30
        assert profile["category_visits"] == {"文化": 1, "自然": 1}

        stats = await ltm.get_statistics("redis_user")
        assert stats["most_visited_category"] == "文化"

    @pytest.mark.asyncio
    async def test_redis_update_preference(self) -> None:
        """FakeRedis 模式下 update_preference 正确。"""
        from fakeredis.aioredis import FakeRedis

        ltm = LongTermMemory()
        ltm._redis = FakeRedis(decode_responses=True)
        ltm._connected = True

        await ltm.update_preference("ru", "nature", 0.9)
        await ltm.update_preference("ru", "social", 0.2)

        profile = await ltm.get_profile("ru")
        assert profile["preferences"]["nature"] == 0.9
        assert profile["preferences"]["social"] == 0.2


# ---------------------------------------------------------------------------
# PsychologyRules
# ---------------------------------------------------------------------------


class TestPsychologyRules:
    """T-F004-04: 心理学规则。"""

    def test_peak_end_last_poi_bonus(self) -> None:
        """终点 POI 应获得 +20% 加成。"""
        route = [
            _make_step("A", excitement=0.3),
            _make_step("B", excitement=0.3),
            _make_step("C", excitement=0.3),
        ]
        scores = [1.0, 1.0, 1.0]
        result = PsychologyRules.apply_peak_end(route, scores)
        # 最后一段 +20%
        assert result[2] == pytest.approx(1.20)
        # 其它不变（所有情绪相同，取第一个最高为 idx 0，+15%）
        assert result[0] == pytest.approx(1.15)
        assert result[1] == pytest.approx(1.0)

    def test_peak_end_highest_emotion_bonus(self) -> None:
        """情绪综合评分最高的 POI 应获得 +15% 加成。"""
        route = [
            _make_step("A", excitement=0.3),
            _make_step("B", excitement=0.9),  # 综合情绪最高
            _make_step("C", excitement=0.3),
        ]
        scores = [1.0, 1.0, 1.0]
        result = PsychologyRules.apply_peak_end(route, scores)
        # 中间 POI 综合情绪最高 → +15%, 终点 +20%
        assert result[1] == pytest.approx(1.15)
        assert result[2] == pytest.approx(1.20)
        assert result[0] == pytest.approx(1.0)

    def test_peak_end_same_poi_both_bonus(self) -> None:
        """当最高情绪 POI 同时也是终点时，两加成叠加。"""
        route = [
            _make_step("A", excitement=0.3),
            _make_step("B", excitement=0.9),  # 最高 + 终点
        ]
        scores = [1.0, 1.0]
        result = PsychologyRules.apply_peak_end(route, scores)
        # 1.0 * 1.2 * 1.15 = 1.38
        assert result[1] == pytest.approx(1.38)
        assert result[0] == pytest.approx(1.0)

    def test_peak_end_empty(self) -> None:
        """空输入应返回空列表。"""
        assert PsychologyRules.apply_peak_end([], []) == []

    def test_hedonic_adaptation_discount(self) -> None:
        """连续 4 个高兴奋度 POI，第 4 个应折扣 30%。"""
        route = [
            _make_step("A", excitement=0.7),
            _make_step("B", excitement=0.8),
            _make_step("C", excitement=0.7),
            _make_step("D", excitement=0.9),  # 第 4 个连续 → 折扣 30%
            _make_step("E", excitement=0.3),  # 重置
        ]
        scores = [1.0, 1.0, 1.0, 1.0, 1.0]
        result = PsychologyRules.apply_hedonic_adaptation(route, scores)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(1.0)
        assert result[3] == pytest.approx(0.7)  # 1.0 * 0.7
        assert result[4] == pytest.approx(1.0)

    def test_hedonic_adaptation_no_discount(self) -> None:
        """非连续高兴奋度不应触发折扣。"""
        route = [
            _make_step("A", excitement=0.7),
            _make_step("B", excitement=0.3),  # 中断
            _make_step("C", excitement=0.7),
            _make_step("D", excitement=0.8),
            _make_step("E", excitement=0.7),
        ]
        scores = [1.0, 1.0, 1.0, 1.0, 1.0]
        result = PsychologyRules.apply_hedonic_adaptation(route, scores)
        assert result == [1.0, 1.0, 1.0, 1.0, 1.0]

    def test_hedonic_adaptation_short_route(self) -> None:
        """路线不足 4 个 POI 时不应触发。"""
        route = [_make_step("A", excitement=0.7), _make_step("B", excitement=0.8)]
        scores = [1.0, 1.0]
        result = PsychologyRules.apply_hedonic_adaptation(route, scores)
        assert result == [1.0, 1.0]

    def test_hedonic_adaptation_multiple_batches(self) -> None:
        """连续 7 个高兴奋度，第 4 和第 7 个应折扣。"""
        route = [_make_step(f"P{i}", excitement=0.8) for i in range(7)]
        scores = [1.0] * 7
        result = PsychologyRules.apply_hedonic_adaptation(route, scores)
        # 索引 3 和 6 受到折扣（第 4 和第 7 个连续高）
        assert result[3] == pytest.approx(0.7)
        assert result[6] == pytest.approx(0.7)

    def test_loss_aversion_penalty(self) -> None:
        """价格波动 > 30% 应触发 -0.1 惩罚。"""
        route = [
            _make_step("A", price=100),
            _make_step("B", price=100),
            _make_step("C", price=50),  # 偏离 50%
            _make_step("D", price=150),  # 偏离 50%
        ]
        scores = [1.0, 1.0, 1.0, 1.0]
        result = PsychologyRules.apply_loss_aversion(route, scores)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(0.9)  # 1.0 - 0.1
        assert result[3] == pytest.approx(0.9)  # 1.0 - 0.1

    def test_loss_aversion_no_penalty(self) -> None:
        """价格波动 ≤ 30% 不应触发惩罚。"""
        route = [
            _make_step("A", price=100),
            _make_step("B", price=110),  # 10% 偏离
            _make_step("C", price=90),  # 10% 偏离
        ]
        scores = [1.0, 1.0, 1.0]
        result = PsychologyRules.apply_loss_aversion(route, scores)
        assert result == [1.0, 1.0, 1.0]

    def test_loss_aversion_all_free(self) -> None:
        """全部免费景点不应触发惩罚。"""
        route = [
            _make_step("A", price=0),
            _make_step("B", price=0),
        ]
        scores = [1.0, 1.0]
        result = PsychologyRules.apply_loss_aversion(route, scores)
        assert result == [1.0, 1.0]

    def test_loss_aversion_mixed_free(self) -> None:
        """混合免费和付费景点，应以付费景点均价为基准。"""
        route = [
            _make_step("A", price=0),  # 免费，不参与基准计算
            _make_step("B", price=100),  # 基准
            _make_step("C", price=100),  # 基准
            _make_step("D", price=50),  # 偏离 50%
        ]
        scores = [1.0, 1.0, 1.0, 1.0]
        result = PsychologyRules.apply_loss_aversion(route, scores)
        # 均价 = 100，D 偏离 50% → 惩罚
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(1.0)
        assert result[3] == pytest.approx(0.9)

    def test_choice_overload_cutoff(self) -> None:
        """候选列表超过 5 个时只返回前 5 个。"""
        candidates = [{"name": f"POI_{i}"} for i in range(12)]
        result = PsychologyRules.apply_choice_overload(candidates)
        assert len(result) == 5

    def test_choice_overload_under_limit(self) -> None:
        """候选列表少于 5 个时全部返回。"""
        candidates = [{"name": f"POI_{i}"} for i in range(3)]
        result = PsychologyRules.apply_choice_overload(candidates)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# MemoryOrchestrator 集成
# ---------------------------------------------------------------------------


class TestMemoryOrchestrator:
    """T-F004-05: MemoryOrchestrator 集成。"""

    @pytest.mark.asyncio
    async def test_get_working_returns_instance(self) -> None:
        """get_working 返回 WorkingMemory 实例。"""
        orch = MemoryOrchestrator()
        wm = await orch.get_working("session_x")
        assert isinstance(wm, WorkingMemory)

    @pytest.mark.asyncio
    async def test_get_short_term_returns_instance(self) -> None:
        """get_short_term 返回 ShortTermMemory 实例。"""
        orch = MemoryOrchestrator()
        stm = await orch.get_short_term("user_x")
        assert isinstance(stm, ShortTermMemory)

    @pytest.mark.asyncio
    async def test_get_long_term_returns_instance(self) -> None:
        """get_long_term 返回 LongTermMemory 实例。"""
        orch = MemoryOrchestrator()
        ltm = await orch.get_long_term("user_x")
        assert isinstance(ltm, LongTermMemory)

    @pytest.mark.asyncio
    async def test_on_trip_completed_updates_both(self) -> None:
        """行程完成时 short-term 和 long-term 都应更新。"""
        orch = MemoryOrchestrator()
        trip = _trip_summary("珠海")

        await orch.on_trip_completed(
            user_id="u_complete",
            session_id="s_complete",
            trip_summary=trip,
        )

        # L2 应包含行程
        stm = await orch.get_short_term("u_complete")
        last = await stm.get_last_trip("u_complete")
        assert last is not None
        assert last["destination"] == "珠海"

        # L3 应包含访问记录
        ltm = await orch.get_long_term("u_complete")
        stats = await ltm.get_statistics("u_complete")
        # 2 个 POI (POI_A, POI_B)
        assert stats["visit_count"] == 2
        assert stats["category_visits"]["自然"] == 1
        assert stats["category_visits"]["美食"] == 1

    @pytest.mark.asyncio
    async def test_apply_psychology_runs_all_rules(self) -> None:
        """apply_psychology 应运行所有 3 个心理学规则。"""
        orch = MemoryOrchestrator()
        route = [
            _make_step("A", excitement=0.7, price=100),
            _make_step("B", excitement=0.8, price=100),
            _make_step("C", excitement=0.7, price=100),
            _make_step("D", excitement=0.9, price=50),  # 第4个高兴奋度 + 价格波动
        ]
        scores = [1.0, 1.0, 1.0, 1.0]

        result = await orch.apply_psychology(route, scores)

        # 享乐适应: D 有 4 个连续高兴奋度 → 折扣 30%
        # 损失厌恶: D 价格 50 偏离 100 的 50% → -0.1
        # 峰终: D 是终点 → +20%
        # 峰终: 情绪综合最高 → B 或 D → +15%（实际 D 情绪最高 0.9）
        # D = 1.0 * 0.7 (适应) - 0.1 (损失) * 1.2 (终点) * 1.15 (峰)
        # 实际计算顺序: 峰终先 → D=1.38 → 享乐适应 → D=0.966 → 损失厌恶 → D=0.866
        # Wait, 顺序是 peak_end → hedonic → loss_aversion

        # Peak-End: last(D) * 1.2 = 1.2, highest_emotion(D) * 1.15 = 1.38
        # Hedonic: consecutive 4 (D is 4th) → D * 0.7 = 0.966
        # Loss: D * ? - 0.1 = 0.866

        # Let me check:
        # Peak: scores = [1.0, 1.0, 1.0, 1.0]
        # R0=1.0, R1=1.0, R2=1.0, R3=1.0
        # Last: R3 = 1.2
        # Emotion max: D (0.9 avg based on ALL emotion_tags: 0.9/0.5/0.5/0.5/0.5/0.5 ... wait
        # Actually _make_step creates emotion_tags with {excitement: 0.9, tranquility: 0.5, ...}
        # So avg for D = (0.9 + 0.5 + 0.5 + 0.5 + 0.5 + 0.5)/6 = 3.4/6 = 0.5666
        # For B: (0.8 + 0.5 + 0.5 + 0.5 + 0.5 + 0.5)/6 = 3.3/6 = 0.55
        # So D still has highest avg emotion.
        # Peak: R3 = 1.0 * 1.2 = 1.2, R3 (max emotion) = 1.2 * 1.15 = 1.38
        # R0=1.0, R1=1.0, R2=1.0, R3=1.38
        # Hedonic: R0(exc=0.7)→1, R1(0.8)→2, R2(0.7)→3, R3(0.9)→4→ *0.7=R3=0.966
        # R0=1.0, R1=1.0, R2=1.0, R3=0.966
        # Loss: avg = (100+100+100+50)/4 = 87.5
        # R0: |100-87.5|/87.5 = 0.143 < 0.3 → 1.0
        # R1: same → 1.0
        # R2: same → 1.0
        # R3: |50-87.5|/87.5 = 0.429 > 0.3 → 0.966 - 0.1 = 0.866
        # Result: [1.0, 1.0, 1.0, 0.866]

        assert len(result) == 4
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(1.0)
        assert result[3] == pytest.approx(0.866, rel=1e-2)

    @pytest.mark.asyncio
    async def test_multiple_trips_completed(self) -> None:
        """多次完成行程应正确累计。"""
        orch = MemoryOrchestrator()

        trip1 = _trip_summary("珠海")
        trip2 = _trip_summary("广州")

        await orch.on_trip_completed(user_id="u_multi", session_id="s1", trip_summary=trip1)
        await orch.on_trip_completed(user_id="u_multi", session_id="s2", trip_summary=trip2)

        # L2: 应有 2 次行程
        stm = await orch.get_short_term("u_multi")
        trips = await stm.get_recent_trips("u_multi", n=5)
        assert len(trips) == 2
        # L3: 应有 4 个 POI 访问记录
        ltm = await orch.get_long_term("u_multi")
        stats = await ltm.get_statistics("u_multi")
        assert stats["visit_count"] == 4
