"""CityFlow LLM评估框架 — 生成测试场景 + 批量评分 + 趋势追踪

用法:
  python eval_framework.py generate    # 生成20个测试场景
  python eval_framework.py run         # 跑评测
  python eval_framework.py report      # 出报告
"""

import asyncio, json, re, sys, time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
BASE = "http://localhost:8000"
DATA_DIR = Path(__file__).parent / "eval_data"
DATA_DIR.mkdir(exist_ok=True)

import httpx


async def llm(prompt: str, max_tokens: int = 3000) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=90.0) as c:
            r = await c.post(API_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"model": "LongCat-Flash-Lite", "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.1,
                      "response_format": {"type": "json_object"}})
            if r.status_code == 200:
                return r.json().get("content", [{}])[0].get("text", "")
    except Exception as e:
        print(f"  LLM Error: {e}")
    return None


def extract_json(text: str):
    # 去掉 markdown 代码块标记
    text = re.sub(r'```json\s*|\s*```|```', '', text)
    text = text.replace("'", '"')
    text = re.sub(r',\s*([}\]])', r'\1', text)
    m = re.search(r'\[[\s\S]*\]', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    return None


def load_scenarios() -> list[dict]:
    path = DATA_DIR / "scenarios.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_scenarios(scenarios: list[dict]):
    (DATA_DIR / "scenarios.json").write_text(json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8")


def load_results() -> list[dict]:
    path = DATA_DIR / "results.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_results(results: list[dict]):
    (DATA_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# 生成测试场景
# ═══════════════════════════════════════════════════════════════

GEN_PROMPT = """你是一个旅游测试专家。生成20个真实用户的珠海旅游查询。

每个场景必须包括不同的人群/预算/偏好组合。格式：
{{
  "id": "S{编号(两位数)}",
  "input": "用户自然语言查询",
  "profile": "用户画像一句话",
  "expected_tags": ["期望的场景标签(从下面选)"],
  "avoid_tags": ["应避免的标签"],
  "budget": 预算数字,
  "pace": "闲逛型/平衡型/特种兵型",
  "group": "独处/情侣/亲子/朋友/退休"
}}

场景标签可选：海滨,山景,公园,夜景,文化历史,自然风光,拍照出片,打卡热点,品质体验,运动健身,休闲放松,亲子,情侣,美食,购物

覆盖：
- 人群：独处x4, 情侣x4, 亲子x4, 朋友x4, 退休x4
- 预算：¥100, ¥200, ¥500, ¥1000, 不限
- 偏好：自然/文化/美食/运动/拍照/购物/安静
- 特殊需求：带宠物/无障碍/下雨天/冬季/非标体验

只输出 JSON 数组。"""


async def cmd_generate(count: int = 20):
    print(f"🌿 生成 {count} 个测试场景...")
    text = await llm(f"生成{count}个珠海旅游测试场景。{GEN_PROMPT.split('只输出')[0]}只输出JSON数组。", max_tokens=6000)
    if not text:
        print("  ❌ LLM 无响应")
        return
    scenarios = extract_json(text)
    if not isinstance(scenarios, list):
        print(f"  ❌ 解析失败: {text[:200]}")
        return

    # 标准化ID
    for i, s in enumerate(scenarios):
        s["id"] = f"S{i+1:02d}"
    save_scenarios(scenarios)
    print(f"  ✅ 保存 {len(scenarios)} 个场景到 eval_data/scenarios.json")

    # 统计
    groups = Counter(s.get("group", "?") for s in scenarios)
    budgets = Counter(s.get("budget", "?") for s in scenarios)
    print(f"  人群: {dict(groups)}")
    print(f"  预算: {dict(budgets)}")


# ═══════════════════════════════════════════════════════════════
# 运行评测
# ═══════════════════════════════════════════════════════════════

async def cmd_run():
    scenarios = load_scenarios()
    if not scenarios:
        print("❌ 无场景，先运行 generate")
        return

    print(f"🌿 评测 {len(scenarios)} 个场景...")
    results = load_results()
    done_ids = {r["scenario_id"] for r in results}

    for sc in scenarios:
        if sc["id"] in done_ids:
            print(f"  SKIP {sc['id']} (already done)")
            continue

        print(f"\n  [{sc['id']}] {sc['input'][:60]}...")
        start = time.time()

        # 调用规划API
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                resp = await c.post(f"{BASE}/api/plan",
                    json={"user_input": sc["input"], "user_id": f"eval_{sc['id']}", "start_location": "<auto>"})
                elapsed = time.time() - start

                if resp.status_code != 200:
                    results.append({"scenario_id": sc["id"], "status": "error", "error": f"HTTP {resp.status_code}", "elapsed": elapsed})
                    continue

                # 解析SSE拿路线
                route = []
                current_event = None
                for line in resp.text.split("\n"):
                    line = line.strip()
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: ") and current_event == "done":
                        try:
                            data = json.loads(line[6:])
                            route = data.get("full_route", {}).get("route", [])
                        except:
                            pass

                # LLM评分
                eval_result = await llm_score(sc, route, elapsed)
                results.append(eval_result)
                save_results(results)

                score = eval_result.get("scores", {}).get("overall", 0)
                status = "✅" if score >= 6.5 else "❌"
                print(f"    {status} overall={score}/10 intent={eval_result.get('scores',{}).get('intent_match','?')} poi_q={eval_result.get('scores',{}).get('poi_quality','?')} ({elapsed:.0f}s)")
        except Exception as e:
            print(f"    ❌ Error: {e}")

    # 汇总
    await cmd_report()


async def llm_score(scenario: dict, route: list, elapsed: float) -> dict:
    """LLM给路线评分。"""
    if not route:
        return {"scenario_id": scenario["id"], "status": "no_route", "scores": {"overall": 0}, "bad_points": ["路线为空"], "elapsed": elapsed}

    route_str = "\n".join(
        f'  {i+1}. {s["poi"]["name"]} [{s["poi"].get("category","?")}] ¥{s["poi"].get("avg_price",0)} 标签:{s["poi"].get("_scene_tags",[])}'
        for i, s in enumerate(route))

    prompt = f"""你是一个旅游路线质量评审专家。评估以下路线是否符合用户需求。

用户需求: {scenario['input']}
用户画像: {scenario.get('profile','?')}
期望场景标签: {scenario.get('expected_tags',[])}
应避免: {scenario.get('avoid_tags',[])}

路线:
{route_str}

从以下维度评分(0-10):
1. intent_match - 路线是否符合用户需求和场景标签
2. poi_quality - POI本身是否是值得去的旅游地点
3. geo_continuity - 地理上是否合理(不走回头路)
4. budget_fit - 预算是否合理
5. scene_diversity - 场景是否多样
6. overall - 总体合理性

列出最多3个最严重问题。

输出JSON:
{{"scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"budget_fit":N,"scene_diversity":N,"overall":N}},"bad_points":["问题1","问题2"],"verdict":"pass/fail"}}"""

    # 重试3次
    for attempt in range(3):
        text = await llm(prompt, max_tokens=2000)
        if text:
            # 直接用 json.loads 解析（extract_json 有时会莫名失败）
            try:
                data = json.loads(text)
                if isinstance(data, dict) and "scores" in data:
                    scores = data["scores"]
                    # 修复 LLM 对 overall 的拼写错误
                    for k in list(scores.keys()):
                        if k != "overall" and k.startswith("over"):
                            scores["overall"] = scores.pop(k)
                    # JSON mode 可能输出字符串数字，转 int
                    for k in list(scores.keys()):
                        if isinstance(scores[k], str) and scores[k].isdigit():
                            scores[k] = int(scores[k])
                    data["scenario_id"] = scenario["id"]
                    data["status"] = "eval_ok"
                    data["elapsed"] = elapsed
                    return data
            except json.JSONDecodeError:
                pass
            data = extract_json(text)
            if isinstance(data, dict) and "scores" in data:
                data["scenario_id"] = scenario["id"]
                data["status"] = "eval_ok"
                data["elapsed"] = elapsed
                return data
            if attempt == 0:
                print(f"    ⚠ LLM解析失败(长度={len(text)}, 原始={repr(text[:150])})")
                (DATA_DIR / f"raw_{scenario['id']}.txt").write_text(text, encoding="utf-8")
        else:
            if attempt == 0:
                print(f"    ⚠ LLM无响应, 重试...")
        await asyncio.sleep(1)

    return {"scenario_id": scenario["id"], "status": "parse_error", "scores": {"overall": 0}, "elapsed": elapsed}


# ═══════════════════════════════════════════════════════════════
# 报告
# ═══════════════════════════════════════════════════════════════

async def cmd_report():
    results = load_results()
    scenarios = load_scenarios()
    if not results:
        print("无结果")
        return

    total = len(results)
    passed = sum(1 for r in results if r.get("scores", {}).get("overall", 0) >= 6.5)
    pass_rate = passed / total * 100 if total else 0

    # 各维度平均分
    dims = ["intent_match", "poi_quality", "geo_continuity", "budget_fit", "scene_diversity", "overall"]
    avg = {d: sum(r.get("scores", {}).get(d, 0) for r in results) / total for d in dims}

    # 问题统计
    all_issues = [bp for r in results for bp in r.get("bad_points", [])]
    top_issues = Counter(all_issues).most_common(5)

    print(f"\n{'='*50}")
    print(f"📊 评测报告")
    print(f"{'='*50}")
    print(f"  场景数: {total}  |  通过: {passed}  | 通过率: {pass_rate:.0f}%")
    print(f"\n  各维度平均分:")
    for d in dims:
        bar = "█" * int(avg[d]) + "░" * (10 - int(avg[d]))
        print(f"    {d:15s} {bar} {avg[d]:.1f}")
    print(f"\n  TOP问题:")
    for issue, cnt in top_issues:
        print(f"    [{cnt}次] {issue}")

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "passed": passed,
        "pass_rate": round(pass_rate, 1),
        "avg_scores": avg,
        "top_issues": [{"issue": i, "count": c} for i, c in top_issues],
    }
    (DATA_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return pass_rate


# ═══════════════════════════════════════════════════════════════
# 生成更多场景(扩展到1000)
# ═══════════════════════════════════════════════════════════════

async def cmd_expand(target: int = 200):
    """分批生成直到达到target个场景。"""
    current = load_scenarios()
    existing_inputs = {s["input"] for s in current}

    batch = 20
    while len(current) < target:
        print(f"\n当前{len(current)}个，目标{target}，生成{batch}个...")
        text = await llm(f"""生成{batch}个珠海旅游测试场景，不要重复已有场景。
已有场景: {list(existing_inputs)[:5]}...

{GEN_PROMPT.split('只输出')[0]}
只输出JSON数组。""", max_tokens=6000)

        scenarios = extract_json(text)
        if not isinstance(scenarios, list):
            print(f"  解析失败，重试")
            continue

        # 去重
        new_count = 0
        for s in scenarios:
            inp = s.get("input", "")
            if inp and inp not in existing_inputs:
                s["id"] = f"S{len(current)+1:02d}"
                current.append(s)
                existing_inputs.add(inp)
                new_count += 1

        print(f"  新增{new_count}个，共{len(current)}个")
        save_scenarios(current)
        if new_count == 0:
            break  # 防止无限循环

    print(f"\n✅ 完成: {len(current)}个场景")


# ═══════════════════════════════════════════════════════════════
# CLI入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "generate":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        asyncio.run(cmd_generate(count))
    elif cmd == "run":
        asyncio.run(cmd_run())
    elif cmd == "report":
        asyncio.run(cmd_report())
    elif cmd == "expand":
        target = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        asyncio.run(cmd_expand(target))
    else:
        print("用法:")
        print("  python eval_framework.py generate [N]   # 生成N个场景(默认20)")
        print("  python eval_framework.py run             # 运行评测")
        print("  python eval_framework.py report          # 出报告")
        print("  python eval_framework.py expand [N]      # 扩展到N个场景")
