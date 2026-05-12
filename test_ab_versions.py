"""A版本 vs B版本 对比测试。

A版本: 3层联邦架构（意图探测+矛盾调解 → 竞标市场 → 对抗校验 → 微协商）
B版本: LangGraph+Validator架构（原实现）

用法: python test_ab_versions.py [场景数]
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

**federation_quality** (联邦架构质量):
- 9-10: 矛盾调解精准、竞标方案优质、校验全面、协商连贯
- 7-8: 联邦各层工作良好
- 5-6: 部分层次表现一般
- 3-4: 联邦机制有明显缺陷
- 0-2: 联邦架构未发挥作用

**overall** (总体): 综合以上维度，给出你的真实满意度评分。

重要规则:
1. 如果用户需求本身不可能实现，只要路线提供了合理的替代方案，intent_match给5-6分，overall给5-6分
2. 如果路线有3个以上POI且时间安排合理，geo_continuity至少给5分
3. 不要因为小问题给0分，0分只用于完全无意义的路线
4. 列出2-3个优点(good_points)和2-3个改进建议(bad_points)，不要只挑毛病
5. 对于复杂需求(如"既要历史感又要孩子不无聊")，如果路线能妥善处理矛盾，federation_quality应给高分

输出JSON: {{"scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"federation_quality":N,"overall":N}},"good_points":["优点1","优点2"],"bad_points":["建议1","建议2"]}}"""

    result = await llm_json(prompt)
    if not result:
        return None

    if "scores" in result:
        scores = result["scores"]
    else:
        expected_keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "federation_quality", "overall"}
        if expected_keys & set(result.keys()):
            scores = {k: result[k] for k in expected_keys if k in result}
        else:
            return None

    for k, v in scores.items():
        if not isinstance(v, (int, float)) or v < 0 or v > 10:
            return None

    return {
        "scores": scores,
        "overall": scores.get("overall", 0),
        "federation_quality": scores.get("federation_quality", 0),
        "good_points": result.get("good_points", []),
        "bad_points": result.get("bad_points", []),
    }


async def plan_route_version(user_input, session_id, version="a", retries=2):
    """调用指定版本的路由。

    version="a": A版本（3层联邦架构）
    version="b": B版本（LangGraph+Validator）
    """
    for attempt in range(retries):
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                # 使用version参数区分A/B版本
                endpoint = f"{BASE}/api/plan"
                payload = {
                    "user_input": user_input,
                    "session_id": session_id,
                    "version": version  # "a" or "b"
                }
                r = await c.post(endpoint, json=payload)
                elapsed = time.time() - start
                return r.text, elapsed
        except Exception as e:
            print(f"  [{version}版本错误: {e}]")
            if attempt < retries - 1:
                await asyncio.sleep(2)
    return "", 0


async def main():
    # 加载场景
    if not SCENARIOS_PATH.exists():
        print("场景文件不存在")
        return

    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    count = int(sys.argv[1]) if len(sys.argv) > 1 else len(scenarios)
    scenarios = scenarios[:count]

    print("=" * 80)
    print("A版本 vs B版本 对比测试")
    print("=" * 80)
    print(f"A版本: 3层联邦架构（意图探测+竞标市场+对抗校验+微协商）")
    print(f"B版本: LangGraph+Validator架构")
    print(f"场景数: {len(scenarios)}")
    print("=" * 80)

    results = []

    for i, sc in enumerate(scenarios):
        name = sc.get("name", f"s{i}")
        inp = sc.get("input", "")
        difficulty = sc.get("difficulty", "medium")
        edge_case = sc.get("edge_case", "")

        print(f"\n[{i+1}/{len(scenarios)}] {name} ({difficulty})")
        print(f"   题目: {inp[:50]}...")
        print(f"   边界: {edge_case}")

        # 1. 测试A版本
        print("   [A版本] 联邦架构...", end=" ")
        a_sse, a_time = await plan_route_version(inp, f"a_{i}", version="a")
        a_route = parse_sse_route(a_sse)
        print(f"路线{len(a_route)}站 ({a_time:.1f}s)")

        # 2. 测试B版本
        print("   [B版本] Validator架构...", end=" ")
        b_sse, b_time = await plan_route_version(inp, f"b_{i}", version="b")
        b_route = parse_sse_route(b_sse)
        print(f"路线{len(b_route)}站 ({b_time:.1f}s)")

        # 3. 评分
        a_score = None
        if a_route:
            a_text = format_route_for_eval(a_route)
            a_score = await score_route(inp, a_text)

        b_score = None
        if b_route:
            b_text = format_route_for_eval(b_route)
            b_score = await score_route(inp, b_text)

        # 记录
        result = {
            "name": name,
            "input": inp,
            "difficulty": difficulty,
            "edge_case": edge_case,
            "a_version": {
                "route_length": len(a_route),
                "elapsed": a_time,
                "score": a_score,
            },
            "b_version": {
                "route_length": len(b_route),
                "elapsed": b_time,
                "score": b_score,
            },
        }
        results.append(result)

        # 显示对比
        if a_score and b_score:
            a_overall = a_score["overall"]
            b_overall = b_score["overall"]
            diff = a_overall - b_overall
            winner = "A" if diff > 0 else "B" if diff < 0 else "平"
            symbol = "↑" if diff > 0 else "↓" if diff < 0 else "→"

            print(f"\n   对比结果:")
            print(f"     A版本(联邦): overall={a_overall:.1f} federation={a_score.get('federation_quality','?'):.1f}")
            print(f"     B版本(验证器): overall={b_overall:.1f}")
            print(f"     差异: {symbol} {abs(diff):.1f}分 [{winner}版本胜]")
        elif a_score:
            print(f"\n   B版本无结果，A版本 overall={a_score['overall']:.1f}")
        elif b_score:
            print(f"\n   A版本无结果，B版本 overall={b_score['overall']:.1f}")
        else:
            print(f"\n   两者都无结果")

    # 汇总
    print("\n" + "=" * 80)
    print("📊 A版本 vs B版本 对比结果汇总")
    print("=" * 80)

    valid_results = [r for r in results if r["a_version"]["score"] and r["b_version"]["score"]]

    if not valid_results:
        print("没有有效评分数据")
        return

    # 1. 总体平均分
    a_avg = sum(r["a_version"]["score"]["overall"] for r in valid_results) / len(valid_results)
    b_avg = sum(r["b_version"]["score"]["overall"] for r in valid_results) / len(valid_results)

    print(f"\n1. 总体平均分对比")
    print(f"   A版本(联邦架构): {a_avg:.2f}/10")
    print(f"   B版本(验证器):   {b_avg:.2f}/10")
    print(f"   差异: {a_avg - b_avg:+.2f} ({(a_avg - b_avg) / max(b_avg, 0.1) * 100:+.1f}%)")

    # 2. 通过率
    a_pass = sum(1 for r in valid_results if r["a_version"]["score"]["overall"] >= PASS_THRESHOLD)
    b_pass = sum(1 for r in valid_results if r["b_version"]["score"]["overall"] >= PASS_THRESHOLD)

    print(f"\n2. 通过率对比 (及格线={PASS_THRESHOLD})")
    print(f"   A版本: {a_pass}/{len(valid_results)} ({a_pass / len(valid_results) * 100:.0f}%)")
    print(f"   B版本: {b_pass}/{len(valid_results)} ({b_pass / len(valid_results) * 100:.0f}%)")

    # 3. Federation Quality（A版本特有维度）
    a_fed_avg = sum(r["a_version"]["score"].get("federation_quality", 0) for r in valid_results) / len(valid_results)
    print(f"\n3. A版本联邦架构质量评分: {a_fed_avg:.2f}/10")

    # 4. 胜负统计
    wins_a = sum(1 for r in valid_results if r["a_version"]["score"]["overall"] > r["b_version"]["score"]["overall"] + 0.1)
    wins_b = sum(1 for r in valid_results if r["b_version"]["score"]["overall"] > r["a_version"]["score"]["overall"] + 0.1)
    ties = len(valid_results) - wins_a - wins_b

    print(f"\n4. 胜负统计")
    print(f"   A版本胜: {wins_a}/{len(valid_results)} ({wins_a / len(valid_results) * 100:.0f}%)")
    print(f"   B版本胜: {wins_b}/{len(valid_results)} ({wins_b / len(valid_results) * 100:.0f}%)")
    print(f"   平局: {ties}/{len(valid_results)} ({ties / len(valid_results) * 100:.0f}%)")

    # 5. 结论
    print(f"\n" + "=" * 80)
    print("📈 结论")
    print("=" * 80)

    if a_avg > b_avg + 0.5:
        verdict = "A版本(联邦架构)明显优于B版本"
    elif a_avg > b_avg + 0.1:
        verdict = "A版本略有优势"
    elif a_avg < b_avg - 0.5:
        verdict = "B版本明显优于A版本"
    elif a_avg < b_avg - 0.1:
        verdict = "B版本略有优势"
    else:
        verdict = "两者表现相当"

    print(f"   结论: {verdict}")
    print(f"   A版本: {a_avg:.2f}分, 通过率{a_pass}/{len(valid_results)}")
    print(f"   B版本: {b_avg:.2f}分, 通过率{b_pass}/{len(valid_results)}")

    # 保存
    Path("test_ab_versions_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果已保存到: test_ab_versions_results.json")


if __name__ == "__main__":
    asyncio.run(main())
