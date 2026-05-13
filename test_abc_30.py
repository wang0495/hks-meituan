"""A/B/C三版本30场景LLM对比测试。

A版本: 3层联邦架构（HTTP API）
B版本: LangGraph+Validator架构（HTTP API）
C版本: 分布式智能体网络（本地调用）

用法:
  python test_abc_30.py              # 只测C版本
  python test_abc_30.py --all        # 测试全部（需要服务器运行）
  python test_abc_30.py 10           # 只测前10个场景
"""
import asyncio, json, sys, time, os
from pathlib import Path
import httpx

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
SERVER_BASE = "http://localhost:8002"
PASS_THRESHOLD = 6.5
SCENARIOS_PATH = Path("eval_data/llm_scenarios.json")


async def llm_json(prompt, max_tokens=2000, retries=3):
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(API_URL,
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={"model": MODEL, "max_tokens": max_tokens,
                          "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0.1, "response_format": {"type": "json_object"}})
                if r.status_code != 200:
                    continue
                text = r.json().get("content", [{}])[0].get("text", "")
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                try:
                    return json.loads(text.strip())
                except:
                    continue
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(2)
    return None


def format_route(route_steps):
    lines = []
    for i, step in enumerate(route_steps, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        arrive = step.get("arrival_time", "?")
        lines.append(f"{i}. {name} [{cat}] ¥{price} 到达:{arrive}")
    return "\n".join(lines)


def parse_sse_route(sse_text):
    route = []
    current_event = None
    for line in sse_text.split("\n"):
        line = line.strip()
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: ") and current_event == "step":
            try:
                route.append(json.loads(line[6:]))
            except:
                pass
    return route


async def score_route(user_input, route_text):
    prompt = f"""你是旅游路线质量评审。请客观公正地评估以下路线。

用户需求: {user_input}

路线:
{route_text}

评分标准(每项0-10分):

**intent_match**: 意图匹配度
**poi_quality**: POI质量
**geo_continuity**: 地理合理性
**scene_diversity**: 场景多样性
**overall**: 总体评分

规则:
1. 不可能需求有合理替代方案给5-6分
2. 3个以上POI时间合理geo至少5分
3. 列出优缺点

输出JSON: {{"scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["优点"],"bad_points":["建议"]}}"""

    result = await llm_json(prompt)
    if not result:
        return None
    if "scores" in result:
        scores = result["scores"]
    else:
        keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
        if keys & set(result.keys()):
            scores = {k: result[k] for k in keys if k in result.keys()}
        else:
            return None
    for k, v in scores.items():
        if not isinstance(v, (int, float)) or v < 0 or v > 10:
            return None
    return {"scores": scores, "overall": scores.get("overall", 0),
            "good_points": result.get("good_points", []), "bad_points": result.get("bad_points", [])}


# ── C版本：本地调用 ──

async def plan_c(user_input):
    sys.path.insert(0, str(Path(__file__).parent / "backend"))
    from backend.agents_v3 import get_graph_c
    graph = get_graph_c()
    initial = {"user_input": user_input, "proposals": [], "counter_proposals": [],
               "negotiation_msgs": [], "errors": [], "events": []}
    start = time.time()
    result = await asyncio.wait_for(graph.ainvoke(initial), timeout=120)
    elapsed = time.time() - start
    route = result.get("route", {})
    steps = route.get("route", []) if route else []
    return steps, elapsed, result.get("errors", [])


# ── A/B版本：HTTP API ──

async def plan_ab(user_input, session_id, version="a"):
    try:
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(f"{SERVER_BASE}/api/plan",
                json={"user_input": user_input, "session_id": session_id, "version": version})
            return r.text
    except Exception:
        return ""


async def main():
    test_all = "--all" in sys.argv
    count_arg = None
    for a in sys.argv[1:]:
        if a.isdigit():
            count_arg = int(a)

    # 加载场景
    if not SCENARIOS_PATH.exists():
        print("场景文件不存在: eval_data/llm_scenarios.json")
        return
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    if count_arg:
        scenarios = scenarios[:count_arg]

    print(f"A/B/C三版本对比 — {len(scenarios)}场景")
    print(f"A: 3层联邦 | B: Validator | C: 分布式Agent")
    if not test_all:
        print("（仅测试C版本，加 --all 测全部）")
    print()

    # 检查服务器
    server_ok = False
    if test_all:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{SERVER_BASE}/docs")
                server_ok = r.status_code == 200
                if server_ok:
                    print("服务器连接成功\n")
                else:
                    print("服务器返回异常，仅测试C版本\n")
                    test_all = False
        except Exception:
            print("服务器未运行，仅测试C版本\n")
            test_all = False

    results = []

    for i, sc in enumerate(scenarios):
        name = sc.get("name", f"s{i}")
        inp = sc.get("input", "")
        difficulty = sc.get("difficulty", "?")
        print(f"[{i+1}/{len(scenarios)}] {name} ({difficulty})")

        row = {"name": name, "input": inp, "difficulty": difficulty,
               "a": None, "b": None, "c": None}

        # ── C版本 ──
        try:
            steps, elapsed, errors = await plan_c(inp)
            if steps:
                route_text = format_route(steps)
                poi_names = [s.get("poi", {}).get("name", "?") for s in steps]
                print(f"  C: {len(steps)}站 {' → '.join(poi_names[:4])}... ({elapsed:.0f}s)")
                ev = await score_route(inp, route_text)
                if ev:
                    s = ev["scores"]
                    p = "✅" if ev["overall"] >= PASS_THRESHOLD else "❌"
                    print(f"     {p} intent={s.get('intent_match','?')} q={s.get('poi_quality','?')} "
                          f"geo={s.get('geo_continuity','?')} div={s.get('scene_diversity','?')} "
                          f"overall={ev['overall']}")
                    row["c"] = {"overall": ev["overall"], "scores": s, "steps": len(steps),
                                "elapsed": elapsed, "poi_names": poi_names,
                                "good_points": ev.get("good_points", []),
                                "bad_points": ev.get("bad_points", [])}
                else:
                    print(f"     ⚠ 评分失败")
                    row["c"] = {"overall": 0, "steps": len(steps), "error": "eval_fail"}
            else:
                print(f"  C: 空路线 ({elapsed:.0f}s)")
                row["c"] = {"overall": 0, "error": "empty_route"}
        except Exception as e:
            print(f"  C: 💥 {e}")
            row["c"] = {"overall": 0, "error": str(e)}

        # ── A版本 ──
        if test_all:
            try:
                a_sse = await plan_ab(inp, f"a_{i}", "a")
                a_route = parse_sse_route(a_sse)
                if a_route:
                    a_text = format_route(a_route)
                    a_ev = await score_route(inp, a_text)
                    if a_ev:
                        print(f"  A: overall={a_ev['overall']} ({len(a_route)}站)")
                        row["a"] = {"overall": a_ev["overall"], "scores": a_ev["scores"],
                                    "steps": len(a_route)}
                    else:
                        row["a"] = {"overall": 0, "error": "eval_fail"}
                else:
                    row["a"] = {"overall": 0, "error": "empty_route"}
            except Exception as e:
                row["a"] = {"overall": 0, "error": str(e)}

        # ── B版本 ──
        if test_all:
            try:
                b_sse = await plan_ab(inp, f"b_{i}", "b")
                b_route = parse_sse_route(b_sse)
                if b_route:
                    b_text = format_route(b_route)
                    b_ev = await score_route(inp, b_text)
                    if b_ev:
                        print(f"  B: overall={b_ev['overall']} ({len(b_route)}站)")
                        row["b"] = {"overall": b_ev["overall"], "scores": b_ev["scores"],
                                    "steps": len(b_route)}
                    else:
                        row["b"] = {"overall": 0, "error": "eval_fail"}
                else:
                    row["b"] = {"overall": 0, "error": "empty_route"}
            except Exception as e:
                row["b"] = {"overall": 0, "error": str(e)}

        results.append(row)

    # ── 汇总 ──
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)

    def summarize(version_key):
        valid = [r for r in results if r.get(version_key) and r[version_key].get("overall", 0) > 0]
        if not valid:
            return None
        avg = sum(r[version_key]["overall"] for r in valid) / len(valid)
        passed = sum(1 for r in valid if r[version_key]["overall"] >= PASS_THRESHOLD)
        # 维度平均
        dims = {"intent_match": [], "poi_quality": [], "geo_continuity": [], "scene_diversity": []}
        for r in valid:
            scores = r[version_key].get("scores", {})
            for d in dims:
                if d in scores:
                    dims[d].append(scores[d])
        dim_avg = {d: sum(v)/len(v) for d, v in dims.items() if v}
        return {"avg": avg, "passed": passed, "total": len(valid), "dims": dim_avg}

    c_stats = summarize("c")
    if c_stats:
        print(f"\nC版本（分布式Agent）:")
        print(f"  平均: {c_stats['avg']:.1f}/10 | 通过: {c_stats['passed']}/{c_stats['total']}")
        for d, v in c_stats["dims"].items():
            print(f"  {d}: {v:.1f}")

    if test_all:
        a_stats = summarize("a")
        b_stats = summarize("b")
        if a_stats:
            print(f"\nA版本（联邦架构）:")
            print(f"  平均: {a_stats['avg']:.1f}/10 | 通过: {a_stats['passed']}/{a_stats['total']}")
        if b_stats:
            print(f"\nB版本（Validator）:")
            print(f"  平均: {b_stats['avg']:.1f}/10 | 通过: {b_stats['passed']}/{b_stats['total']}")

        if a_stats and b_stats and c_stats:
            print(f"\n对比:")
            print(f"  A vs C: {a_stats['avg']:.1f} vs {c_stats['avg']:.1f} ({a_stats['avg']-c_stats['avg']:+.1f})")
            print(f"  B vs C: {b_stats['avg']:.1f} vs {c_stats['avg']:.1f} ({b_stats['avg']-c_stats['avg']:+.1f})")

    # 保存
    out_path = "test_abc_30_results.json"
    Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
