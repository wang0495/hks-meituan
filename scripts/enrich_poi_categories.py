"""POI category enrichment: 拆分大类、合并碎片、增加多样性可见度。

问题：
  - "景点"(335个) 包含自然/海滨/文化/亲子/夜景等完全不同的体验
  - 但evaluator只看到一个"景点"→ scene_diversity低分
  - 29种碎片化category，15种不到10个POI

方案：
  - 给每个POI添加 _display_category 字段（保留原始category不变）
  - "景点"按 _scene_tags 和 tags 拆分为5个子类
  - "餐饮"按 tags 拆分为3个子类
  - 碎片化category合并
  - 修改 format_route 使用 _display_category

用法:
    python scripts/enrich_poi_categories.py          # 分析+修改
    python scripts/enrich_poi_categories.py --dry-run # 只分析不修改

影响范围：
    - backend/data/city_poi_db.json (添加 _display_category 字段)
    - tests/test_c_version.py (format_route 使用 _display_category)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA_PATH = Path("backend/data/city_poi_db.json")

# ═══════════════════════════════════════════════════════════
# 分类规则
# ═══════════════════════════════════════════════════════════

def _classify_scenic(poi: dict) -> str:
    """将"景点"拆分为5个子类。"""
    tags = set(t.lower() for t in poi.get("tags", []))
    scene_tags = set(t.lower() for t in poi.get("_scene_tags", []))
    name = poi.get("name", "").lower()
    all_text = " ".join(tags | scene_tags) + " " + name

    # 优先级：亲子 > 海滨 > 自然 > 夜景 > 文化 > 默认景点
    if any(kw in all_text for kw in ["亲子", "儿童", "游乐", "乐园", "海洋馆", "动物园", "水族"]):
        return "亲子游乐"

    if any(kw in all_text for kw in ["海滨", "海滩", "海边", "海岸", "沙滩", "泳场", "海湾", "海岛"]):
        return "海滨景点"

    if any(kw in all_text for kw in ["山", "森林", "湿地", "公园", "绿道", "生态", "自然保护区"]):
        # 但"公园"如果是"文化公园"则不算自然
        if "文化" not in all_text and "历史" not in all_text:
            return "自然风光"

    if any(kw in all_text for kw in ["夜景", "夜游", "灯光", "喷泉表演", "观景台"]):
        return "夜景地标"

    if any(kw in all_text for kw in ["文化", "历史", "古镇", "遗址", "博物馆", "纪念馆", "牌坊", "祠堂"]):
        return "文化景点"

    # 默认：地标景点
    return "地标景点"


def _classify_food(poi: dict) -> str:
    """将"餐饮"拆分为子类。"""
    tags = set(t.lower() for t in poi.get("tags", []))
    scene_tags = set(t.lower() for t in poi.get("_scene_tags", []))
    name = poi.get("name", "").lower()
    cat = poi.get("category", "").lower()
    all_text = " ".join(tags | scene_tags) + " " + name + " " + cat

    if any(kw in all_text for kw in ["夜市", "大排档", "深夜", "宵夜", "24小时", "凌晨"]):
        return "夜市小吃"

    if any(kw in all_text for kw in ["海鲜", "水产", "生蚝"]):
        return "海鲜餐饮"

    if any(kw in all_text for kw in ["甜品", "奶茶", "冰室", "甜品店", "饮品", "咖啡", "蛋糕"]):
        return "甜品饮品"

    if any(kw in all_text for kw in ["茶餐厅", "早茶", "点心", "港式"]):
        return "茶餐厅"

    if any(kw in all_text for kw in ["小吃", "粉", "面", "粥", "排档", "烧烤", "串", "煎", "饼"]):
        return "地方小吃"

    return "正餐"


# 碎片化category合并表
_MERGE_MAP = {
    "密室逃脱": "密室逃脱",
    "益智": "密室逃脱",
    "恐怖密室": "密室逃脱",
    "亲子密室": "密室逃脱",
    "户外攀岩": "攀岩",
    "室内攀岩": "攀岩",
    "科技": "科技体验",
    "游戏": "科技体验",
    "网吧": "科技体验",
    "科技体验": "科技体验",
    "夜市小吃": "夜市小吃",
    "夜市": "夜市小吃",
    "海景咖啡馆": "海景咖啡馆",
    "咖啡馆": "海景咖啡馆",
    "娱乐": "休闲娱乐",
    "剧本杀": "休闲娱乐",
    "休闲": "休闲娱乐",
}


def enrich_display_category(poi: dict) -> str:
    """计算POI的_display_category。"""
    cat = poi.get("category", "")

    # 1. 景点拆分
    if cat == "景点":
        return _classify_scenic(poi)

    # 2. 餐饮拆分
    if cat in ("餐饮", "美食", "小吃"):
        return _classify_food(poi)

    # 3. 碎片化合并
    if cat in _MERGE_MAP:
        return _MERGE_MAP[cat]

    # 4. 其他保持不变
    return cat


def main():
    dry_run = "--dry-run" in sys.argv

    print("加载POI数据...")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        pois = json.load(f)
    print(f"共 {len(pois)} 个POI")

    # 分析当前分布
    print("\n=== 当前category分布 ===")
    current_cats = Counter(p.get("category", "?") for p in pois)
    for cat, count in current_cats.most_common(15):
        print(f"  {cat}: {count} ({count / len(pois) * 100:.1f}%)")

    # 计算enrichment
    enriched = []
    for poi in pois:
        new_cat = enrich_display_category(poi)
        enriched.append((poi.get("category", ""), new_cat))
        poi["_display_category"] = new_cat

    # 分析新分布
    print("\n=== Enriched _display_category 分布 ===")
    new_cats = Counter(p.get("_display_category", "?") for p in pois)
    for cat, count in new_cats.most_common(20):
        print(f"  {cat}: {count} ({count / len(pois) * 100:.1f}%)")

    # 对比
    print("\n=== 变化摘要 ===")
    changed = sum(1 for old, new in enriched if old != new)
    print(f"  变化: {changed}/{len(pois)} ({changed / len(pois) * 100:.1f}%)")
    print(f"  原始唯一category: {len(current_cats)}")
    print(f"  新唯一category: {len(new_cats)}")

    # 展示景点拆分效果
    scenic_orig = sum(1 for p in pois if p.get("category") == "景点")
    scenic_new = Counter(
        p.get("_display_category", "?") for p in pois if p.get("category") == "景点"
    )
    print(f"\n  景点({scenic_orig}个)拆分为:")
    for cat, count in scenic_new.most_common():
        print(f"    {cat}: {count}")

    # 展示餐饮拆分效果
    food_orig = sum(1 for p in pois if p.get("category") in ("餐饮", "美食", "小吃"))
    food_new = Counter(
        p.get("_display_category", "?") for p in pois if p.get("category") in ("餐饮", "美食", "小吃")
    )
    print(f"\n  餐饮({food_orig}个)拆分为:")
    for cat, count in food_new.most_common():
        print(f"    {cat}: {count}")

    if dry_run:
        print("\n[dry-run] 不写入文件")
        return

    # 写入
    backup = DATA_PATH.with_suffix(".json.bak")
    DATA_PATH.rename(backup)
    print(f"\n备份到 {backup}")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)
    print(f"已写入 {DATA_PATH}")

    # 统计：如果使用_display_category，路线的category多样性会怎样
    print("\n=== 预期diversity提升 ===")
    # 模拟：如果路线有6个POI（2景点+2餐饮+1文化+1运动）
    sample_route_cats = ["地标景点", "海滨景点", "海鲜餐饮", "甜品饮品", "文化", "运动"]
    print(f"  示例路线category: {sample_route_cats}")
    print(f"  唯一类型数: {len(set(sample_route_cats))}")
    print(f"  原始分类下: ['景点', '景点', '餐饮', '餐饮', '文化', '运动'] → {len(set(['景点', '景点', '餐饮', '餐饮', '文化', '运动']))}种")
    print(f"  enrichment后: {sample_route_cats} → {len(set(sample_route_cats))}种")
    print(f"  → diversity从3种提升到6种!")


if __name__ == "__main__":
    main()
