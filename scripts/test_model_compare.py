"""单点专家模型对比测试。

用法: PYTHONPATH=. python scripts/test_model_compare.py

测试流程：
1. 用现有pipeline跑rule_guard拿到candidates
2. 构造极窄的food specialist prompt
3. 分别用不同模型调用，对比输出
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx

# ── 模型配置 ──

MODELS = {
    "Qwen3.6-27B": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-bkamiuygydnklotgniygaamxbnoostamrghxnjyvqwwfjhoo",
        "model": "Qwen/Qwen3.6-27B",
    },
    "Qwen3.6-35B-A3B": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-bkamiuygydnklotgniygaamxbnoostamrghxnjyvqwwfjhoo",
        "model": "Qwen/Qwen3.6-35B-A3B",
    },
    "Qwen3.5-27B": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-bkamiuygydnklotgniygaamxbnoostamrghxnjyvqwwfjhoo",
        "model": "Qwen/Qwen3.5-27B",
    },
    "Qwen3.5-35B-A3B": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-bkamiuygydnklotgniygaamxbnoostamrghxnjyvqwwfjhoo",
        "model": "Qwen/Qwen3.5-35B-A3B",
    },
    "Ling-mini-2.0": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-bkamiuygydnklotgniygaamxbnoostamrghxnjyvqwwfjhoo",
        "model": "inclusionAI/Ling-mini-2.0",
    },
    "MiniMax-M2.5": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-bkamiuygydnklotgniygaamxbnoostamrghxnjyvqwwfjhoo",
        "model": "MiniMaxAI/MiniMax-M2.5",
    },
}

# ── 测试场景（5个失败场景） ──

TEST_CASES = [
    {
        "id": 11,
        "name": "朋友聚餐",
        "input": "周末和朋友珠海聚一下，吃吃喝喝",
        "scene_type": "美食型",
        "intent_hint": "用户要和朋友聚餐，核心是吃+社交",
        "max_food": 5,
    },
    {
        "id": 21,
        "name": "海鲜大餐",
        "input": "珠海吃海鲜，想吃最新鲜最划算的",
        "scene_type": "美食型",
        "intent_hint": "核心是海鲜！必须推荐海鲜类POI，至少3个海鲜相关",
        "max_food": 4,
    },
    {
        "id": 22,
        "name": "美食探索",
        "input": "珠海美食一日游，想吃海鲜和本地特色",
        "scene_type": "美食型",
        "intent_hint": "海鲜+本地特色，分散到午/晚餐时段",
        "max_food": 5,
    },
    {
        "id": 25,
        "name": "预算吃垮珠海",
        "input": "珠海一天吃5顿，预算300，怎么安排",
        "scene_type": "美食型",
        "intent_hint": "用户要吃5顿！必须推荐5家，预算300元",
        "max_food": 5,
    },
    {
        "id": 30,
        "name": "模糊需求",
        "input": "珠海有啥好玩的",
        "scene_type": "观光型",
        "intent_hint": "模糊输入，推荐珠海代表性景点（海滨+地标）",
        "max_food": 2,
    },
]

# ── 极窄专家prompt（MoE极致拆分后的food specialist） ──

FOOD_SPECIALIST_PROMPT = """你是珠海美食推荐专家。任务极窄：从候选餐厅中挑选最合适的组合。

硬约束（必须遵守）：
1. 只能从候选列表里选
2. 输出JSON格式: {{"picks":[{{"name":"店名","reason":"理由","confidence":0.8,"meal_time":"早餐/午餐/下午茶/晚餐/夜宵"}}]}}
3. 选{max_food}个
4. 餐饮必须分散到不同时段（早餐/午餐/下午茶/晚餐/夜宵），同一时段不超过2家
5. 同一子类型（海鲜/正餐/小吃/甜品/美食街）不超过2家
6. 综合美食街（夜市/美食街/海鲜街）最多选1个

{intent_hint}

只输出JSON，不要输出其他内容。"""


async def load_candidates() -> list[dict]:
    """从mock server或本地JSON加载POI数据。"""
    from backend.agents_v3.experts.base import _load_all_pois
    pois = await _load_all_pois()
    return pois


def build_food_candidates(all_pois: list[dict]) -> list[dict]:
    """构建餐饮候选池（模拟food_expert的逻辑）。"""
    food_names = [
        "餐厅", "海鲜", "烧", "煲", "粉", "面", "火锅", "烧烤", "夜市", "粥", "蚝", "排档",
        "甜品", "奶茶", "冰", "茶餐厅", "柠檬", "美食街", "海鲜街", "老街",
    ]
    food_cats = ["餐饮", "美食", "小吃", "海鲜", "餐厅", "夜市", "茶餐厅", "甜品", "饮品"]
    foods = [
        p for p in all_pois
        if (any(kw in p.get("category", "") for kw in food_cats)
            or any(kw in p.get("name", "") for kw in food_names))
        and p.get("category", "") not in ["购物", "酒店", "住宿"]
        and p.get("rating") is not None
    ]
    return foods


def stratified_sample(foods: list[dict], max_per_cat: int = 3) -> list[dict]:
    """分层采样（和food_expert一样的逻辑）。"""
    subcats = {
        "海鲜": ["海鲜", "蚝", "鱼排", "渔港"],
        "正餐": ["餐厅", "烧", "煲", "火锅", "烧烤"],
        "小吃": ["粉", "面", "粥", "小吃", "排档"],
        "茶餐厅/甜品": ["茶餐厅", "甜品", "奶茶", "冰", "柠檬", "饮品"],
        "综合美食街": ["夜市", "美食街", "海鲜街", "老街"],
    }
    result = []
    seen = set()
    for sub_name, kws in subcats.items():
        bucket = [f for f in foods if any(kw in f.get("name", "") or kw in f.get("category", "") for kw in kws)
                  and f.get("name", "") not in seen]
        bucket.sort(key=lambda f: f.get("rating", 0), reverse=True)
        for f in bucket[:max_per_cat]:
            result.append(f)
            seen.add(f.get("name", ""))
    return result


async def call_model(model_cfg: dict, system: str, user: str) -> tuple[dict | None, float]:
    """调用指定模型，返回结果和耗时。"""
    t0 = time.time()
    for _ in range(2):
        try:
            body = {
                "model": model_cfg["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 2000,
                "temperature": 0.1,
            }
            # Qwen3.x / GLM-Z1需要关闭thinking模式
            if "Qwen3" in model_cfg["model"] or "GLM-Z1" in model_cfg["model"]:
                body["enable_thinking"] = False

            async with httpx.AsyncClient(timeout=90.0) as c:
                r = await c.post(
                    f"{model_cfg['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {model_cfg['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                if r.status_code != 200:
                    print(f"    API error {r.status_code}: {r.text[:200]}")
                    continue
                text = r.json()["choices"][0]["message"].get("content") or ""
                text = text.strip()
                if not text:
                    print(f"    Empty response from {model_cfg['model']}")
                    continue
                # 提取JSON（可能被markdown包裹）
                if "```" in text:
                    text = text.split("```")[1].split("```")[0]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                data = json.loads(text)
                elapsed = time.time() - t0
                return data, elapsed
        except Exception as e:
            print(f"    Error: {e}")
            await asyncio.sleep(1)
    return None, time.time() - t0


async def main():
    print("=" * 70)
    print("单点专家模型对比测试")
    print("=" * 70)

    # 加载数据
    all_pois = await load_candidates()
    foods = build_food_candidates(all_pois)
    sampled = stratified_sample(foods, max_per_cat=2)
    summaries = [
        {
            "name": f.get("name", ""),
            "cat": f.get("category", ""),
            "price": f.get("avg_price", 0),
            "rating": f.get("rating", 0),
            "tags": f.get("tags", [])[:3],
            "lat": round(f.get("lat", 0), 3),
            "lng": round(f.get("lng", 0), 3),
        }
        for f in sampled
    ]
    print(f"\n候选池: {len(foods)}家餐饮, 分层采样: {len(sampled)}家")
    _sub = {"海鲜": ["海鲜", "蚝"], "正餐": ["餐厅", "烧", "煲"], "小吃": ["粉", "面", "粥"], "甜品": ["茶餐厅", "甜品", "奶茶"], "美食街": ["夜市", "美食街", "海鲜街"]}
    _dist = {n: sum(1 for f in sampled if any(kw in f.get("name", "") or kw in f.get("category", "") for kw in kws)) for n, kws in _sub.items()}
    print(f"采样分布: {_dist}")

    results = []

    for tc in TEST_CASES:
        print(f"\n{'─' * 70}")
        print(f"#{tc['id']} {tc['name']} | {tc['input']}")
        print(f"场景: {tc['scene_type']} | 需选: {tc['max_food']}个")
        print(f"{'─' * 70}")

        system = FOOD_SPECIALIST_PROMPT.format(
            max_food=tc["max_food"],
            intent_hint=tc["intent_hint"],
        )
        user = f"""用户需求: {tc['input']}
场景类型: {tc['scene_type']}

候选餐厅（分层采样）:
{json.dumps(summaries, ensure_ascii=False)}"""

        for model_name, model_cfg in MODELS.items():
            data, elapsed = await call_model(model_cfg, system, user)

            if data and "picks" in data:
                picks = data["picks"]
                names = [p.get("name", "?") for p in picks]
                meals = [p.get("meal_time", "?") for p in picks]
                reasons = [p.get("reason", "")[:40] for p in picks]

                # 检查约束
                issues = []
                # 同时段检查
                meal_counts = {}
                for m in meals:
                    meal_counts[m] = meal_counts.get(m, 0) + 1
                for m, c in meal_counts.items():
                    if c > 2:
                        issues.append(f"同时段{m}有{c}家")

                # 是否来自候选池
                valid_names = {s["name"] for s in summaries}
                invalid = [n for n in names if n not in valid_names and not any(n in vn or vn in n for vn in valid_names)]
                if invalid:
                    issues.append(f"不在候选池: {invalid}")

                # 数量
                if len(picks) != tc["max_food"]:
                    issues.append(f"数量{len(picks)}≠{tc['max_food']}")

                print(f"\n  [{model_name}] {elapsed:.1f}s | 选了{len(picks)}个")
                for i, p in enumerate(picks):
                    print(f"    {i+1}. {p.get('name','?')} ({p.get('meal_time','?')}) — {p.get('reason','')[:50]}")
                if issues:
                    print(f"    ⚠ {' | '.join(issues)}")
                else:
                    print(f"    ✅ 约束全部通过")

                results.append({
                    "scenario": tc["id"],
                    "model": model_name,
                    "elapsed": round(elapsed, 1),
                    "picks": len(picks),
                    "names": names,
                    "issues": issues,
                })
            else:
                print(f"\n  [{model_name}] {elapsed:.1f}s | ❌ 输出解析失败")
                print(f"    raw: {str(data)[:200] if data else 'None'}")
                results.append({
                    "scenario": tc["id"],
                    "model": model_name,
                    "elapsed": round(elapsed, 1),
                    "picks": 0,
                    "names": [],
                    "issues": ["输出解析失败"],
                })

    # 汇总
    print(f"\n{'=' * 70}")
    print("汇总对比")
    print(f"{'=' * 70}")
    print(f"{'场景':<12}", end="")
    for m in MODELS:
        print(f" {m:<18}", end="")
    print()
    print(f"{'─' * 90}")

    for tc in TEST_CASES:
        print(f"#{tc['id']:>2} {tc['name']:<8}", end="")
        for m in MODELS:
            r = next((r for r in results if r["scenario"] == tc["id"] and r["model"] == m), None)
            if r:
                ok = "✅" if not r["issues"] else "⚠️"
                print(f" {ok}{r['picks']}个/{r['elapsed']}s".ljust(18), end="")
            else:
                print(f" {'—':<18}", end="")
        print()

    # 保存结果
    out_path = "docs/baseline/model_compare_results.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
