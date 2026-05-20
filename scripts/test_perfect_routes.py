"""手动构建3条完美路线，送评分系统看天花板。"""

from __future__ import annotations

import asyncio
import json
import os
import sys

# 复用test_c_version的评分函数
sys.path.insert(0, ".")
from tests.test_c_version import llm_score, format_route

API_KEY = os.getenv("LLM_API_KEY", "")
if not API_KEY:
    print("请设置 LLM_API_KEY 环境变量")
    sys.exit(1)

# ── 场景1: 情侣珠海一日游 ──
# 策略: 情侣路沿线经典景点 → 海景咖啡馆 → 日月贝日落 → 海鲜晚餐
# 地理: 香山湖→景山道→海滨公园→海滨泳场→日月贝 全程情侣路沿线，不折返
PERFECT_ROUTE_1 = [
    {"poi": {"name": "香山湖公园", "category": "景点", "_display_category": "自然景点", "avg_price": 0, "rating": 4.5, "lat": 22.2670, "lng": 113.5560, "_scene_tags": ["自然风光", "拍照出片", "湖景"]}, "arrival_time": "09:00", "departure_time": "10:30", "travel_from_prev": None},
    {"poi": {"name": "珠海景山道（板樟山步道）", "category": "自然风光", "_display_category": "自然风光", "avg_price": 0, "rating": 4.4, "lat": 22.2350, "lng": 113.5480, "_scene_tags": ["徒步", "城市绿道", "全景"]}, "arrival_time": "10:50", "departure_time": "12:00", "travel_from_prev": {"distance_m": 3800, "time_min": 20}},
    {"poi": {"name": "湾仔海鲜街", "category": "餐饮", "_display_category": "海鲜餐饮", "avg_price": 120, "rating": 4.8, "lat": 22.1946, "lng": 113.5267, "_scene_tags": ["海鲜", "本地特色", "美食街"]}, "arrival_time": "12:30", "departure_time": "14:00", "travel_from_prev": {"distance_m": 5500, "time_min": 30}},
    {"poi": {"name": "海滨公园", "category": "景点", "_display_category": "海滨公园", "avg_price": 0, "rating": 4.5, "lat": 22.2736, "lng": 113.5789, "_scene_tags": ["海滨", "拍照出片", "情侣"]}, "arrival_time": "14:40", "departure_time": "16:00", "travel_from_prev": {"distance_m": 9200, "time_min": 40}},
    {"poi": {"name": "野狸岛·屿见咖啡", "category": "海景咖啡馆", "_display_category": "海景咖啡馆", "avg_price": 65, "rating": 4.7, "lat": 22.2750, "lng": 113.5760, "_scene_tags": ["海景咖啡", "手冲", "拍照"]}, "arrival_time": "16:15", "departure_time": "17:30", "travel_from_prev": {"distance_m": 800, "time_min": 15}},
    {"poi": {"name": "日月贝（珠海大剧院）", "category": "文化", "_display_category": "地标建筑", "avg_price": 80, "rating": 4.7, "lat": 22.2820, "lng": 113.5680, "_scene_tags": ["地标", "日落", "拍照圣地"]}, "arrival_time": "17:45", "departure_time": "19:00", "travel_from_prev": {"distance_m": 600, "time_min": 15}},
    {"poi": {"name": "梅华海鲜城", "category": "餐饮", "_display_category": "粤式餐饮", "avg_price": 88, "rating": 4.8, "lat": 22.2784, "lng": 113.5174, "_scene_tags": ["粤菜", "本地特色", "性价比"]}, "arrival_time": "19:30", "departure_time": "21:00", "travel_from_prev": {"distance_m": 5200, "time_min": 30}},
]

# ── 场景2: 带孩子去长隆海洋王国 ──
# 策略: 横琴片区集中，海洋王国玩大半天 → 午餐在园区附近 → 花海长廊散步 → 温泉放松
# 地理: 全部横琴片区，距离极近
PERFECT_ROUTE_2 = [
    {"poi": {"name": "珠海横琴长隆海洋王国", "category": "景点", "_display_category": "主题乐园", "avg_price": 300, "rating": 4.8, "lat": 22.1390, "lng": 113.5600, "_scene_tags": ["亲子", "海洋动物", "游乐设施"]}, "arrival_time": "09:00", "departure_time": "15:00", "travel_from_prev": None},
    {"poi": {"name": "横琴长隆海洋科学馆", "category": "景点", "_display_category": "科普展馆", "avg_price": 150, "rating": 4.7, "lat": 22.1567, "lng": 113.5432, "_scene_tags": ["亲子", "科普", "互动体验"]}, "arrival_time": "15:20", "departure_time": "17:00", "travel_from_prev": {"distance_m": 3200, "time_min": 20}},
    {"poi": {"name": "珠海横琴花海长廊", "category": "景点", "_display_category": "花海公园", "avg_price": 0, "rating": 4.7, "lat": 22.1400, "lng": 113.5610, "_scene_tags": ["花海", "拍照出片", "散步"]}, "arrival_time": "17:20", "departure_time": "18:30", "travel_from_prev": {"distance_m": 2800, "time_min": 20}},
    {"poi": {"name": "横琴长隆·海洋主题咖啡", "category": "海景咖啡馆", "_display_category": "亲子咖啡馆", "avg_price": 68, "rating": 4.6, "lat": 22.1300, "lng": 113.5100, "_scene_tags": ["亲子设施", "卡通拉花", "下午茶"]}, "arrival_time": "18:50", "departure_time": "19:30", "travel_from_prev": {"distance_m": 1500, "time_min": 20}},
    {"poi": {"name": "横琴长隆海洋温泉", "category": "温泉SPA", "_display_category": "亲子温泉", "avg_price": 328, "rating": 4.7, "lat": 22.1345, "lng": 113.5678, "_scene_tags": ["亲子", "温泉", "海洋主题"]}, "arrival_time": "19:50", "departure_time": "21:00", "travel_from_prev": {"distance_m": 2000, "time_min": 20}},
]

# ── 场景3: 珠海美食一日游 ──
# 策略: 纯美食路线，覆盖海鲜、茶餐厅、甜品、夜市4种子类型
# 地理: 市区范围内，同区域连走不折返
PERFECT_ROUTE_3 = [
    {"poi": {"name": "世記咖啡", "category": "餐饮", "_display_category": "茶餐厅", "avg_price": 84, "rating": 5.0, "lat": 22.1951, "lng": 113.5406, "_scene_tags": ["港式茶餐厅", "老字号", "菠萝油"]}, "arrival_time": "09:00", "departure_time": "10:00", "travel_from_prev": None},
    {"poi": {"name": "義順鮮奶", "category": "餐饮", "_display_category": "甜品饮品", "avg_price": 197, "rating": 5.0, "lat": 22.1945, "lng": 113.5402, "_scene_tags": ["鲜奶甜品", "双皮奶", "网红店"]}, "arrival_time": "10:10", "departure_time": "11:00", "travel_from_prev": {"distance_m": 200, "time_min": 10}},
    {"poi": {"name": "湾仔海鲜街", "category": "餐饮", "_display_category": "海鲜餐饮", "avg_price": 150, "rating": 4.8, "lat": 22.1946, "lng": 113.5267, "_scene_tags": ["海鲜", "现买现做", "本地特色"]}, "arrival_time": "11:30", "departure_time": "13:00", "travel_from_prev": {"distance_m": 1800, "time_min": 30}},
    {"poi": {"name": "Cuppa Coffee", "category": "餐饮", "_display_category": "精品咖啡", "avg_price": 109, "rating": 5.0, "lat": 22.1566, "lng": 113.5596, "_scene_tags": ["精品咖啡", "手冲", "环境好"]}, "arrival_time": "14:00", "departure_time": "15:00", "travel_from_prev": {"distance_m": 6500, "time_min": 60}},
    {"poi": {"name": "梅华海鲜城", "category": "餐饮", "_display_category": "粤式餐饮", "avg_price": 88, "rating": 4.8, "lat": 22.2784, "lng": 113.5174, "_scene_tags": ["粤菜", "烧鹅", "本地人推荐"]}, "arrival_time": "17:00", "departure_time": "18:30", "travel_from_prev": {"distance_m": 8000, "time_min": 60}},
    {"poi": {"name": "夏湾夜市", "category": "夜市小吃", "_display_category": "夜市小吃", "avg_price": 50, "rating": 4.3, "lat": 22.2300, "lng": 113.5350, "_scene_tags": ["夜市", "小吃", "烧烤"]}, "arrival_time": "19:00", "departure_time": "21:00", "travel_from_prev": {"distance_m": 6000, "time_min": 30}},
]


SCENARIOS = [
    {"id": 1, "name": "情侣珠海一日游", "input": "情侣珠海一日游，预算500元，喜欢拍照打卡", "route": PERFECT_ROUTE_1},
    {"id": 2, "name": "亲子海洋王国", "input": "带6岁孩子去长隆海洋王国，预算1000元", "route": PERFECT_ROUTE_2},
    {"id": 3, "name": "美食探索", "input": "珠海美食一日游，想吃海鲜和本地特色", "route": PERFECT_ROUTE_3},
]


async def main():
    print("=" * 60)
    print("完美路线天花板测试 — 手写路线 vs 评分系统")
    print(f"评分模型: deepseek-chat | 及格线: 6.5")
    print("=" * 60)

    results = []
    for sc in SCENARIOS:
        route_text = format_route(sc["route"])
        print(f"\n{'─' * 50}")
        print(f"场景{sc['id']}: {sc['name']}")
        print(f"输入: {sc['input']}")
        print(f"路线 ({len(sc['route'])}站):")
        for i, step in enumerate(sc["route"], 1):
            p = step["poi"]
            print(f"  {i}. {p['name']} [{p.get('_display_category', p['category'])}] ¥{p['avg_price']} {step['arrival_time']}→{step['departure_time']}")

        # 评分3次取平均
        scores_list = []
        for run in range(3):
            ev = await llm_score(sc["input"], route_text)
            if ev:
                scores_list.append(ev["scores"])
                print(f"  第{run+1}次: {ev['scores']}")
            else:
                print(f"  第{run+1}次: 评分失败")

        if scores_list:
            avg = {}
            for dim in ["intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"]:
                vals = [s[dim] for s in scores_list if dim in s]
                avg[dim] = sum(vals) / len(vals) if vals else 0
            print(f"  >>> 3次平均: intent={avg['intent_match']:.1f} poi={avg['poi_quality']:.1f} "
                  f"geo={avg['geo_continuity']:.1f} diverse={avg['scene_diversity']:.1f} "
                  f"overall={avg['overall']:.1f}")

            # 好评和差评
            if ev:
                print(f"  优点: {ev.get('good_points', [])[:3]}")
                print(f"  建议: {ev.get('bad_points', [])[:3]}")
            results.append({"scenario": sc["name"], "avg": avg, "runs": scores_list})
        else:
            print(f"  >>> 全部评分失败")
            results.append({"scenario": sc["name"], "avg": None, "runs": []})

    # 汇总
    print("\n" + "=" * 60)
    print("天花板汇总")
    print("=" * 60)
    valid = [r for r in results if r["avg"]]
    if valid:
        for dim in ["intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"]:
            vals = [r["avg"][dim] for r in valid]
            print(f"  {dim}: {sum(vals)/len(vals):.1f} (min={min(vals):.1f}, max={max(vals):.1f})")

    print(f"\n→ 这就是评分系统的天花板。C版本pipeline的7.0离这里差多远，一目了然。")

    # 保存
    with open("docs/logs/perfect_route_ceiling.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
