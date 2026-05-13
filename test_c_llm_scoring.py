"""C版本 LLM评分测试。

架构：rule_guard → [7Agent并行] → emergence_check → coordinator → live_itinerary
"""

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

**intent_match** (意图匹配):
- 9-10: 完美匹配用户核心需求
- 7-8: 大部分匹配，有小偏差
- 5-6: 部分匹配，遗漏了重要需求
- 3-4: 匹配度低，但有相关性
- 0-2: 完全不相关

**poi_quality** (POI质量):
- 9-10: 所有POI都是值得专程去的优质景点
- 7-8: 大部分POI质量不错
- 5-6: POI质量一般
- 3-4: 多数POI质量偏低
- 0-2: POI基本不值得去

**geo_continuity** (地理合理性):
- 9-10: 路线流畅，无回头路
- 7-8: 基本合理
- 5-6: 有一定绕路但可接受
- 3-4: 明显不合理
- 0-2: 完全混乱

**scene_diversity** (场景多样性):
- 9-10: 类型丰富，体验多样
- 7-8: 有不错的多样性
- 5-6: 多样性一般
- 3-4: 较为单调
- 0-2: 完全单一

**overall** (总体): 综合以上维度。

重要规则:
1. 如果用户需求本身不可能实现，只要路线提供了合理替代方案，intent_match给5-6分
2. 如果路线有3个以上POI且时间安排合理，geo_continuity至少给5分
3. 不要因为小问题给0分
4. 列出2-3个优点和2-3个改进建议

输出JSON: {{"scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["优点1","优点2"],"bad_points":["建议1","建议2"]}}"""

    result = await llm_json(prompt)
    if not result:
        return None

    if "scores" in result:
        scores = result["scores"]
    else:
        expected_keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
        if expected_keys & set(result.keys()):
            scores = {k: result[k] for k in expected_keys if k in result.keys()}
        else:
            return None

    for k, v in scores.items():
        if not isinstance(v, (int, float)) or v < 0 or v > 10:
            return None

    return {
        "scores": scores,
        "overall": scores.get("overall", 0),
        "good_points": result.get("good_points", []),
        "bad_points": result.get("bad_points", []),
    }


async def plan_c(user_input):
    import sys
    sys.path.insert(0, "backend")
    from backend.agents_v3 import get_graph_c, TravelState

    graph = get_graph_c()

    initial = {
        "user_input": user_input,
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
    }

    start = time.time()
    result = await asyncio.wait_for(graph.ainvoke(initial), timeout=60)
    elapsed = time.time() - start

    route = result.get("route", {})
    steps = route.get("route", []) if route else []
    heatmap = result.get("heatmap", {})
    return steps, elapsed, result.get("errors", []), heatmap


async def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else len(SCENARIOS)
    scenarios = SCENARIOS[:count]

    print(f"C版本 LLM评分 — {len(scenarios)}个场景 (严格架构)")
    print(f"评分: {MODEL} | 及格线: {PASS_THRESHOLD}\n")

    results = []
    for i, sc in enumerate(scenarios):
        name = sc["name"]
        inp = sc["input"]
        print(f"[{i+1}/{len(scenarios)}] {name}")

        try:
            steps, elapsed, errors, heatmap = await plan_c(inp)
            if not steps:
                print(f"  ❌ 空路线 ({elapsed:.1f}s)")
                results.append({"name": name, "input": inp, "status": "empty", "overall": 0})
                continue

            route_text = format_route(steps)
            cats = [s.get("poi", {}).get("category", "?") for s in steps]
            poi_names = [s.get("poi", {}).get("name", "?") for s in steps]

            # 热力图摘要
            hm_green = sum(1 for h in heatmap.values() if h.get("color") == "green")
            hm_total = len(heatmap)

            print(f"  路线({len(steps)}步): {' → '.join(poi_names[:5])}")
            print(f"  热力图: {hm_green}/{hm_total}绿 | 错误: {errors[:2]}")

            eval_result = await score_route(inp, route_text)
            if not eval_result:
                print(f"  ⚠ 评分失败")
                results.append({"name": name, "input": inp, "status": "eval_fail", "overall": 0})
                continue

            overall = eval_result["overall"]
            passed = overall >= PASS_THRESHOLD
            scores = eval_result["scores"]
            status = "✅" if passed else "❌"

            print(f"  {status} intent={scores.get('intent_match','?')} quality={scores.get('poi_quality','?')} "
                  f"geo={scores.get('geo_continuity','?')} diverse={scores.get('scene_diversity','?')} "
                  f"overall={overall}")

            results.append({
                "name": name, "input": inp, "status": "scored",
                "overall": overall, "scores": scores, "passed": passed,
                "good_points": eval_result.get("good_points", []),
                "bad_points": eval_result.get("bad_points", []),
                "route_steps": len(steps), "poi_names": poi_names,
                "elapsed": elapsed, "heatmap_green": hm_green, "heatmap_total": hm_total,
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  💥 {e}")
            results.append({"name": name, "input": inp, "status": "error", "overall": 0, "error": str(e)})

    # 汇总
    scored = [r for r in results if r["status"] == "scored"]
    passed = [r for r in scored if r.get("passed")]
    print(f"\n{'='*60}")
    print(f"结果: {len(passed)}/{len(scored)} 通过")
    if scored:
        avg = sum(r["overall"] for r in scored) / len(scored)
        print(f"平均分: {avg:.1f}/10")
    print(f"{'='*60}")

    if scored:
        for dim in ["intent_match", "poi_quality", "geo_continuity", "scene_diversity"]:
            vals = [r["scores"].get(dim, 0) for r in scored if dim in r.get("scores", {})]
            if vals:
                print(f"   {dim}: {sum(vals)/len(vals):.1f}")

    all_bad = []
    for r in scored:
        all_bad.extend(r.get("bad_points", []))
    if all_bad:
        from collections import Counter
        print(f"\n常见问题:")
        for item, cnt in Counter(all_bad).most_common(5):
            print(f"  [{cnt}次] {item[:60]}")

    Path("test_c_llm_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
