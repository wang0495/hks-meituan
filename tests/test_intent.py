"""
CityFlow 意图解析模块测试
覆盖 LLM 降级、规则匹配、画像匹配等场景。
"""

import asyncio
from unittest.mock import AsyncMock, patch

from backend.services.intent_parser import (PROFILES, _match_profile,
                                            _rule_based_parse, parse_intent)

# ---------------------------------------------------------------------------
# 辅助：运行 async 函数
# ---------------------------------------------------------------------------


def run(coro):
    """同步运行 async 函数的辅助。"""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 规则匹配测试
# ---------------------------------------------------------------------------


class TestRuleBasedParse:
    """测试关键词规则匹配降级方案。"""

    def test_social_anxiety(self):
        """社恐 → 低社交、低人流。"""
        result = _rule_based_parse("周末想出去走走，不想去人多的地方")
        assert result["preferences"]["social"] <= 0.2
        assert "低人流" in result["hard_constraints"]

    def test_pet_friendly(self):
        """宠物 → pet_friendly 约束。"""
        result = _rule_based_parse("带狗子出去转转")
        assert "pet_friendly" in result["hard_constraints"]

    def test_baby_stroller(self):
        """婴儿车 → accessible 约束。"""
        result = _rule_based_parse("推婴儿车出门逛逛")
        assert "accessible" in result["hard_constraints"]

    def test_couple_date(self):
        """情侣 → 双人、情侣类型。"""
        result = _rule_based_parse("和女朋友约会，想找有氛围的地方")
        assert result["group"]["type"] == "情侣"
        assert result["group"]["size"] == 2

    def test_family_with_kids(self):
        """亲子 → 儿童友好约束。"""
        result = _rule_based_parse("周末一家人带娃出去，让他消耗体力")
        assert result["group"]["type"] == "亲子"
        assert "儿童友好" in result["hard_constraints"]

    def test_morning_time(self):
        """上午时间解析。"""
        result = _rule_based_parse("上午去博物馆看看")
        assert result["time"]["period"] == "上午"
        assert result["time"]["start"] == "08:00"
        assert result["time"]["end"] == "12:00"

    def test_evening_time(self):
        """晚上时间解析。"""
        result = _rule_based_parse("晚上想去夜市逛逛")
        assert result["time"]["period"] == "晚上"

    def test_budget_extraction(self):
        """预算提取。"""
        result = _rule_based_parse("预算200元以内")
        assert result["budget"]["per_person"] == 200
        assert result["budget"]["type"] == "硬约束"

    def test_default_values(self):
        """无明确信息时的默认值。"""
        result = _rule_based_parse("想出去玩")
        assert result["time"]["period"] == "全天"
        assert result["budget"]["per_person"] == 500
        assert result["group"]["type"] == "独居"
        assert result["pace"] == "平衡型"

    def test_culture_preference(self):
        """文化偏好。"""
        result = _rule_based_parse("想去博物馆和历史古迹")
        assert result["preferences"]["culture"] >= 0.8

    def test_food_preference(self):
        """美食偏好。"""
        result = _rule_based_parse("想找好吃的餐厅探店")
        assert result["preferences"]["food"] >= 0.8


# ---------------------------------------------------------------------------
# 画像匹配测试
# ---------------------------------------------------------------------------


class TestMatchProfile:
    """测试画像模糊匹配。"""

    def test_match_social_anxiety(self):
        """社恐意图 → P1 或 P20。"""
        intent = {
            "group": {"type": "独居", "size": 1},
            "preferences": {"social": 0.1},
            "pace": "闲逛型",
            "hard_constraints": ["低人流"],
        }
        pid = _match_profile(intent, PROFILES)
        assert pid in ("P1", "P20"), f"期望 P1 或 P20，实际 {pid}"

    def test_match_family(self):
        """亲子意图 → P3 或 P11。"""
        intent = {
            "group": {"type": "亲子", "size": 3},
            "preferences": {"social": 0.6},
            "pace": "平衡型",
            "hard_constraints": ["儿童友好"],
        }
        pid = _match_profile(intent, PROFILES)
        assert pid in ("P3", "P11", "P17"), f"期望亲子画像，实际 {pid}"

    def test_match_pet(self):
        """宠物意图 → P12。"""
        intent = {
            "group": {"type": "独居", "size": 1},
            "preferences": {"social": 0.3},
            "pace": "闲逛型",
            "hard_constraints": ["pet_friendly"],
        }
        pid = _match_profile(intent, PROFILES)
        assert pid == "P12", f"期望 P12，实际 {pid}"

    def test_match_couple(self):
        """情侣意图 → P2。"""
        intent = {
            "group": {"type": "情侣", "size": 2},
            "preferences": {"social": 0.5},
            "pace": "平衡型",
            "hard_constraints": [],
        }
        pid = _match_profile(intent, PROFILES)
        assert pid == "P2", f"期望 P2，实际 {pid}"

    def test_match_friends_gathering(self):
        """朋友聚会 → P4 或 P19。"""
        intent = {
            "group": {"type": "朋友", "size": 5},
            "preferences": {"social": 0.9},
            "pace": "特种兵型",
            "hard_constraints": [],
        }
        pid = _match_profile(intent, PROFILES)
        assert pid in ("P4", "P19"), f"期望 P4 或 P19，实际 {pid}"

    def test_match_retired(self):
        """退休 → P5 或 P18。"""
        intent = {
            "group": {"type": "退休", "size": 2},
            "preferences": {"social": 0.3},
            "pace": "闲逛型",
            "hard_constraints": [],
        }
        pid = _match_profile(intent, PROFILES)
        assert pid in ("P5", "P18"), f"期望 P5 或 P18，实际 {pid}"


# ---------------------------------------------------------------------------
# 端到端集成测试（LLM 降级到规则匹配）
# ---------------------------------------------------------------------------


class TestParseIntentE2E:
    """
    端到端测试。
    模拟 LLM 超时，验证降级到规则匹配的完整流程。
    """

    @patch("backend.services.intent_parser._call_llm", new_callable=AsyncMock)
    def test_llm_timeout_fallback(self, mock_llm):
        """LLM 超时 → 降级为规则匹配。"""
        mock_llm.side_effect = asyncio.TimeoutError()

        result = run(parse_intent("周末想出去走走，不想去人多的地方"))

        assert result["preferences"]["social"] <= 0.2
        assert result["matched_profile_id"] in ("P1", "P20")
        assert "time" in result
        assert "budget" in result

    @patch("backend.services.intent_parser._call_llm", new_callable=AsyncMock)
    def test_llm_success(self, mock_llm):
        """LLM 正常返回 → 使用 LLM 结果。"""
        mock_llm.return_value = {
            "time": {"period": "全天", "start": "08:00", "end": "22:00"},
            "budget": {"per_person": 500, "type": "弹性"},
            "group": {"size": 2, "type": "情侣"},
            "preferences": {"culture": 0.5, "food": 0.6, "nature": 0.3, "social": 0.5},
            "pace": "平衡型",
            "hard_constraints": [],
        }

        result = run(parse_intent("和女朋友约会"))

        assert result["group"]["type"] == "情侣"
        assert result["matched_profile_id"] == "P2"

    @patch("backend.services.intent_parser._call_llm", new_callable=AsyncMock)
    def test_family_with_baby(self, mock_llm):
        """亲子场景端到端。"""
        mock_llm.side_effect = asyncio.TimeoutError()

        result = run(parse_intent("周末一家人带娃出去，让他消耗体力"))

        assert result["group"]["type"] == "亲子"
        assert result["matched_profile_id"] in ("P3", "P11", "P17")

    @patch("backend.services.intent_parser._call_llm", new_callable=AsyncMock)
    def test_pet_scenario(self, mock_llm):
        """宠物场景端到端。"""
        mock_llm.side_effect = asyncio.TimeoutError()

        result = run(parse_intent("带狗子出去转转"))

        assert "pet_friendly" in result["hard_constraints"]
        assert result["matched_profile_id"] == "P12"

    @patch("backend.services.intent_parser._call_llm", new_callable=AsyncMock)
    def test_couple_date_scenario(self, mock_llm):
        """情侣约会端到端。"""
        mock_llm.side_effect = asyncio.TimeoutError()

        result = run(parse_intent("和女朋友约会，想找有氛围的地方"))

        assert result["group"]["type"] == "情侣"
        assert result["matched_profile_id"] == "P2"

    @patch("backend.services.intent_parser._call_llm", new_callable=AsyncMock)
    def test_custom_profiles(self, mock_llm):
        """自定义画像库。"""
        mock_llm.side_effect = asyncio.TimeoutError()
        custom_profiles = {
            "X1": {
                "name": "测试画像",
                "group_type": "独居",
                "social": 0.1,
                "pace": "闲逛型",
                "keywords": ["测试"],
            },
        }

        result = run(parse_intent("一个人安静待着", available_profiles=custom_profiles))

        assert result["matched_profile_id"] == "X1"


# ---------------------------------------------------------------------------
# 画像库完整性测试
# ---------------------------------------------------------------------------


class TestProfiles:
    """验证画像库结构完整性。"""

    def test_all_profiles_have_required_fields(self):
        """所有画像包含必要字段。"""
        required = {"name", "group_type", "social", "pace"}
        for pid, profile in PROFILES.items():
            missing = required - set(profile.keys())
            assert not missing, f"{pid} 缺少字段: {missing}"

    def test_20_profiles_count(self):
        """画像数量为 20。"""
        assert len(PROFILES) == 20

    def test_social_range(self):
        """social 值在 0-1 范围内。"""
        for pid, profile in PROFILES.items():
            assert (
                0 <= profile["social"] <= 1
            ), f"{pid} social={profile['social']} 超出范围"

    def test_pace_values(self):
        """pace 只能是三种取值。"""
        valid_paces = {"特种兵型", "平衡型", "闲逛型"}
        for pid, profile in PROFILES.items():
            assert (
                profile["pace"] in valid_paces
            ), f"{pid} pace={profile['pace']} 不合法"
