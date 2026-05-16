"""生成Golden Test Cases — 用于评估路线规划质量。

用龙猫API生成100个标准答案场景，覆盖所有画像和边界情况。
每个场景包含：用户意图、期望POI类别、期望路线长度、禁止类别、评分权重。

用法:
    python scripts/gen_golden_cases.py
"""
import asyncio
import json
from pathlib import Path

import httpx

API_KEY = "os.getenv("AMAP_API_KEY", "")"
OUTPUT_PATH = Path("tests/golden_cases.json")

# 场景模板：每种画像生成多个变体
SCENARIO_TEMPLATES = [
    # ── 情侣 ──
    {"画像": "情侣", "城市": "珠海", "时段": "下午", "变体": "浪漫海滨"},
    {"画像": "情侣", "城市": "珠海", "时段": "全天", "变体": "一日约会"},
    {"画像": "情侣", "城市": "广州", "时段": "下午", "变体": "文化约会"},
    {"画像": "情侣", "城市": "珠海", "时段": "晚上", "变体": "夜间浪漫"},
    {"画像": "情侣", "城市": "广州", "时段": "晚上", "变体": "珠江夜游"},
    # ── 朋友 ──
    {"画像": "朋友", "城市": "珠海", "时段": "下午", "变体": "轰趴聚会"},
    {"画像": "朋友", "城市": "珠海", "时段": "晚上", "变体": "夜生活"},
    {"画像": "朋友", "城市": "广州", "时段": "全天", "变体": "一日游"},
    {"画像": "朋友", "城市": "广州", "时段": "晚上", "变体": "酒吧街"},
    {"画像": "朋友", "城市": "珠海", "时段": "下午", "变体": "密室逃脱"},
    # ── 文艺独处 ──
    {"画像": "独处", "城市": "珠海", "时段": "下午", "变体": "书店咖啡"},
    {"画像": "独处", "城市": "珠海", "时段": "全天", "变体": "文化漫步"},
    {"画像": "独处", "城市": "广州", "时段": "下午", "变体": "老城文艺"},
    {"画像": "独处", "城市": "广州", "时段": "全天", "变体": "博物馆日"},
    {"画像": "独处", "城市": "珠海", "时段": "上午", "变体": "清晨散步"},
    # ── 亲子 ──
    {"画像": "亲子", "城市": "珠海", "时段": "全天", "变体": "周末遛娃"},
    {"画像": "亲子", "城市": "珠海", "时段": "下午", "变体": "室内游乐"},
    {"画像": "亲子", "城市": "广州", "时段": "全天", "变体": "长隆一日"},
    {"画像": "亲子", "城市": "广州", "时段": "下午", "变体": "科普教育"},
    {"画像": "亲子", "城市": "珠海", "时段": "上午", "变体": "海边亲子"},
    # ── 深夜觅食 ──
    {"画像": "深夜", "城市": "珠海", "时段": "深夜", "变体": "宵夜一条龙"},
    {"画像": "深夜", "城市": "珠海", "时段": "深夜", "变体": "夜市探秘"},
    {"画像": "深夜", "城市": "广州", "时段": "深夜", "变体": "老广宵夜"},
    {"画像": "深夜", "城市": "广州", "时段": "深夜", "变体": "酒吧转场"},
    # ── 极速打卡 ──
    {"画像": "极速", "城市": "珠海", "时段": "下午", "变体": "2小时打卡"},
    {"画像": "极速", "城市": "广州", "时段": "上午", "变体": "半日精华"},
    {"画像": "极速", "城市": "珠海", "时段": "上午", "变体": "快闪珠海"},
    # ── 退休 ──
    {"画像": "退休", "城市": "珠海", "时段": "全天", "变体": "悠闲一日"},
    {"画像": "退休", "城市": "广州", "时段": "上午", "变体": "早茶文化"},
    {"画像": "退休", "城市": "珠海", "时段": "下午", "变体": "公园散步"},
    # ── 预算约束 ──
    {"画像": "情侣", "城市": "珠海", "时段": "下午", "变体": "穷游约会", "特殊约束": "预算100元"},
    {"画像": "朋友", "城市": "珠海", "时段": "下午", "变体": "AA制聚会", "特殊约束": "预算80元"},
    {"画像": "独处", "城市": "广州", "时段": "全天", "变体": "免费文艺", "特殊约束": "预算0元"},
    # ── 时间约束 ──
    {"画像": "极速", "城市": "珠海", "时段": "午间", "变体": "午休1小时", "特殊约束": "1小时"},
    {"画像": "情侣", "城市": "珠海", "时段": "傍晚", "变体": "下班约会", "特殊约束": "2小时"},
    # ── 特殊需求 ──
    {"画像": "亲子", "城市": "珠海", "时段": "全天", "变体": "雨天遛娃", "特殊约束": "室内"},
    {"画像": "情侣", "城市": "珠海", "时段": "下午", "变体": "带宠物约会", "特殊约束": "宠物友好"},
    {"画像": "退休", "城市": "珠海", "时段": "全天", "变体": "轮椅出行", "特殊约束": "无障碍"},
    # ── 混合场景 ──
    {"画像": "朋友", "城市": "珠海", "时段": "全天", "变体": "运动+聚餐"},
    {"画像": "情侣", "城市": "广州", "时段": "全天", "变体": "文化+美食"},
    {"画像": "亲子", "城市": "珠海", "时段": "全天", "变体": "游乐+科普"},
    {"画像": "独处", "城市": "珠海", "时段": "全天", "变体": "阅读+咖啡+展览"},
]

# 额外场景：批量扩到100个（同一画像不同城市/时段组合）
EXTRA_SCENES = []
cities = ["珠海", "广州"]
for profile in ["情侣", "朋友", "独处", "亲子", "深夜", "极速", "退休"]:
    for city in cities:
        for period in ["上午", "下午", "晚上", "全天"]:
            EXTRA_SCENES.append({
                "画像": profile, "城市": city, "时段": period,
                "变体": f"{profile}_{city}_{period}"
            })

# 去重：和SCENARIO_TEMPLATES不重复
_seen = {(s["画像"], s["城市"], s["时段"], s["变体"]) for s in SCENARIO_TEMPLATES}
for s in EXTRA_SCENES:
    key = (s["画像"], s["城市"], s["时段"], s["变体"])
    if key not in _seen:
        SCENARIO_TEMPLATES.append(s)
        _seen.add(key)
    if len(SCENARIO_TEMPLATES) >= 100:
        break

SCENARIO_TEMPLATES = SCENARIO_TEMPLATES[:100]


async def llm_json(prompt: str, max_tokens: int = 4000) -> dict | None:
    """调用龙猫API生成JSON"""
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(
            "https://api.longcat.chat/anthropic/v1/messages",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "LongCat-Flash-Lite",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
        )
        if r.status_code != 200:
            print(f"  API Error: {r.status_code}")
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


def build_batch_prompt(scenarios: list[dict]) -> str:
    """构建批量生成prompt"""
    scenario_list = "\n".join(
        f"  {i+1}. [{s['画像']}] {s['城市']}·{s['时段']}·{s['变体']}"
        + (f" (特殊: {s['特殊约束']})" if s.get("特殊约束") else "")
        for i, s in enumerate(scenarios)
    )

    return f"""你是城市出行规划评估专家。请为以下{len(scenarios)}个场景生成"标准答案"。

# 场景列表
{scenario_list}

# 每个场景需要生成的字段
```json
{{
  "id": "gc_001",
  "scenario": "情侣_珠海_下午_浪漫海滨",
  "profile": "情侣",
  "city": "珠海",
  "intent": {{
    "time": {{"period": "下午", "start": "14:00", "end": "22:00"}},
    "budget": {{"per_person": 300, "type": "弹性"}},
    "group": {{"size": 2, "type": "情侣"}},
    "preferences": {{"culture": 0.5, "food": 0.8, "nature": 0.6, "social": 0.5, "excitement": 0.4, "tranquility": 0.6}},
    "pace": "平衡型",
    "hard_constraints": ["有氛围感", "可拍照"],
    "scene_requirements": ["拍照出片", "情侣"]
  }},
  "expected": {{
    "categories": ["景点", "餐饮", "文化", "咖啡馆", "海景咖啡馆"],
    "forbidden": ["运动", "娱乐"],
    "route_length": [3, 6],
    "must_have_tags": ["浪漫", "拍照", "海滨"],
    "emotion_profile": {{
      "excitement": [0.3, 0.7],
      "tranquility": [0.4, 0.8],
      "sociability": [0.3, 0.7]
    }}
  }},
  "weights": {{
    "category_coverage": 30,
    "emotion_fit": 30,
    "feasibility": 20,
    "intent_match": 20
  }}
}}
```

# 字段说明
- intent: 模拟真实用户输入，preferences各维度0-1
- expected.categories: 路线中应该出现的POI类别（至少3个）
- expected.forbidden: 路线中不应该出现的类别
- expected.route_length: [最少站数, 最多站数]
- expected.must_have_tags: 路线中至少有1个POI包含这些tag
- expected.emotion_profile: 路线整体情绪各维度应落在的范围
- weights: 4项评分权重，总和100

# 要求
1. intent要真实自然，符合该画像的典型需求
2. preferences要合理（情侣偏food/nature，朋友偏social/excitement，独处偏tranquility/culture）
3. budget要符合画像（独处/退休偏低，朋友/情侣适中）
4. hard_constraints要从实际场景出发
5. expected要合理可达成（不要出现矛盾需求）

输出格式：{{"cases": [...]}}，包含{len(scenarios)}个case。"""


async def main():
    print(f"准备生成 {len(SCENARIO_TEMPLATES)} 个golden test cases...")

    all_cases = []
    batch_size = 10  # 每批10个场景

    for i in range(0, len(SCENARIO_TEMPLATES), batch_size):
        batch = SCENARIO_TEMPLATES[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(SCENARIO_TEMPLATES) + batch_size - 1) // batch_size

        print(f"\n批次 {batch_num}/{total_batches} ({len(batch)} 个场景)...")

        prompt = build_batch_prompt(batch)
        result = await llm_json(prompt, max_tokens=8000)

        if not result or "cases" not in result:
            print("  首次失败，重试...")
            await asyncio.sleep(2)
            result = await llm_json(prompt, max_tokens=8000)
            if not result or "cases" not in result:
                print("  二次失败，跳过")
                continue

        cases = result["cases"]
        # 修正ID
        for j, case in enumerate(cases):
            case["id"] = f"gc_{i+j+1:03d}"

        all_cases.extend(cases)
        print(f"  生成 {len(cases)} 个")

        # 每批保存
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(all_cases, ensure_ascii=False, indent=2), encoding="utf-8")

        await asyncio.sleep(1)

    print(f"\n完成! 共 {len(all_cases)} 个golden test cases")
    print(f"保存至: {OUTPUT_PATH}")

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
