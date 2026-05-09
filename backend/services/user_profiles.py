"""
CityFlow 用户画像定义模块
定义20组典型用户画像，用于意图匹配和路线推荐。
"""

from __future__ import annotations

import math
from typing import Any

from backend.services.cache import cache_key, profile_cache

# ---------------------------------------------------------------------------
# 20 组用户画像
# ---------------------------------------------------------------------------

USER_PROFILES: dict[str, dict[str, Any]] = {
    "P1": {
        "name": "社恐独居",
        "group_type": "独居",
        "social": 0.1,
        "pace": "闲逛型",
        "preferences": {"culture": 0.6, "food": 0.4, "nature": 0.7, "social": 0.1},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["排队容忍度<5min", "避开人流高峰"],
    },
    "P2": {
        "name": "浪漫情侣",
        "group_type": "情侣",
        "social": 0.5,
        "pace": "平衡型",
        "preferences": {"culture": 0.5, "food": 0.8, "nature": 0.6, "social": 0.5},
        "budget_level": "高",
        "spend_style": "享受型",
        "hard_constraints": ["有氛围感", "可拍照"],
    },
    "P3": {
        "name": "活力亲子",
        "group_type": "亲子",
        "social": 0.6,
        "pace": "平衡型",
        "preferences": {"culture": 0.4, "food": 0.5, "nature": 0.7, "social": 0.6},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["儿童友好", "有教育意义", "有休息区"],
    },
    "P4": {
        "name": "朋友聚会",
        "group_type": "朋友",
        "social": 0.9,
        "pace": "特种兵型",
        "preferences": {"culture": 0.3, "food": 0.8, "nature": 0.4, "social": 0.9},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["可容纳多人", "有互动体验"],
    },
    "P5": {
        "name": "退休休闲",
        "group_type": "退休",
        "social": 0.3,
        "pace": "闲逛型",
        "preferences": {"culture": 0.7, "food": 0.5, "nature": 0.8, "social": 0.3},
        "budget_level": "低",
        "spend_style": "节俭型",
        "hard_constraints": ["无障碍通行", "有休息区", "不需长时间步行"],
    },
    "P6": {
        "name": "文化探索者",
        "group_type": "独居",
        "social": 0.4,
        "pace": "平衡型",
        "preferences": {"culture": 0.9, "food": 0.4, "nature": 0.5, "social": 0.4},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["有文化内涵", "可学习知识"],
    },
    "P7": {
        "name": "美食猎人",
        "group_type": "朋友",
        "social": 0.7,
        "pace": "特种兵型",
        "preferences": {"culture": 0.3, "food": 0.95, "nature": 0.2, "social": 0.7},
        "budget_level": "高",
        "spend_style": "享受型",
        "hard_constraints": ["有特色美食", "可排队但要值得"],
    },
    "P8": {
        "name": "自然爱好者",
        "group_type": "独居",
        "social": 0.2,
        "pace": "闲逛型",
        "preferences": {"culture": 0.3, "food": 0.3, "nature": 0.95, "social": 0.2},
        "budget_level": "低",
        "spend_style": "节俭型",
        "hard_constraints": ["亲近自然", "空气清新"],
    },
    "P9": {
        "name": "社交达人",
        "group_type": "朋友",
        "social": 0.95,
        "pace": "特种兵型",
        "preferences": {"culture": 0.2, "food": 0.6, "nature": 0.3, "social": 0.95},
        "budget_level": "高",
        "spend_style": "享受型",
        "hard_constraints": ["热闹场所", "可认识新朋友"],
    },
    "P10": {
        "name": "摄影爱好者",
        "group_type": "独居",
        "social": 0.3,
        "pace": "平衡型",
        "preferences": {"culture": 0.6, "food": 0.3, "nature": 0.7, "social": 0.3},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["拍照出片", "有独特视角"],
    },
    "P11": {
        "name": "历史迷",
        "group_type": "独居",
        "social": 0.3,
        "pace": "平衡型",
        "preferences": {"culture": 0.95, "food": 0.3, "nature": 0.4, "social": 0.3},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["历史遗迹", "有讲解服务"],
    },
    "P12": {
        "name": "宠物主人",
        "group_type": "独居",
        "social": 0.4,
        "pace": "闲逛型",
        "preferences": {"culture": 0.3, "food": 0.5, "nature": 0.8, "social": 0.4},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["宠物友好", "有户外空间"],
    },
    "P13": {
        "name": "运动健身",
        "group_type": "独居",
        "social": 0.4,
        "pace": "特种兵型",
        "preferences": {"culture": 0.2, "food": 0.4, "nature": 0.7, "social": 0.4},
        "budget_level": "低",
        "spend_style": "节俭型",
        "hard_constraints": ["有运动设施", "可消耗体力"],
    },
    "P14": {
        "name": "三代同堂",
        "group_type": "亲子",
        "social": 0.5,
        "pace": "闲逛型",
        "preferences": {"culture": 0.5, "food": 0.6, "nature": 0.6, "social": 0.5},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["无障碍通行", "有儿童设施", "有休息区", "老少皆宜"],
    },
    "P15": {
        "name": "商务休闲",
        "group_type": "独居",
        "social": 0.5,
        "pace": "平衡型",
        "preferences": {"culture": 0.4, "food": 0.7, "nature": 0.4, "social": 0.5},
        "budget_level": "高",
        "spend_style": "享受型",
        "hard_constraints": ["环境优雅", "适合洽谈"],
    },
    "P16": {
        "name": "学生穷游",
        "group_type": "朋友",
        "social": 0.7,
        "pace": "特种兵型",
        "preferences": {"culture": 0.5, "food": 0.6, "nature": 0.5, "social": 0.7},
        "budget_level": "低",
        "spend_style": "节俭型",
        "hard_constraints": ["免费或低价", "交通便利"],
    },
    "P17": {
        "name": "艺术家",
        "group_type": "独居",
        "social": 0.3,
        "pace": "闲逛型",
        "preferences": {"culture": 0.9, "food": 0.4, "nature": 0.6, "social": 0.3},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["有艺术氛围", "可激发灵感"],
    },
    "P18": {
        "name": "夜生活爱好者",
        "group_type": "朋友",
        "social": 0.8,
        "pace": "特种兵型",
        "preferences": {"culture": 0.2, "food": 0.7, "nature": 0.1, "social": 0.8},
        "budget_level": "高",
        "spend_style": "享受型",
        "hard_constraints": ["夜间营业", "有娱乐设施"],
    },
    "P19": {
        "name": "亲子教育",
        "group_type": "亲子",
        "social": 0.5,
        "pace": "平衡型",
        "preferences": {"culture": 0.7, "food": 0.4, "nature": 0.5, "social": 0.5},
        "budget_level": "中",
        "spend_style": "均衡型",
        "hard_constraints": ["有教育意义", "互动体验", "适合儿童"],
    },
    "P20": {
        "name": "极简主义者",
        "group_type": "独居",
        "social": 0.1,
        "pace": "闲逛型",
        "preferences": {"culture": 0.5, "food": 0.3, "nature": 0.8, "social": 0.1},
        "budget_level": "低",
        "spend_style": "节俭型",
        "hard_constraints": ["人少清净", "自然环境"],
    },
}

# 预算水平数值映射（用于相似度计算）
_BUDGET_LEVEL_MAP: dict[str, float] = {"低": 0.2, "中": 0.5, "高": 0.8}

# 预算水平 → 消费风格映射
_SPEND_STYLE_MAP: dict[str, str] = {"低": "节俭型", "中": "均衡型", "高": "享受型"}


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def match_profile(intent: dict[str, Any]) -> str:
    """
    根据用户意图匹配最相似的画像ID。

    计算逻辑：
    1. 偏好向量余弦相似度（权重 0.4）
    2. 社交倾向距离（权重 0.2）
    3. 群体类型匹配（权重 0.2）
    4. 节奏偏好匹配（权重 0.1）
    5. 预算水平距离（权重 0.1）

    参数:
        intent: 用户意图字典，包含 group, preferences, pace, budget 等字段

    返回:
        最匹配的画像 ID（P1-P20）
    """
    # 检查缓存
    ck = f"profile:{cache_key(intent)}"
    cached_result = profile_cache.get(ck)
    if cached_result is not None:
        return cached_result

    best_id = "P1"
    best_score = -1.0

    # 提取意图特征
    group_type = intent.get("group", {}).get("type", "独居")
    social = intent.get("preferences", {}).get("social", 0.5)
    pace = intent.get("pace", "平衡型")
    budget = intent.get("budget", {})
    budget_level = _infer_budget_level(budget)

    # 构建用户偏好向量 [culture, food, nature, social]
    user_prefs = intent.get("preferences", {})
    user_vec = [
        user_prefs.get("culture", 0.5),
        user_prefs.get("food", 0.5),
        user_prefs.get("nature", 0.5),
        user_prefs.get("social", 0.5),
    ]

    for pid, profile in USER_PROFILES.items():
        score = 0.0

        # 1. 偏好向量余弦相似度（权重 0.4）
        profile_vec = [
            profile["preferences"]["culture"],
            profile["preferences"]["food"],
            profile["preferences"]["nature"],
            profile["preferences"]["social"],
        ]
        cos_sim = _cosine_similarity(user_vec, profile_vec)
        score += 0.4 * cos_sim

        # 2. 社交倾向距离（权重 0.2）
        social_diff = abs(profile["social"] - social)
        score += 0.2 * (1 - social_diff)

        # 3. 群体类型匹配（权重 0.2）
        if profile["group_type"] == group_type:
            score += 0.2

        # 4. 节奏偏好匹配（权重 0.1）
        if profile["pace"] == pace:
            score += 0.1

        # 5. 预算水平距离（权重 0.1）
        profile_budget = _BUDGET_LEVEL_MAP.get(profile["budget_level"], 0.5)
        user_budget = _BUDGET_LEVEL_MAP.get(budget_level, 0.5)
        budget_diff = abs(profile_budget - user_budget)
        score += 0.1 * (1 - budget_diff)

        if score > best_score:
            best_score = score
            best_id = pid

    # 缓存结果
    profile_cache.set(ck, best_id)
    return best_id


def _infer_budget_level(budget: dict[str, Any]) -> str:
    """从预算信息推断预算水平。"""
    per_person = budget.get("per_person", 500)
    if per_person < 200:
        return "低"
    elif per_person < 800:
        return "中"
    else:
        return "高"


def get_spend_style_by_budget_level(budget_level: str) -> str:
    """根据预算水平获取消费风格。

    Args:
        budget_level: "低" / "中" / "高"

    Returns:
        "节俭型" / "均衡型" / "享受型"
    """
    return _SPEND_STYLE_MAP.get(budget_level, "均衡型")


def get_profile_by_id(profile_id: str) -> dict[str, Any] | None:
    """根据画像 ID 获取画像详情。"""
    return USER_PROFILES.get(profile_id)


def get_all_profile_ids() -> list[str]:
    """获取所有画像 ID 列表。"""
    return list(USER_PROFILES.keys())


def get_profiles_by_group_type(group_type: str) -> dict[str, dict[str, Any]]:
    """根据群体类型筛选画像。"""
    return {
        pid: profile
        for pid, profile in USER_PROFILES.items()
        if profile["group_type"] == group_type
    }


# ---------------------------------------------------------------------------
# CLI 测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # 测试画像匹配
    test_intent = {
        "group": {"type": "情侣", "size": 2},
        "preferences": {"culture": 0.5, "food": 0.8, "nature": 0.6, "social": 0.5},
        "pace": "平衡型",
        "budget": {"per_person": 1000, "type": "弹性"},
    }

    matched_id = match_profile(test_intent)
    profile = USER_PROFILES[matched_id]

    print("=== 画像匹配测试 ===")
    print(f"输入意图: {json.dumps(test_intent, ensure_ascii=False, indent=2)}")
    print(f"\n匹配结果: {matched_id} - {profile['name']}")
    print(f"画像详情: {json.dumps(profile, ensure_ascii=False, indent=2)}")

    # 列出所有画像
    print("\n=== 所有画像概览 ===")
    for pid, p in USER_PROFILES.items():
        print(
            f"{pid}: {p['name']} ({p['group_type']}, {p['pace']}, 社交={p['social']})"
        )
