"""用龙猫对路线进行LLM打分评估。

用法: python test_llm_scoring.py [场景数]
"""
import asyncio, json, re, sys, time
from pathlib import Path
import httpx

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
BASE = "http://localhost:8002"
SCENARIOS_PATH = Path("eval_data/llm_scenarios.json")
PASS_THRESHOLD = 6.5

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

def parse_sse_route(sse_text):
    """从SSE文本中提取路线数据。"""
    route = []
    current_event = None
    for line in sse_text.split("\n"):
        line = line.strip()
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: ") and current_event == "step":
            try:
                d = json.loads(line[6:])
                route.append(d)
            except: pass
    return route

def format_route_for_eval(route):
    """格式化路线供LLM评估。"""
    lines = []
    for i, step in enumerate(route, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        tags = poi.get("_scene_tags", [])
        arrive = step.get("arrival_time", "?")
        lines.append(f"{i}. {name} [{cat}] ¥{price} 到达:{arrive} 标签:{tags}")
    return "\n".join(lines)

async def score_route(user_input, route_text):
    """用龙猫给路线打分。"""
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
- 5-6: POI质量一般，有些不太值得去
- 3-4: 多数POI质量偏低
- 0-2: POI基本不值得去

**geo_continuity** (地理合理性):
- 9-10: 路线流畅，无回头路
- 7-8: 基本合理，有轻微绕行
- 5-6: 有一定绕路但可接受
- 3-4: 明显不合理
- 0-2: 完全混乱

**scene_diversity** (场景多样性):
- 9-10: 类型丰富，体验多样
- 7-8: 有不错的多样性
- 5-6: 多样性一般
- 3-4: 较为单调
- 0-2: 完全单一

**overall** (总体): 综合以上维度，给出你的真实满意度评分。

重要规则:
1. 如果用户需求本身不可能实现（如50元住五星酒店、凌晨2点吃大餐），只要路线提供了合理的替代方案，intent_match给5-6分，overall给5-6分
2. 如果路线有3个以上POI且时间安排合理，geo_continuity至少给5分
3. 不要因为小问题给0分，0分只用于完全无意义的路线
4. 列出2-3个优点(good_points)和2-3个改进建议(bad_points)，不要只挑毛病
5. 对于"不可能需求"场景，如果路线能正确识别需求不合理并提供替代方案（如推荐免费景点代替五星酒店），应给予肯定

输出JSON: {{"scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["优点1","优点2"],"bad_points":["建议1","建议2"]}}"""

    result = await llm_json(prompt)
    if not result:
        return None

    # 兼容两种格式：scores嵌套 或 平铺
    if "scores" in result:
        scores = result["scores"]
    else:
        # 平铺格式：直接就是分数
        expected_keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
        if expected_keys & set(result.keys()):
            scores = {k: result[k] for k in expected_keys if k in result}
        else:
            return None

    # 验证分数合理性
    for k, v in scores.items():
        if not isinstance(v, (int, float)) or v < 0 or v > 10:
            return None
    vals = list(scores.values())
    if len(set(vals)) == 1 and len(vals) > 1:
        return None

    return {
        "scores": scores,
        "overall": scores.get("overall", 0),
        "good_points": result.get("good_points", []),
        "bad_points": result.get("bad_points", []),
        "verdict": result.get("verdict", "unknown"),
    }

async def plan_route(user_input, session_id, retries=2):
    """调用规划接口获取路线。"""
    for attempt in range(retries):
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post(f"{BASE}/api/plan",
                    json={"user_input": user_input, "session_id": session_id})
                elapsed = time.time() - start
                return r.text, elapsed
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(2)
    return "", 0

async def main():
    # 加载场景
    if not SCENARIOS_PATH.exists():
        print("场景文件不存在，先运行 gen_test_scenarios.py")
        return

    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    count = int(sys.argv[1]) if len(sys.argv) > 1 else len(scenarios)
    scenarios = scenarios[:count]
    print(f"🌿 LLM路线评分评估 — {len(scenarios)}个场景")
    print(f"   服务器: {BASE}")
    print(f"   及格线: {PASS_THRESHOLD}\n")

    results = []
    for i, sc in enumerate(scenarios):
        name = sc.get("name", f"s{i}")
        inp = sc.get("input", "")
        print(f"[{i+1}/{len(scenarios)}] {name}: {inp[:40]}...")

        try:
            # 规划
            sse_text, elapsed = await plan_route(inp, f"score_{i}")
            route = parse_sse_route(sse_text)
            if not route:
                print(f"  ❌ 空路线 ({elapsed:.1f}s)")
                results.append({"name": name, "input": inp, "status": "empty", "overall": 0})
                continue

            route_text = format_route_for_eval(route)
            cats = [s.get("poi",{}).get("category","?") for s in route]
            print(f"  路线: {' → '.join(cats)} ({elapsed:.1f}s)")

            # 评分
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
            if eval_result.get("bad_points"):
                for bp in eval_result["bad_points"][:2]:
                    print(f"     ⚠ {bp}")

            results.append({
                "name": name, "input": inp, "status": "scored",
                "overall": overall, "scores": scores, "passed": passed,
                "good_points": eval_result.get("good_points", []),
                "bad_points": eval_result.get("bad_points", []),
                "route_cats": cats, "elapsed": elapsed,
            })
        except Exception as e:
            print(f"  💥 异常: {e}")
            results.append({"name": name, "input": inp, "status": "error", "overall": 0, "error": str(e)})

    # 汇总
    scored = [r for r in results if r["status"] == "scored"]
    passed = [r for r in scored if r.get("passed")]
    print(f"\n{'='*60}")
    print(f"📊 结果: {len(passed)}/{len(scored)} 通过 (及格线={PASS_THRESHOLD})")
    if scored:
        avg = sum(r["overall"] for r in scored) / len(scored)
        print(f"   平均分: {avg:.1f}/10")
    print(f"{'='*60}")

    # 按维度统计
    if scored:
        dims = ["intent_match", "poi_quality", "geo_continuity", "scene_diversity"]
        for dim in dims:
            vals = [r["scores"].get(dim, 0) for r in scored if dim in r.get("scores", {})]
            if vals:
                print(f"   {dim}: avg={sum(vals)/len(vals):.1f}")

    # 常见问题
    all_bad = []
    for r in scored:
        all_bad.extend(r.get("bad_points", []))
    if all_bad:
        from collections import Counter
        print(f"\n常见问题:")
        for item, cnt in Counter(all_bad).most_common(5):
            print(f"  [{cnt}次] {item}")

    # 失败场景
    failed = [r for r in scored if not r.get("passed")]
    if failed:
        print(f"\n失败场景:")
        for r in failed:
            print(f"  ❌ {r['name']}: overall={r['overall']} — {r['bad_points'][0] if r.get('bad_points') else '?'}")

    # 保存
    Path("test_llm_scoring_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存到 test_llm_scoring_results.json")

if __name__ == "__main__":
    asyncio.run(main())
