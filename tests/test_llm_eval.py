"""CityFlow 路线质量评估 — 用 LLM 生成测试集并评估。

用法: python test_llm_eval.py
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx

API_KEY = "os.getenv("AMAP_API_KEY", "")"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
BASE = "http://localhost:8000"

# ── 用 LLM 生成测试场景 ──────────────────────────────────────

SCENARIO_GEN_PROMPT = """你是一个旅游规划测试专家。生成 12 个真实用户的珠海旅游查询。

覆盖以下维度：
- 不同人群：独处、情侣、亲子、朋友、退休
- 不同预算：¥100、¥300、¥500、¥1000、不限
- 不同偏好：自然/文化/美食/购物/运动/拍照
- 不同节奏：闲逛、平衡、特种兵

每个场景格式：
{{
  "id": "scenario_01",
  "input": "用户的自然语言查询",
  "user_profile": "简要描述用户画像",
  "expected_poi_types": ["期望的POI类型列表"],
  "must_avoid": ["应避免的POI类型"],
  "budget": 预算数字,
  "pace": "闲逛型/平衡型/特种兵型"
}}

只输出 JSON 数组。
"""


async def generate_scenarios() -> list[dict]:
    """用 LLM 生成测试场景。"""
    print("🧠 用 LLM 生成测试场景...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": 3000,
                "messages": [{"role": "user", "content": SCENARIO_GEN_PROMPT}],
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            print(f"  API错误: {resp.status_code}")
            return get_fallback_scenarios()

        data = resp.json()
        text = data.get("content", [{}])[0].get("text", "")
        import re
        json_match = re.search(r"\[[\s\S]*\]", text)
        if json_match:
            raw_json = json_match.group()
            # 修复常见 LLM JSON 问题：单引号 → 双引号，末尾逗号
            raw_json = raw_json.replace("'", '"')
            raw_json = re.sub(r",\s*([}\]])", r"\1", raw_json)
            try:
                scenarios = json.loads(raw_json)
                print(f"  ✅ 生成了 {len(scenarios)} 个场景")
                return scenarios
            except json.JSONDecodeError as e:
                print(f"  ⚠ JSON解析失败({e}), 尝试修复...")
                # 更激进的修复：用 ast.literal_eval
                import ast
                try:
                    scenarios = ast.literal_eval(raw_json)
                    print(f"  ✅ ast修复成功, {len(scenarios)} 个场景")
                    return scenarios
                except:
                    pass
        print(f"  ⚠ 解析失败，使用默认场景")
        return get_fallback_scenarios()


def get_fallback_scenarios() -> list[dict]:
    """兜底场景。"""
    return [
        {"id": "s01", "input": "想去海边走走，一个人安静待着", "expected_poi_types": ["海滨", "公园"], "must_avoid": ["健身房", "网吧"], "budget": 300, "pace": "闲逛型"},
        {"id": "s02", "input": "带5岁儿子去珠海玩一天，轻松点", "expected_poi_types": ["公园", "亲子"], "must_avoid": ["酒吧", "健身房"], "budget": 500, "pace": "闲逛型"},
        {"id": "s03", "input": "和女朋友约会，浪漫餐厅+夜景", "expected_poi_types": ["餐饮", "夜景"], "must_avoid": ["网吧", "健身房"], "budget": 800, "pace": "平衡型"},
        {"id": "s04", "input": "想运动一下，爬山或者跑步", "expected_poi_types": ["运动", "公园"], "must_avoid": ["购物", "餐饮"], "budget": 200, "pace": "特种兵型"},
        {"id": "s05", "input": "想去博物馆、历史文化景点逛逛", "expected_poi_types": ["文化", "博物馆"], "must_avoid": ["网吧", "健身房"], "budget": 200, "pace": "平衡型"},
        {"id": "s06", "input": "和三个朋友一起吃吃喝喝", "expected_poi_types": ["餐饮", "美食"], "must_avoid": [], "budget": 1000, "pace": "平衡型"},
        {"id": "s07", "input": "退休了到处走走，看看花鸟鱼虫", "expected_poi_types": ["公园", "自然"], "must_avoid": ["剧烈运动"], "budget": 200, "pace": "闲逛型"},
        {"id": "s08", "input": "想去拍照打卡，出片的地方", "expected_poi_types": ["景点", "拍照"], "must_avoid": ["网吧"], "budget": 300, "pace": "平衡型"},
        {"id": "s09", "input": "预算只有100块，想省钱玩一天", "expected_poi_types": ["免费", "公园"], "must_avoid": ["高消费"], "budget": 100, "pace": "闲逛型"},
        {"id": "s10", "input": "想逛街购物，买点特产", "expected_poi_types": ["购物", "商业街"], "must_avoid": ["运动"], "budget": 600, "pace": "闲逛型"},
        {"id": "s11", "input": "精打细算吃一天，从早吃到晚", "expected_poi_types": ["餐饮", "美食"], "must_avoid": ["购物"], "budget": 300, "pace": "特种兵型"},
        {"id": "s12", "input": "带父母去轻松走走，看看风景", "expected_poi_types": ["公园", "自然", "文化"], "must_avoid": ["剧烈运动", "爬山"], "budget": 500, "pace": "闲逛型"},
    ]


# ── 用 LLM 评估路线质量 ──────────────────────────────────────

EVAL_PROMPT = """你是一个旅游路线质量评审专家。评估以下旅游路线是否符合用户需求。

用户原始需求: {user_input}

用户画像: {profile}

规划出的路线（依次访问）:
{route_str}

从以下维度评分（每项 0-10，10=完美）：
1. **intent_match** - 路线是否符合用户意图（想去海边→有海边POI）
2. **poi_quality** - POI本身是否是值得去的旅游地点（排除网吧、健身房等）
3. **geo_continuity** - 地理上是否合理（不走回头路）
4. **budget_fit** - 预算是否合理
5. **scene_diversity** - 场景是否多样不单调
6. **overall** - 总体合理性

同时列出最多3个最严重的问题。

输出格式（只输出JSON）：
{{
  "scores": {{"intent_match": 0-10, "poi_quality": 0-10, "geo_continuity": 0-10, "budget_fit": 0-10, "scene_diversity": 0-10, "overall": 0-10}},
  "good_points": ["优点1", "优点2"],
  "bad_points": ["问题1", "问题2", "问题3"],
  "needs_llm": ["需要LLM解决的问题"],
  "needs_algorithm": ["需要算法解决的问题"],
  "verdict": "pass/fail"
}}
"""


async def evaluate_route(scenario: dict, route_data: dict, elapsed: float) -> dict:
    """用 LLM 评估路线质量。"""
    route = route_data.get("route", [])
    if not route:
        return {"scenario_id": scenario["id"], "status": "no_route", "scores": {}, "bad_points": ["路线为空"]}

    route_lines = []
    for i, step in enumerate(route, 1):
        p = step.get("poi", {})
        cat = p.get("category", "?")
        price = p.get("avg_price", 0)
        st = p.get("_scene_tags", [])
        route_lines.append(f"  {i}. {p.get('name','?')} ({cat}) ¥{price} 标签:{st}")

    route_str = "\n".join(route_lines)
    profile = scenario.get("user_profile", "未知")
    prompt = EVAL_PROMPT.format(
        user_input=scenario["input"],
        profile=profile,
        route_str=route_str,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                API_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
            if resp.status_code != 200:
                return {"scenario_id": scenario["id"], "status": "eval_error", "error": f"HTTP {resp.status_code}"}

            data = resp.json()
            text = data.get("content", [{}])[0].get("text", "")
            def _fix_json(raw: str) -> str:
                raw = raw.replace("'", '"')
                raw = re.sub(r",\s*([}\]])", r"\1", raw)
                return raw

            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                result = json.loads(_fix_json(json_match.group()))
                result["scenario_id"] = scenario["id"]
                result["status"] = "eval_ok"
                result["elapsed"] = elapsed
                return result
            return {"scenario_id": scenario["id"], "status": "parse_error", "text": text[:200]}
        except Exception as e:
            return {"scenario_id": scenario["id"], "status": "exception", "error": str(e)}


# ── 主流程 ────────────────────────────────────────────────────

async def plan_route(scenario: dict) -> tuple[dict, float]:
    """调用规划接口。"""
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{BASE}/api/plan",
                json={"user_input": scenario["input"], "user_id": f"eval_{scenario['id']}", "start_location": "<auto>"},
            )
            elapsed = time.time() - start

            if resp.status_code != 200:
                return {"route": []}, elapsed

            # 解析 SSE
            result = {}
            current_event = None
            for line in resp.text.split("\n"):
                line = line.strip()
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                elif line.startswith("data: ") and current_event == "done":
                    try:
                        data = json.loads(line[6:])
                        result = data.get("full_route", data)
                    except json.JSONDecodeError:
                        pass

            return result, elapsed
    except Exception as e:
        return {"route": []}, time.time() - start


def print_route(route: list[dict], scenario: dict):
    """打印路线。"""
    if not route:
        print("  (路线为空)")
        return

    total_cost = sum(s.get("poi", {}).get("avg_price", 0) for s in route)
    print(f"  路线 ({len(route)}站, ¥{total_cost}):")
    for i, step in enumerate(route, 1):
        p = step.get("poi", {})
        cat = p.get("category", "?")
        price = p.get("avg_price", 0)
        tags = p.get("_scene_tags", [])
        print(f"    {i}. {p.get('name','?')} [{cat}] ¥{price}")
        if tags:
            print(f"      标签: {', '.join(tags[:3])}")


async def main():
    print("=" * 60)
    print("🌿 CityFlow LLM 路线质量评估")
    print("=" * 60)

    # Step 1: 生成测试场景
    scenarios = await generate_scenarios()
    print(f"\n📋 共 {len(scenarios)} 个测试场景\n")

    # Step 2: 逐个规划并评估
    report = {"pass": 0, "fail": 0, "total": len(scenarios)}
    all_evals = []

    for i, sc in enumerate(scenarios, 1):
        print(f"\n{'─'*50}")
        print(f"[{i}/{len(scenarios)}] {sc.get('input','?')[:60]}")
        print(f"{'─'*50}")

        # 规划
        result, elapsed = await plan_route(sc)
        route = result.get("route", [])
        print_route(route, sc)

        # 评估
        eval_result = await evaluate_route(sc, result, elapsed)
        all_evals.append(eval_result)

        if eval_result.get("status") == "eval_ok":
            scores = eval_result.get("scores", {})
            overall = scores.get("overall", 0)
            passed = overall >= 6
            if passed:
                report["pass"] += 1
            else:
                report["fail"] += 1

            print(f"  评分: intent={scores.get('intent_match','?')} quality={scores.get('poi_quality','?')} "
                  f"geo={scores.get('geo_continuity','?')} budget={scores.get('budget_fit','?')} "
                  f"diverse={scores.get('scene_diversity','?')} overall={overall}")
            for bp in eval_result.get("bad_points", []):
                print(f"  ❌ {bp}")
            print(f"  {'✅ 通过' if passed else '❌ 不通过'} (overall={overall})")
        else:
            print(f"  ⚠ 评估失败: {eval_result.get('error', eval_result.get('status', '?'))}")

        # 写中间结果
        Path("test_llm_results.json").write_text(
            json.dumps(all_evals, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Step 3: 汇总报告
    print(f"\n\n{'='*60}")
    print(f"📊 最终报告: {report['pass']}/{report['total']} 通过")
    print(f"{'='*60}")

    # 汇总需要LLM和需要算法的问题
    needs_llm_all = []
    needs_algo_all = []
    bad_points_all = []

    for ev in all_evals:
        if ev.get("status") == "eval_ok":
            needs_llm_all.extend(ev.get("needs_llm", []))
            needs_algo_all.extend(ev.get("needs_algorithm", []))
            bad_points_all.extend(ev.get("bad_points", []))

    print("\n🔧 需要 LLM 解决的问题:")
    for item in sorted(set(needs_llm_all)):
        print(f"  • {item}")

    print("\n⚙️ 需要算法解决的问题:")
    for item in sorted(set(needs_algo_all)):
        print(f"  • {item}")

    print("\n❌ 常见问题TOP10:")
    from collections import Counter
    for item, cnt in Counter(bad_points_all).most_common(10):
        print(f"  • [{cnt}次] {item}")

    return report


if __name__ == "__main__":
    results = asyncio.run(main())
    sys.exit(0 if results.get("pass", 0) >= results.get("total", 0) * 0.6 else 1)
