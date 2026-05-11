"""扩充Golden Test Cases到1000个 — 用龙猫API批量生成。

用法:
    python scripts/gen_golden_1000.py
"""
import asyncio
import json
from pathlib import Path

import httpx

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
OUTPUT_PATH = Path("tests/golden_cases.json")

# 画像配置
PROFILES = [
    {"name": "情侣", "group_type": "情侣", "prefs": {"culture": 0.5, "food": 0.8, "nature": 0.6, "social": 0.5}},
    {"name": "朋友", "group_type": "朋友", "prefs": {"culture": 0.3, "food": 0.7, "nature": 0.3, "social": 0.9}},
    {"name": "独处", "group_type": "个人", "prefs": {"culture": 0.8, "food": 0.4, "nature": 0.6, "social": 0.1}},
    {"name": "亲子", "group_type": "亲子家庭", "prefs": {"culture": 0.5, "food": 0.6, "nature": 0.5, "social": 0.4}},
    {"name": "退休", "group_type": "退休", "prefs": {"culture": 0.7, "food": 0.5, "nature": 0.6, "social": 0.3}},
    {"name": "深夜", "group_type": "朋友", "prefs": {"culture": 0.2, "food": 0.8, "nature": 0.1, "social": 0.9}},
    {"name": "极速", "group_type": "个人", "prefs": {"culture": 0.5, "food": 0.4, "nature": 0.5, "social": 0.3}},
]

CITIES = ["珠海", "广州"]
PERIODS = ["上午", "下午", "晚上", "全天"]
BUDGETS = [50, 80, 100, 150, 200, 300]

# 变体列表
VARIANTS = [
    "浪漫约会", "朋友聚会", "独处时光", "亲子出游", "退休休闲",
    "深夜觅食", "极速打卡", "文化之旅", "美食探索", "自然风光",
    "海滨漫步", "城市漫步", "夜景欣赏", "购物天堂", "运动健身",
    "咖啡时光", "书店阅读", "密室逃脱", "剧本杀", "酒吧夜生活",
    "早茶文化", "博物馆日", "公园散步", "海边日落", "夜市探秘",
]


async def llm_json(prompt: str, max_tokens: int = 4000) -> dict | None:
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(
            "https://api.longcat.chat/anthropic/v1/messages",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "LongCat-Flash-Lite",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
        )
        if r.status_code != 200:
            return None
        text = r.json().get("content", [{}])[0].get("text", "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None


def build_prompt(profile: dict, city: str, period: str, variant: str, budget: int, idx: int) -> str:
    # 时段映射
    time_map = {
        "上午": ("09:00", "12:00"),
        "下午": ("14:00", "18:00"),
        "晚上": ("19:00", "23:00"),
        "全天": ("09:00", "18:00"),
    }
    start, end = time_map[period]

    return f"""你是城市出行规划评估专家。为以下场景生成1个标准答案。

场景：{profile['name']}·{city}·{period}·{variant}
画像: {profile['name']}({profile['group_type']})
城市: {city}
时段: {start}-{end}
预算: {budget}元/人

POI数据库实际类别（必须用这些类别）:
餐饮, 购物, 文化, 景点, 酒店, 运动, 娱乐, 剧本杀, 咖啡馆, 密室逃脱,
夜市, 夜市小吃, 海景咖啡馆, 温泉SPA, 水上运动场所, 户外攀岩, 室内攀岩,
书店, 科技, 科技体验, 游戏, 益智, 恐怖密室, 休闲, 便利店, 自然风光, 文艺

POI数据库实际tag（必须用这些tag）:
免费, 涨知识, 值得去, 拍照出片, 打卡, 悠闲, 夜景, 自然, 亲子, 浪漫,
性价比高, 老字号, 排队, 网红店, 适合聚餐, 环境好, 味道正宗, 服务好,
交通便利, 停车方便, 休闲放松, 自然风光, 文化历史, 安静, 干净, 海滨,
室内, 运动, 漫步, 咖啡, 深夜, 聚会, 出片, 情侣, 公园, 经济

输出JSON格式:
{{
  "id": "gc_{idx:03d}",
  "scenario": "{profile['name']}_{city}_{period}_{variant}",
  "profile": "{profile['name']}",
  "city": "{city}",
  "intent": {{
    "time": {{"period": "{period}", "start": "{start}", "end": "{end}"}},
    "budget": {{"per_person": {budget}, "type": "弹性"}},
    "group": {{"size": 2, "type": "{profile['group_type']}"}},
    "preferences": {json.dumps(profile['prefs'])},
    "pace": "平衡型",
    "hard_constraints": ["2-3个真实约束"],
    "scene_requirements": ["2-3个场景需求tag"]
  }},
  "expected": {{
    "categories": ["3-5个POI类别，必须用上面的实际类别"],
    "forbidden": ["2-3个禁止类别，用描述性词语如'高强度运动'、'嘈杂场所'"],
    "route_length": [最少站数, 最多站数],
    "must_have_tags": ["3-5个tag，必须用上面的实际tag"],
    "emotion_profile": {{"excitement": [lo, hi], "tranquility": [lo, hi], "sociability": [lo, hi]}}
  }},
  "weights": {{"category_coverage": 30, "emotion_fit": 30, "feasibility": 20, "intent_match": 20}}
}}

注意：
- categories必须用POI数据库实际类别
- must_have_tags必须用POI数据库实际tag
- forbidden用描述性词语（不需要对应POI类别）
- hard_constraints要真实自然
- route_length要合理（2-8站）
- 不要生成矛盾需求（如预算0元、深夜3点等）
- 输出纯JSON，不要额外说明"""


async def generate_batch(batch: list[dict], start_idx: int) -> list[dict]:
    """生成一批golden cases"""
    cases = []
    for i, item in enumerate(batch):
        idx = start_idx + i
        prompt = build_prompt(
            item["profile"], item["city"], item["period"],
            item["variant"], item["budget"], idx
        )
        result = await llm_json(prompt)
        if result and "id" in result:
            result["id"] = f"gc_{idx:03d}"
            cases.append(result)
            if (i + 1) % 10 == 0:
                print(f"  已生成 {i+1}/{len(batch)} 个", flush=True)
        await asyncio.sleep(0.5)
    return cases


async def main():
    # 生成场景组合
    scenarios = []
    idx = 1
    for profile in PROFILES:
        for city in CITIES:
            for period in PERIODS:
                for variant in VARIANTS:
                    for budget in BUDGETS:
                        scenarios.append({
                            "profile": profile,
                            "city": city,
                            "period": period,
                            "variant": variant,
                            "budget": budget,
                        })
                        idx += 1

    # 去重并限制到1000个
    seen = set()
    unique_scenarios = []
    for s in scenarios:
        key = (s["profile"]["name"], s["city"], s["period"], s["variant"], s["budget"])
        if key not in seen:
            seen.add(key)
            unique_scenarios.append(s)
        if len(unique_scenarios) >= 1000:
            break

    print(f"准备生成 {len(unique_scenarios)} 个golden cases")

    # 分批生成（每批20个）
    batch_size = 20
    all_cases = []

    # 加载已有cases
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        all_cases.extend(existing)
        print(f"已有 {len(existing)} 个cases")

    start_idx = len(all_cases) + 1

    for i in range(0, len(unique_scenarios), batch_size):
        batch = unique_scenarios[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(unique_scenarios) + batch_size - 1) // batch_size

        print(f"\n批次 {batch_num}/{total_batches} ({len(batch)} 个场景)...")
        cases = await generate_batch(batch, start_idx + i)
        all_cases.extend(cases)

        # 每批保存
        OUTPUT_PATH.write_text(
            json.dumps(all_cases, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  本批新增 {len(cases)} 个，总计 {len(all_cases)} 个")

    print(f"\n完成! 总计 {len(all_cases)} 个golden cases")

    # 统计
    profiles = {}
    for c in all_cases:
        p = c.get("profile", "未知")
        profiles[p] = profiles.get(p, 0) + 1
    print("\n画像分布:")
    for p, n in sorted(profiles.items(), key=lambda x: -x[1]):
        print(f"  {p}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
