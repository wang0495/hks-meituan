"""C版本快速5场景LLM评分（验证优化效果）。"""

import asyncio, json, sys, time
from pathlib import Path
import httpx

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
PASS_THRESHOLD = 6.5

SCENARIOS = [
    {"name": "情侣珠海一日游", "input": "情侣珠海一日游，预算500元，喜欢拍照打卡"},
    {"name": "亲子海洋王国", "input": "带6岁孩子去长隆海洋王国，预算1000元"},
    {"name": "美食探索", "input": "珠海美食一日游，想吃海鲜和本地特色"},
    {"name": "特种兵打卡", "input": "一天打卡珠海所有著名景点，时间紧"},
    {"name": "休闲养老游", "input": "珠海两日游，节奏慢，喜欢公园和海边"},
]


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


async def main():
    print(f"C版本（真Agent+提案组装） — {len(SCENARIOS)}场景\n")
    results = []
    for i, sc in enumerate(SCENARIOS):
        print(f"[{i+1}/{len(SCENARIOS)}] {sc['name']}")
        try:
            steps, elapsed, errors = await plan_c(sc["input"])
            if not steps:
                print(f"  ❌ 空路线 ({elapsed:.1f}s) errors={errors}")
                results.append({"name": sc["name"], "overall": 0, "status": "empty"})
                continue

            route_text = format_route(steps)
            poi_names = [s.get("poi", {}).get("name", "?") for s in steps]
            print(f"  路线({len(steps)}站): {' → '.join(poi_names[:6])}")

            ev = await score_route(sc["input"], route_text)
            if not ev:
                print(f"  ⚠ 评分失败")
                results.append({"name": sc["name"], "overall": 0, "status": "eval_fail"})
                continue

            s = ev["scores"]
            p = "✅" if ev["overall"] >= PASS_THRESHOLD else "❌"
            print(f"  {p} intent={s.get('intent_match','?')} q={s.get('poi_quality','?')} "
                  f"geo={s.get('geo_continuity','?')} div={s.get('scene_diversity','?')} "
                  f"overall={ev['overall']} ({elapsed:.1f}s)")
            if ev.get("bad_points"):
                for bp in ev["bad_points"][:2]:
                    print(f"     - {bp[:80]}")
            results.append({"name": sc["name"], "overall": ev["overall"], "scores": s, "status": "scored",
                           "poi_names": poi_names, "passed": ev["overall"] >= PASS_THRESHOLD,
                           "elapsed": elapsed, "steps": len(steps)})
        except Exception as e:
            import traceback
            print(f"  💥 {e}")
            traceback.print_exc()
            results.append({"name": sc["name"], "overall": 0, "status": "error"})

    scored = [r for r in results if r["status"] == "scored"]
    passed = [r for r in scored if r.get("passed")]
    if scored:
        avg = sum(r["overall"] for r in scored) / len(scored)
        print(f"\n通过: {len(passed)}/{len(scored)} | 平均: {avg:.1f}/10")

    # 保存结果
    with open("test_c_llm_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("结果已保存到 test_c_llm_results.json")

asyncio.run(main())
