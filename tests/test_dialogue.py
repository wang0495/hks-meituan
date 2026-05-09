"""CityFlow 对话引擎测试。

测试场景：
- 创建会话
- 替换指令
- 节奏调整
- 预算调整
- 时间调整
- 重新规划
- 未知指令处理
- 轮次限制
"""

from __future__ import annotations

import pytest

from backend.services.dialogue import DialogueEngine, DialogueState

# ---------------------------------------------------------------------------
# Fixtures: 模拟 POI 数据
# ---------------------------------------------------------------------------


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


@pytest.fixture()
def pois() -> list[dict]:
    """5 个测试 POI。"""
    return [
        _make_poi(
            "p1",
            "珠海渔女",
            "文化",
            emotion_tags={
                "excitement": 0.3,
                "tranquility": 0.8,
                "sociability": 0.2,
                "culture_depth": 0.9,
                "surprise": 0.1,
                "physical_demand": 0.2,
            },
        ),
        _make_poi(
            "p2",
            "海滨公园",
            "自然",
            avg_price=0,
            emotion_tags={
                "excitement": 0.2,
                "tranquility": 0.7,
                "sociability": 0.4,
                "culture_depth": 0.0,
                "surprise": 0.1,
                "physical_demand": 0.3,
            },
        ),
        _make_poi(
            "p3",
            "情侣路美食街",
            "美食",
            avg_price=80,
            emotion_tags={
                "excitement": 0.6,
                "tranquility": 0.3,
                "sociability": 0.7,
                "culture_depth": 0.1,
                "surprise": 0.3,
                "physical_demand": 0.2,
            },
        ),
        _make_poi(
            "p4",
            "圆明新园",
            "文化",
            avg_price=50,
            emotion_tags={
                "excitement": 0.4,
                "tranquility": 0.6,
                "sociability": 0.3,
                "culture_depth": 0.8,
                "surprise": 0.3,
                "physical_demand": 0.3,
            },
        ),
        _make_poi(
            "p5",
            "长隆海洋王国",
            "娱乐",
            avg_price=200,
            emotion_tags={
                "excitement": 0.95,
                "tranquility": 0.0,
                "sociability": 0.8,
                "culture_depth": 0.1,
                "surprise": 0.9,
                "physical_demand": 0.6,
            },
        ),
    ]


@pytest.fixture()
def sample_intent() -> dict:
    """示例用户意图。"""
    return {
        "time": {"period": "全天", "start": "09:00", "end": "18:00"},
        "budget": {"per_person": 100, "type": "弹性"},
        "group": {"size": 2, "type": "情侣"},
        "preferences": {"culture": 0.6, "food": 0.4, "nature": 0.7, "social": 0.3},
        "pace": "平衡型",
        "hard_constraints": [],
    }


def _build_route(pois_list: list[dict]) -> dict:
    """用给定 POI 列表构建模拟路线（与 solve_route 输出结构一致）。"""
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


@pytest.fixture()
def engine() -> DialogueEngine:
    """每次测试用新的引擎实例。"""
    return DialogueEngine()


@pytest.fixture()
async def state(
    engine: DialogueEngine, pois: list[dict], sample_intent: dict
) -> DialogueState:
    """已创建好的会话状态（路线包含 p1, p2）。"""
    route = _build_route([pois[0], pois[1]])
    return await engine.create_session("test_session", route, sample_intent)


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------


class TestSessionManagement:
    """会话创建、获取、删除。"""

    @pytest.mark.asyncio
    async def test_create_session(
        self, engine: DialogueEngine, pois: list[dict], sample_intent: dict
    ) -> None:
        route = _build_route([pois[0]])
        state = await engine.create_session("s1", route, sample_intent)
        assert state.session_id == "s1"
        assert state.turn_count == 0
        assert await engine.get_session("s1") is state

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, engine: DialogueEngine) -> None:
        assert await engine.get_session("no_such") is None

    @pytest.mark.asyncio
    async def test_remove_session(
        self, engine: DialogueEngine, pois: list[dict], sample_intent: dict
    ) -> None:
        route = _build_route([pois[0]])
        await engine.create_session("s2", route, sample_intent)
        await engine.remove_session("s2")
        assert await engine.get_session("s2") is None


class TestDialogueState:
    """DialogueState 单元测试。"""

    def test_add_message(self, state: DialogueState) -> None:
        state.add_message("user", "你好")
        state.add_message("assistant", "你好！")
        assert len(state.history) == 2
        assert state.history[0]["role"] == "user"
        assert state.history[1]["content"] == "你好！"

    def test_turn_count_increment(self, state: DialogueState) -> None:
        assert not state.is_expired()
        state.turn_count = 10
        assert state.is_expired()


# ---------------------------------------------------------------------------
# 指令分类
# ---------------------------------------------------------------------------


class TestClassifyInstruction:
    """指令分类测试。"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("换掉珠海渔女", "replace"),
            ("不喜欢这个", "replace"),
            ("不要去这里", "replace"),
            ("太赶了", "pace"),
            ("想轻松点", "pace"),
            ("太贵了", "budget"),
            ("便宜一点", "budget"),
            ("早一点出发", "time"),
            ("晚上8点之前结束", "time"),
            ("不行重新来", "retry"),
            ("再来一个", "retry"),
            ("今天天气怎么样", "unknown"),
        ],
    )
    def test_classify(self, engine: DialogueEngine, text: str, expected: str) -> None:
        assert engine._classify_instruction(text) == expected


# ---------------------------------------------------------------------------
# 替换指令
# ---------------------------------------------------------------------------


class TestHandleReplace:
    """替换指令测试。"""

    @pytest.mark.asyncio
    async def test_replace_by_name(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """按名称替换景点。"""
        route = _build_route([pois[0], pois[1]])
        route["unused_candidates"] = [pois[2], pois[3]]
        await engine.create_session("s_replace", route, sample_intent)

        result = await engine.process_instruction("s_replace", "换掉珠海渔女")
        assert "changes_made" in result
        assert len(result["changes_made"]) == 1
        assert result["changes_made"][0]["type"] == "replace"
        assert result["changes_made"][0]["original"] == "珠海渔女"
        # 被换出的 POI 应回到候选池
        unused_ids = {p["id"] for p in result["route"]["unused_candidates"]}
        assert "p1" in unused_ids

    @pytest.mark.asyncio
    async def test_replace_by_index(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """按序号替换景点。"""
        route = _build_route([pois[0], pois[1]])
        route["unused_candidates"] = [pois[2], pois[3]]
        await engine.create_session("s_idx", route, sample_intent)

        result = await engine.process_instruction("s_idx", "换掉第1个")
        assert result["changes_made"][0]["original"] == "珠海渔女"

    @pytest.mark.asyncio
    async def test_replace_no_name(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """未指明要换哪个景点时，提示用户。"""
        route = _build_route([pois[0]])
        await engine.create_session("s_noname", route, sample_intent)

        result = await engine.process_instruction("s_noname", "换一个")
        assert "哪个景点" in result["reply"]
        assert result["changes_made"] == []

    @pytest.mark.asyncio
    async def test_replace_poi_not_in_route(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """指定的景点不在路线中，无法从指令中提取名称，提示用户。"""
        route = _build_route([pois[0]])
        await engine.create_session("s_notfound", route, sample_intent)

        result = await engine.process_instruction("s_notfound", "换掉长隆海洋王国")
        # "长隆海洋王国" 不在路线中，_extract_poi_name 返回 None → 提示用户
        assert "哪个景点" in result["reply"] or "没有找到" in result["reply"]

    @pytest.mark.asyncio
    async def test_replace_no_candidates(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """没有备选景点时。"""
        route = _build_route([pois[0]])
        route["unused_candidates"] = []
        await engine.create_session("s_nocand", route, sample_intent)

        result = await engine.process_instruction("s_nocand", "换掉珠海渔女")
        assert "没有其他" in result["reply"]


# ---------------------------------------------------------------------------
# 节奏调整
# ---------------------------------------------------------------------------


class TestHandlePace:
    """节奏调整测试。"""

    @pytest.mark.asyncio
    async def test_slow_down(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户要求放慢节奏。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_slow", route, sample_intent)

        result = await engine.process_instruction("s_slow", "太赶了，想轻松点")
        assert "轻松" in result["reply"]
        assert result["changes_made"][0]["type"] == "pace"
        assert result["changes_made"][0]["new_pace"] == "闲逛型"

    @pytest.mark.asyncio
    async def test_speed_up(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户要求加快节奏。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_fast", route, sample_intent)

        result = await engine.process_instruction("s_fast", "太慢了，紧凑点")
        assert "紧凑" in result["reply"]
        assert result["changes_made"][0]["new_pace"] == "特种兵型"


# ---------------------------------------------------------------------------
# 预算调整
# ---------------------------------------------------------------------------


class TestHandleBudget:
    """预算调整测试。"""

    @pytest.mark.asyncio
    async def test_reduce_budget(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户要求降低预算。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_cheap", route, sample_intent)

        result = await engine.process_instruction("s_cheap", "太贵了，便宜一点")
        assert result["changes_made"][0]["type"] == "budget"
        assert result["changes_made"][0]["new_budget"] == 80  # 100 * 0.8

    @pytest.mark.asyncio
    async def test_increase_budget(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户要求增加预算。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_rich", route, sample_intent)

        result = await engine.process_instruction("s_rich", "预算可以多一点")
        assert result["changes_made"][0]["new_budget"] == 130  # 100 * 1.3


# ---------------------------------------------------------------------------
# 时间调整
# ---------------------------------------------------------------------------


class TestHandleTime:
    """时间调整测试。"""

    @pytest.mark.asyncio
    async def test_earlier_start(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户要求提前出发。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_early", route, sample_intent)

        result = await engine.process_instruction("s_early", "早一点出发")
        assert "08:00" in result["reply"]
        assert result["changes_made"][0]["type"] == "time"

    @pytest.mark.asyncio
    async def test_specific_time(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户指定具体时间。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_spec", route, sample_intent)

        result = await engine.process_instruction("s_spec", "7点出发")
        assert "07:00" in result["reply"]

    @pytest.mark.asyncio
    async def test_end_before(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户要求某时间前结束。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_end", route, sample_intent)

        result = await engine.process_instruction("s_end", "下午5点之前结束")
        assert "17:00" in result["reply"]


# ---------------------------------------------------------------------------
# 重新规划
# ---------------------------------------------------------------------------


class TestHandleRetry:
    """重新规划测试。"""

    @pytest.mark.asyncio
    async def test_retry(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """用户不满意，要求重新规划。"""
        route = _build_route([pois[0], pois[1]])
        await engine.create_session("s_retry", route, sample_intent)

        result = await engine.process_instruction("s_retry", "不行，重新来")
        assert "重新" in result["reply"]
        assert result["changes_made"][0]["type"] == "retry"
        assert "route" in result


# ---------------------------------------------------------------------------
# 未知指令
# ---------------------------------------------------------------------------


class TestUnknownInstruction:
    """未知指令处理测试。"""

    @pytest.mark.asyncio
    async def test_unknown(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """无法识别的指令应返回帮助信息。"""
        route = _build_route([pois[0]])
        await engine.create_session("s_unknown", route, sample_intent)

        result = await engine.process_instruction("s_unknown", "今天天气怎么样")
        assert "抱歉" in result["reply"]
        assert "换掉" in result["reply"]
        assert result["changes_made"] == []


# ---------------------------------------------------------------------------
# 轮次限制
# ---------------------------------------------------------------------------


class TestTurnLimit:
    """轮次限制测试。"""

    @pytest.mark.asyncio
    async def test_expired_session(
        self,
        engine: DialogueEngine,
        pois: list[dict],
        sample_intent: dict,
    ) -> None:
        """超过最大轮次后应拒绝处理。"""
        from backend.errors import DialogueError

        route = _build_route([pois[0]])
        state = await engine.create_session("s_expire", route, sample_intent)
        state.max_turns = 2

        # 第1轮正常
        await engine.process_instruction("s_expire", "太赶了")
        # 第2轮正常
        await engine.process_instruction("s_expire", "便宜一点")
        # 第3轮应拒绝
        with pytest.raises(DialogueError, match="上限"):
            await engine.process_instruction("s_expire", "换掉珠海渔女")

    @pytest.mark.asyncio
    async def test_nonexistent_session(self, engine: DialogueEngine) -> None:
        """访问不存在的会话。"""
        from backend.errors import DialogueError

        with pytest.raises(DialogueError, match="不存在"):
            await engine.process_instruction("ghost", "你好")


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """模块级便捷函数测试。"""

    @pytest.mark.asyncio
    async def test_create_and_process(
        self, pois: list[dict], sample_intent: dict
    ) -> None:
        """通过便捷函数创建会话并处理指令。"""
        from backend.services.dialogue import create_dialogue, process_dialogue

        route = _build_route([pois[0], pois[1]])
        result = await create_dialogue("conv_test", route, sample_intent)
        assert result["session_id"] == "conv_test"

        result = await process_dialogue("conv_test", "想轻松点")
        assert "reply" in result
        assert "route" in result
