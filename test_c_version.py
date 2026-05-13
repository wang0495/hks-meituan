"""C版本测试：5场景LLM评分。"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime

import httpx

sys.path.insert(0, "backend")

from backend.agents_v3 import get_graph_c, TravelState

# ── LLM评分配置 ──
API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
PASS_THRESHOLD = 6.5


TEST_SCENARIOS = [
    {"id": 1, "name": "情侣珠海一日游", "input": "情侣珠海一日游，预算500元，喜欢拍照打卡"},
    {"id": 2, "name": "亲子海洋王国", "input": "带6岁孩子去长隆海洋王国，预算1000元"},
    {"id": 3, "name": "美食探索", "input": "珠海美食一日游，想吃海鲜和本地特色"},
    {"id": 4, "name": "特种兵打卡", "input": "一天打卡珠海所有著名景点，时间紧"},
    {"id": 5, "name": "休闲养老游", "input": "珠海两日游，节奏慢，喜欢公园和海边"},
]


async def llm_score(user_input: str, route_text: str) -> dict | None:
    """用龙猫给路线打分（与test_llm_scoring.py相同逻辑）。"""
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
1. 如果用户需求本身不可能实现，只要路线提供了合理的替代方案，intent_match给5-6分，overall给5-6分
2. 如果路线有3个以上POI且时间安排合理，geo_continuity至少给5分
3. 不要因为小问题给0分，0分只用于完全无意义的路线
4. 列出2-3个优点(good_points)和2-3个改进建议(bad_points)，不要只挑毛病
5. 对于"不可能需求"场景，如果路线能正确识别需求不合理并提供替代方案，应给予肯定

输出JSON: {{"scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["优点1","优点2"],"bad_points":["建议1","建议2"]}}"""

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": MODEL,
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
                if r.status_code != 200:
                    continue
                text = r.json().get("content", [{}])[0].get("text", "").strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                data = json.loads(text.strip())

                # 兼容两种格式
                if "scores" in data:
                    scores = data["scores"]
                else:
                    keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
                    scores = {k: data[k] for k in keys if k in data}

                # 验证
                for v in scores.values():
                    if not isinstance(v, (int, float)) or v < 0 or v > 10:
                        return None
                vals = list(scores.values())
                if len(set(vals)) == 1 and len(vals) > 1:
                    return None

                return {
                    "scores": scores,
                    "overall": scores.get("overall", 0),
                    "good_points": data.get("good_points", []),
                    "bad_points": data.get("bad_points", []),
                }
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2)
    return None


def format_route(route_steps: list[dict]) -> str:
    """格式化路线供LLM评估。"""
    lines = []
    for i, step in enumerate(route_steps, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        tags = poi.get("_scene_tags", [])
        arrive = step.get("arrival_time", "?")
        lines.append(f"{i}. {name} [{cat}] ¥{price} 到达:{arrive} 标签:{tags}")
    return "\n".join(lines)


async def run_test(scenario: dict) -> dict:
    """运行单场景。"""
    graph = get_graph_c()

    initial: TravelState = {
        "user_input": scenario["input"],
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
    }

    try:
        t0 = time.time()
        result = await asyncio.wait_for(graph.ainvoke(initial), timeout=120)
        elapsed = time.time() - t0

        route = result.get("route", {})
        narrative = result.get("narrative", {})
        steps = route.get("route", []) if route else []
        proposals = result.get("proposals", [])
        conflicts = result.get("conflicts", [])

        # LLM评分
        route_text = format_route(steps) if steps else ""
        eval_result = None
        if route_text:
            eval_result = await llm_score(scenario["input"], route_text)

        return {
            "id": scenario["id"],
            "name": scenario["name"],
            "success": True,
            "elapsed": round(elapsed, 3),
            "route_steps": len(steps),
            "proposals": len(proposals),
            "conflicts": len(conflicts),
            "has_narrative": narrative is not None,
            "poi_names": [s.get("poi", {}).get("name", "?") for s in steps[:6]],
            "errors": result.get("errors", []),
            "eval": eval_result,
        }

    except asyncio.TimeoutError:
        return {"id": scenario["id"], "name": scenario["name"], "success": False, "error": "超时"}
    except Exception as e:
        return {"id": scenario["id"], "name": scenario["name"], "success": False, "error": str(e)}


async def main():
    print("=" * 60)
    print("C版本LLM评分测试：分布式智能体网络")
    print(f"评分模型: {MODEL} | 及格线: {PASS_THRESHOLD}")
    print("=" * 60)

    results = []
    for sc in TEST_SCENARIOS:
        r = await run_test(sc)
        results.append(r)

        if r["success"]:
            ev = r.get("eval")
            poi_str = " → ".join(r["poi_names"][:5])
            print(f"\n{'✅' if ev and ev['overall'] >= PASS_THRESHOLD else '❌'} 场景{r['id']}: {r['name']}")
            print(f"   路线: {poi_str}")
            print(f"   步骤:{r['route_steps']} 提案:{r['proposals']} 冲突:{r['conflicts']} ({r['elapsed']}s)")
            if ev:
                s = ev["scores"]
                print(f"   评分: intent={s.get('intent_match','?')} poi={s.get('poi_quality','?')} "
                      f"geo={s.get('geo_continuity','?')} diverse={s.get('scene_diversity','?')} "
                      f"overall={ev['overall']}")
                for bp in ev.get("bad_points", [])[:2]:
                    print(f"   ⚠ {bp}")
            else:
                print(f"   ⚠ LLM评分失败")
        else:
            print(f"\n❌ 场景{r['id']}: {r['name']} - {r.get('error', '?')}")

    # 汇总
    print("\n" + "=" * 60)
    successes = [r for r in results if r["success"]]
    scored = [r for r in successes if r.get("eval")]
    passed = [r for r in scored if r["eval"]["overall"] >= PASS_THRESHOLD]

    print(f"成功: {len(successes)}/{len(TEST_SCENARIOS)}")
    print(f"通过: {len(passed)}/{len(scored)} (及格线={PASS_THRESHOLD})")

    if scored:
        avgs = {}
        for dim in ["intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"]:
            vals = [r["eval"]["scores"].get(dim, 0) for r in scored if dim in r["eval"].get("scores", {})]
            if vals:
                avgs[dim] = sum(vals) / len(vals)
                print(f"  {dim}: {avgs[dim]:.1f}")

    # 差异化
    all_pois = [tuple(r["poi_names"]) for r in successes if r.get("poi_names")]
    unique_routes = len(set(all_pois))
    print(f"差异化: {unique_routes}/{len(successes)} 条不同路线")

    # 保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"docs/logs/test_c_version_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
