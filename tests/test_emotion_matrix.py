"""F008: 测试情绪化学反应矩阵 + 感官交替 (D5-D6)."""

from __future__ import annotations

import pytest

from backend.services.emotion import (SENSORY_TAGS, chemical_reaction,
                                      sensory_alternation)


# ===========================================================================
# chemical_reaction 测试
# ===========================================================================


def test_chemical_reaction_cognitive_overload():
    """认知超载型: culture_depth > 0.6 → sociability > 0.6 → -0.6."""
    poi_a = {
        "category": "文化",
        "emotion_tags": {"culture_depth": 0.8, "sociability": 0.2},
    }
    poi_b = {
        "category": "餐饮",
        "emotion_tags": {"culture_depth": 0.1, "sociability": 0.9},
    }
    assert chemical_reaction(poi_a, poi_b) == -0.6


def test_chemical_reaction_complement():
    """互补型: poi_a.excitement > 0.7 AND poi_b.tranquility > 0.7 → +0.2."""
    poi_a = {
        "category": "运动",
        "emotion_tags": {"excitement": 0.8, "tranquility": 0.1},
    }
    poi_b = {
        "category": "文化",
        "emotion_tags": {"excitement": 0.2, "tranquility": 0.9},
    }
    assert chemical_reaction(poi_a, poi_b) == 0.2


def test_chemical_reaction_scene_food_to_culture():
    """场景型: 餐饮→文化 → +0.5."""
    poi_a = {
        "category": "美食",
        "emotion_tags": {"excitement": 0.5, "tranquility": 0.3},
    }
    poi_b = {
        "category": "文化",
        "emotion_tags": {"excitement": 0.3, "tranquility": 0.6},
    }
    assert chemical_reaction(poi_a, poi_b) == 0.5


def test_chemical_reaction_scene_sport_to_food():
    """场景型: 运动→餐饮 → +0.5."""
    poi_a = {
        "category": "运动",
        "emotion_tags": {"excitement": 0.7, "tranquility": 0.2},
    }
    poi_b = {
        "category": "美食",
        "emotion_tags": {"excitement": 0.4, "tranquility": 0.3},
    }
    assert chemical_reaction(poi_a, poi_b) == 0.5


def test_chemical_reaction_default():
    """默认: 无匹配条件 → 0.0."""
    poi_a = {
        "category": "购物",
        "emotion_tags": {"excitement": 0.3, "culture_depth": 0.2},
    }
    poi_b = {
        "category": "运动",
        "emotion_tags": {"excitement": 0.4, "sociability": 0.3},
    }
    assert chemical_reaction(poi_a, poi_b) == 0.0


def test_chemical_reaction_same_category_no_match():
    """同category但无化学反应条件 → 0.0."""
    poi_a = {
        "category": "文化",
        "emotion_tags": {"excitement": 0.3, "tranquility": 0.5, "culture_depth": 0.3},
    }
    poi_b = {
        "category": "文化",
        "emotion_tags": {"excitement": 0.4, "tranquility": 0.5, "culture_depth": 0.4},
    }
    assert chemical_reaction(poi_a, poi_b) == 0.0


def test_chemical_reaction_precedence_cognitive_over_scene():
    """认知超载优先于场景型: culture_depth→sociability 即使符合场景规则也返回 -0.6."""
    poi_a = {
        "category": "餐饮",
        "emotion_tags": {"culture_depth": 0.8, "sociability": 0.2},
    }
    poi_b = {
        "category": "文化",
        "emotion_tags": {"culture_depth": 0.2, "sociability": 0.9},
    }
    # poi_a 在 "美食" 类中, poi_b 在 "文化" 类中 → 也匹配场景型，
    # 但 cognitive overload 先匹配，应返回 -0.6
    assert chemical_reaction(poi_a, poi_b) == -0.6


def test_chemical_reaction_missing_emotion_tags():
    """缺少emotion_tags时不应崩溃."""
    poi_a = {"category": "文化"}
    poi_b = {"category": "餐饮"}
    # 无 emotion_tags → 所有值默认为 0 → 无匹配 → 0.0
    assert chemical_reaction(poi_a, poi_b) == 0.0


# ===========================================================================
# sensory_alternation 测试
# ===========================================================================


def _make_step(category: str) -> dict:
    """辅助: 生成一个带指定 category 的 route step."""
    return {"poi": {"category": category}}


def test_sensory_alternation_empty():
    """空路线 → 0.0."""
    assert sensory_alternation([]) == 0.0


def test_sensory_alternation_single():
    """单 POI → 0.0."""
    assert sensory_alternation([_make_step("文化")]) == 0.0


def test_sensory_alternation_alternating_types():
    """相邻 POI 感官类型不同 → 每对 +0.1."""
    route = [_make_step("文化"), _make_step("餐饮"), _make_step("运动")]
    # 文化→餐饮: visual→tactile: +0.1
    # 餐饮→运动: tactile→dynamic: +0.1
    assert sensory_alternation(route) == 0.2


def test_sensory_alternation_three_same_types():
    """连续 3 个 POI 同感官类型 → -0.3."""
    route = [
        _make_step("文化"),
        _make_step("景点"),
        _make_step("自然"),
    ]
    # 文化(visual)→景点(visual): same, consecutive=2
    # 景点(visual)→自然(visual): same, consecutive=3 → -0.3
    assert sensory_alternation(route) == -0.3


def test_sensory_alternation_four_same_types():
    """连续 4 个 POI 同感官类型 → -0.6."""
    route = [
        _make_step("文化"),
        _make_step("景点"),
        _make_step("自然"),
        _make_step("文化"),
    ]
    # 文化(visual)→景点(visual): same, consecutive=2
    # 景点(visual)→自然(visual): same, consecutive=3 → -0.3
    # 自然(visual)→文化(visual): same, consecutive=4 → -0.3
    assert sensory_alternation(route) == -0.6


def test_sensory_alternation_mixed_route():
    """混合感官类型 → 正确累计."""
    route = [
        _make_step("文化"),   # visual
        _make_step("餐饮"),   # tactile  → diff: +0.1, cons=1
        _make_step("餐饮"),   # tactile  → same: cons=2
        _make_step("运动"),   # dynamic  → diff: +0.1, cons=1
        _make_step("运动"),   # dynamic  → same: cons=2
        _make_step("运动"),   # dynamic  → same: cons=3 → -0.3
    ]
    # +0.1 (文化→餐饮) + 0.1 (餐饮→运动) - 0.3 (运动→运动 连续3+)
    # = -0.1
    assert sensory_alternation(route) == pytest.approx(-0.1)


def test_sensory_alternation_bonus_many_changes():
    """交替次数 > 3 → +0.5 bonus (路线 ≥ 4 POI)."""
    route = [
        _make_step("文化"),   # visual
        _make_step("餐饮"),   # tactile  → diff: +0.1 (change 1)
        _make_step("运动"),   # dynamic  → diff: +0.1 (change 2)
        _make_step("餐饮"),   # tactile  → diff: +0.1 (change 3)
        _make_step("文化"),   # visual   → diff: +0.1 (change 4)
    ]
    # 4 changes (相邻 type 不同), > 3 → +0.5 bonus
    # base: 4 * 0.1 = 0.4
    # bonus: +0.5
    assert sensory_alternation(route) == 0.9


def test_sensory_alternation_bonus_three_changes_no_bonus():
    """交替次数 = 3 (在4个POI中), ≤ 3 → 无 bonus."""
    route = [
        _make_step("文化"),   # visual
        _make_step("餐饮"),   # tactile  → diff: +0.1 (change 1)
        _make_step("运动"),   # dynamic  → diff: +0.1 (change 2)
        _make_step("文化"),   # visual   → diff: +0.1 (change 3)
    ]
    # 3 changes, ≤ 3 → no bonus
    # base: 3 * 0.1 = 0.3
    assert sensory_alternation(route) == pytest.approx(0.3)


def test_sensory_alternation_bare_poi_dicts():
    """支持直接 POI 字典列表（无 'poi' 键）. """
    route = [
        {"category": "文化"},
        {"category": "餐饮"},
        {"category": "运动"},
    ]
    assert sensory_alternation(route) == 0.2


def test_sensory_alternation_unknown_category():
    """未知 category → 映射到 'static'."""
    route = [
        _make_step("文化"),       # visual
        _make_step("外星基地"),   # unknown → static → diff: +0.1
    ]
    assert sensory_alternation(route) == 0.1


# ===========================================================================
# SENSORY_TAGS 映射验证
# ===========================================================================


def test_sensory_tags_mapping():
    """验证 SENSORY_TAGS 映射表包含必要的键."""
    assert SENSORY_TAGS["文化"] == "visual"
    assert SENSORY_TAGS["餐饮"] == "tactile"
    assert SENSORY_TAGS["美食"] == "tactile"
    assert SENSORY_TAGS["运动"] == "dynamic"
    assert SENSORY_TAGS["娱乐"] == "dynamic"
    assert SENSORY_TAGS["购物"] == "tactile"
    assert SENSORY_TAGS["其他"] == "static"
    assert SENSORY_TAGS["自然"] == "visual"
    assert SENSORY_TAGS["景点"] == "visual"


# ===========================================================================
# 导入验证: solver 仍能正常导入新函数
# ===========================================================================


def test_solver_imports_with_new_functions():
    """验证 solver 导入 chemical_reaction 和 sensory_alternation 不报错."""
    from backend.services.solver import solve_route

    assert callable(solve_route)
