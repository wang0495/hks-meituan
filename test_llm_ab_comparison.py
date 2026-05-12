"""A/B对比测试：新旧架构LLM评分对比。

用同样的30个场景，分别调用旧管线和新管线，
用LLM对两组结果进行评分，量化对比效果。

用法: python test_llm_ab_comparison.py [场景数]
"""
import asyncio, json, sys, time
from pathlib import Path
import httpx

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
BASE = "http://localhost:8002"
SCENARIOS_PATH = Path("eval_data/llm_scenarios.json")
PASS_THRESHOLD = 6.5


async def llm_json(prompt, max_tokens=2000, retries=3):
    """调用LLM获取JSON响应。"""
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
            except:
                pass
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
    """用LLM给路线打分。"""
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

    if "scores" in result:
        scores = result["scores"]
    else:
        expected_keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
        if expected_keys & set(result.keys()):
            scores = {k: result[k] for k in expected_keys if k in result}
        else:
            return None

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
    }


async def plan_route_old(user_input, session_id, retries=2):
    """调用旧管线（关闭agent）。"""
    for attempt in range(retries):
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                # 旧管线：agent=false
                r = await c.post(f"{BASE}/api/plan",
                    json={"user_input": user_input, "session_id": session_id, "agent": False})
                elapsed = time.time() - start
                return r.text, elapsed
        except Exception as e:
            print(f"  [旧管线错误: {e}]")
            if attempt < retries - 1:
                await asyncio.sleep(2)
    return "", 0


async def plan_route_new(user_input, session_id, retries=2):
    """调用新管线（启用agent）。"""
    for attempt in range(retries):
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                # 新管线：agent=true
                r = await c.post(f"{BASE}/api/plan",
                    json={"user_input": user_input, "session_id": session_id, "agent": True})
                elapsed = time.time() - start
                return r.text, elapsed
        except Exception as e:
            print(f"  [新管线错误: {e}]")
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

    print("=" * 70)
    print("A/B对比测试：新旧架构LLM评分对比")
    print("=" * 70)
    print(f"场景数: {len(scenarios)}")
    print(f"服务器: {BASE}")
    print(f"及格线: {PASS_THRESHOLD}")
    print("=" * 70)

    results = []

    for i, sc in enumerate(scenarios):
        name = sc.get("name", f"s{i}")
        inp = sc.get("input", "")
        difficulty = sc.get("difficulty", "medium")
        edge_case = sc.get("edge_case", "")

        print(f"\n[{i+1}/{len(scenarios)}] {name} ({difficulty})")
        print(f"   输入: {inp[:50]}...")
        print(f"   边界: {edge_case}")

        # 1. 测试旧管线
        print("   [旧管线] 规划...", end=" ")
        old_sse, old_time = await plan_route_old(inp, f"old_{i}")
        old_route = parse_sse_route(old_sse)
        print(f"路线{len(old_route)}站 ({old_time:.1f}s)")

        # 2. 测试新管线
        print("   [新管线] 规划...", end=" ")
        new_sse, new_time = await plan_route_new(inp, f"new_{i}")
        new_route = parse_sse_route(new_sse)
        print(f"路线{len(new_route)}站 ({new_time:.1f}s)")

        # 3. 评分旧管线
        old_score = None
        if old_route:
            old_text = format_route_for_eval(old_route)
            old_score = await score_route(inp, old_text)

        # 4. 评分新管线
        new_score = None
        if new_route:
            new_text = format_route_for_eval(new_route)
            new_score = await score_route(inp, new_text)

        # 格式化路线详情
        def fmt_route(route):
            return [{
                "name": s.get("poi", {}).get("name", "?"),
                "category": s.get("poi", {}).get("category", "?"),
                "price": s.get("poi", {}).get("avg_price", 0),
                "arrival": s.get("arrival_time", "?"),
                "departure": s.get("departure_time", "?"),
            } for s in route]

        # 记录结果
        result = {
            "name": name,
            "input": inp,
            "difficulty": difficulty,
            "edge_case": edge_case,
            "old": {
                "route_length": len(old_route),
                "elapsed": old_time,
                "route_detail": fmt_route(old_route),
                "score": old_score,
            },
            "new": {
                "route_length": len(new_route),
                "elapsed": new_time,
                "route_detail": fmt_route(new_route),
                "score": new_score,
            },
        }
        results.append(result)

        # 显示对比
        if old_score and new_score:
            old_overall = old_score["overall"]
            new_overall = new_score["overall"]
            diff = new_overall - old_overall
            winner = "新" if diff > 0 else "旧" if diff < 0 else "平"
            symbol = "↑" if diff > 0 else "↓" if diff < 0 else "→"

            print(f"\n   对比结果:")
            print(f"     旧管线: overall={old_overall:.1f} intent={old_score['scores'].get('intent_match','?'):.1f}")
            print(f"     新管线: overall={new_overall:.1f} intent={new_score['scores'].get('intent_match','?'):.1f}")
            print(f"     差异: {symbol} {abs(diff):.1f}分 [{winner}架构胜]")

            # 显示改进点
            if diff > 0.5:
                print(f"     ✅ 新架构有明显提升")
            elif diff < -0.5:
                print(f"     ⚠️  新架构表现下降")
            else:
                print(f"     →  两者相当")
        elif new_score:
            print(f"\n   旧管线无结果，新管线 overall={new_score['overall']:.1f}")
        elif old_score:
            print(f"\n   新管线无结果，旧管线 overall={old_score['overall']:.1f}")
        else:
            print(f"\n   两者都无结果")

    # ========== 汇总统计 ==========
    print("\n" + "=" * 70)
    print("📊 A/B对比结果汇总")
    print("=" * 70)

    # 过滤出有评分的
    valid_results = [r for r in results if r["old"]["score"] and r["new"]["score"]]

    if not valid_results:
        print("没有有效评分数据")
        return

    # 1. 总体平均分对比
    old_avg = sum(r["old"]["score"]["overall"] for r in valid_results) / len(valid_results)
    new_avg = sum(r["new"]["score"]["overall"] for r in valid_results) / len(valid_results)

    print(f"\n1. 总体平均分对比")
    print(f"   旧管线: {old_avg:.2f}/10")
    print(f"   新管线: {new_avg:.2f}/10")
    print(f"   提升: {new_avg - old_avg:+.2f} ({(new_avg - old_avg) / old_avg * 100:+.1f}%)")

    # 2. 通过率对比
    old_pass = sum(1 for r in valid_results if r["old"]["score"]["overall"] >= PASS_THRESHOLD)
    new_pass = sum(1 for r in valid_results if r["new"]["score"]["overall"] >= PASS_THRESHOLD)

    print(f"\n2. 通过率对比 (及格线={PASS_THRESHOLD})")
    print(f"   旧管线: {old_pass}/{len(valid_results)} ({old_pass / len(valid_results) * 100:.0f}%)")
    print(f"   新管线: {new_pass}/{len(valid_results)} ({new_pass / len(valid_results) * 100:.0f}%)")
    print(f"   提升: +{new_pass - old_pass}个场景通过")

    # 3. 各维度对比
    print(f"\n3. 各维度平均分对比")
    dims = ["intent_match", "poi_quality", "geo_continuity", "scene_diversity"]
    dim_names = {"intent_match": "意图匹配", "poi_quality": "POI质量",
                 "geo_continuity": "地理合理性", "scene_diversity": "场景多样性"}

    for dim in dims:
        old_val = sum(r["old"]["score"]["scores"].get(dim, 0) for r in valid_results) / len(valid_results)
        new_val = sum(r["new"]["score"]["scores"].get(dim, 0) for r in valid_results) / len(valid_results)
        symbol = "↑" if new_val > old_val else "↓" if new_val < old_val else "→"
        print(f"   {dim_names[dim]}: 旧={old_val:.2f} 新={new_val:.2f} {symbol}")

    # 4. 胜负统计
    wins_new = sum(1 for r in valid_results if r["new"]["score"]["overall"] > r["old"]["score"]["overall"] + 0.1)
    wins_old = sum(1 for r in valid_results if r["old"]["score"]["overall"] > r["new"]["score"]["overall"] + 0.1)
    ties = len(valid_results) - wins_new - wins_old

    print(f"\n4. 胜负统计")
    print(f"   新架构胜: {wins_new}/{len(valid_results)} ({wins_new / len(valid_results) * 100:.0f}%)")
    print(f"   旧架构胜: {wins_old}/{len(valid_results)} ({wins_old / len(valid_results) * 100:.0f}%)")
    print(f"   平局: {ties}/{len(valid_results)} ({ties / len(valid_results) * 100:.0f}%)")

    # 5. 按难度统计
    print(f"\n5. 按难度统计")
    for diff in ["easy", "medium", "hard", "extreme"]:
        diff_results = [r for r in valid_results if r["difficulty"] == diff]
        if diff_results:
            old_avg_diff = sum(r["old"]["score"]["overall"] for r in diff_results) / len(diff_results)
            new_avg_diff = sum(r["new"]["score"]["overall"] for r in diff_results) / len(diff_results)
            print(f"   {diff}: 旧={old_avg_diff:.2f} 新={new_avg_diff:.2f} ({new_avg_diff - old_avg_diff:+.2f})")

    # 6. 性能对比
    old_time_avg = sum(r["old"]["elapsed"] for r in valid_results) / len(valid_results)
    new_time_avg = sum(r["new"]["elapsed"] for r in valid_results) / len(valid_results)

    print(f"\n6. 性能对比")
    print(f"   旧管线平均耗时: {old_time_avg:.1f}s")
    print(f"   新管线平均耗时: {new_time_avg:.1f}s")
    if new_time_avg > old_time_avg:
        print(f"   新架构慢 {new_time_avg - old_time_avg:.1f}s ({(new_time_avg / old_time_avg - 1) * 100:.0f}%)")
    else:
        print(f"   新架构快 {old_time_avg - new_time_avg:.1f}s ({(1 - new_time_avg / old_time_avg) * 100:.0f}%)")

    # 7. 亮点场景（新架构提升最大的）
    print(f"\n7. 新架构表现最优的场景")
    improvements = [(r["new"]["score"]["overall"] - r["old"]["score"]["overall"], r) for r in valid_results]
    improvements.sort(reverse=True, key=lambda x: x[0])
    for diff, r in improvements[:3]:
        if diff > 0:
            print(f"   +{diff:.1f}分 | {r['name']} ({r['difficulty']}): {r['edge_case'][:30]}")

    # 8. 问题场景（新架构表现下降）
    print(f"\n8. 新架构表现下降的场景")
    regressions = [(r["old"]["score"]["overall"] - r["new"]["score"]["overall"], r) for r in valid_results]
    regressions.sort(reverse=True, key=lambda x: x[0])
    for diff, r in regressions[:3]:
        if diff > 0:
            print(f"   -{diff:.1f}分 | {r['name']} ({r['difficulty']}): {r['edge_case'][:30]}")

    # 9. 最终结论
    print(f"\n" + "=" * 70)
    print("📈 结论")
    print("=" * 70)

    if new_avg > old_avg + 0.5:
        verdict = "新架构明显优于旧架构"
    elif new_avg > old_avg + 0.1:
        verdict = "新架构略有优势"
    elif new_avg < old_avg - 0.5:
        verdict = "新架构表现不如旧架构，需优化"
    elif new_avg < old_avg - 0.1:
        verdict = "新架构略逊于旧架构"
    else:
        verdict = "新旧架构表现相当"

    print(f"   结论: {verdict}")
    print(f"   平均分: {old_avg:.2f} → {new_avg:.2f} ({new_avg - old_avg:+.2f})")
    print(f"   通过率: {old_pass}/{len(valid_results)} → {new_pass}/{len(valid_results)}")

    # 保存详细结果
    output_path = Path("test_llm_ab_comparison_results.json")
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果已保存到: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
