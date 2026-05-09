"""
为 city_poi_db.json 中每个POI添加6维情绪标签。

维度：
  excitement      兴奋度
  tranquility     宁静度
  sociability     社交性
  culture_depth   文化深度
  surprise        惊喜感
  physical_demand 体力消耗

运行: python add_emotion_tags.py
幂等：重复运行会覆盖已有 emotion_tags，结果一致。
"""

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "city_poi_db.json"

# ---------- 基础分 (按 category) ----------

BASE_SCORES: dict[str, dict[str, float]] = {
    "文化": {
        "excitement": 0.30,
        "tranquility": 0.60,
        "sociability": 0.30,
        "culture_depth": 0.80,
        "surprise": 0.30,
        "physical_demand": 0.20,
    },
    "运动": {
        "excitement": 0.50,
        "tranquility": 0.20,
        "sociability": 0.40,
        "culture_depth": 0.20,
        "surprise": 0.30,
        "physical_demand": 0.70,
    },
    "餐饮": {
        "excitement": 0.40,
        "tranquility": 0.30,
        "sociability": 0.60,
        "culture_depth": 0.30,
        "surprise": 0.35,
        "physical_demand": 0.10,
    },
    "购物": {
        "excitement": 0.50,
        "tranquility": 0.20,
        "sociability": 0.50,
        "culture_depth": 0.20,
        "surprise": 0.40,
        "physical_demand": 0.20,
    },
    "酒店": {
        "excitement": 0.20,
        "tranquility": 0.60,
        "sociability": 0.30,
        "culture_depth": 0.10,
        "surprise": 0.20,
        "physical_demand": 0.10,
    },
    "其他": {
        "excitement": 0.35,
        "tranquility": 0.40,
        "sociability": 0.35,
        "culture_depth": 0.25,
        "surprise": 0.30,
        "physical_demand": 0.30,
    },
}

# ---------- tag 微调 ----------

TAG_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "安静":       {"tranquility": +0.20},
    "人少":       {"tranquility": +0.15, "sociability": -0.20},
    "免费":       {"surprise": +0.10},
    "空气好":     {"tranquility": +0.10, "physical_demand": +0.10},
    "拍照好":     {"excitement": +0.10, "surprise": +0.10},
    "值得去":     {"excitement": +0.10, "surprise": +0.10},
    "网红店":     {"excitement": +0.15, "surprise": +0.10},
    "教练好":     {"physical_demand": +0.20},
    "早餐好":     {"surprise": +0.10},
    "位置好":     {},
    "服务好":     {},
    "干净":       {"tranquility": +0.05},
    "性价比高":   {"surprise": +0.10},
    "设施全":     {"physical_demand": +0.10},
    # ---- 额外标签（数据中出现但规则未覆盖）----
    "环境好":     {"tranquility": +0.10},
    "味道正宗":   {"excitement": +0.10},
    "分量足":     {"surprise": +0.05},
    "老字号":     {"culture_depth": +0.15},
    "推荐":       {"excitement": +0.05},
    "排队":       {"excitement": +0.05, "physical_demand": +0.05},
    "方便":       {"surprise": +0.05},
    "交通便利":   {},
    "停车方便":   {},
    "打折":       {"surprise": +0.08},
    "品牌齐全":   {"excitement": +0.05},
    "新品多":     {"excitement": +0.05, "surprise": +0.05},
    "有讲解":     {"culture_depth": +0.10},
    "涨知识":     {"culture_depth": +0.10},
    "适合聚餐":   {"sociability": +0.15},
    "不错":       {"excitement": +0.03},
}


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """限制在 [lo, hi] 范围内，保留两位小数。"""
    return round(max(lo, min(hi, value)), 2)


def compute_emotion_tags(category: str, tags: list[str]) -> dict[str, float]:
    """基于 category 和 tags 计算6维情绪标签。"""
    base = dict(BASE_SCORES.get(category, BASE_SCORES["其他"]))

    for tag in tags:
        adjustments = TAG_ADJUSTMENTS.get(tag, {})
        for dim, delta in adjustments.items():
            base[dim] = base[dim] + delta

    return {dim: clamp(val) for dim, val in base.items()}


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    for poi in data:
        category = poi.get("category", "其他")
        tags = poi.get("tags", [])
        poi["emotion_tags"] = compute_emotion_tags(category, tags)

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Done. {len(data)} POIs updated.")


if __name__ == "__main__":
    main()
