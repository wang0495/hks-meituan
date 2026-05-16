"""架构对比测试：在5个标准场景上对比所有synthesizer架构。

用法:
    # 对比所有架构
    python tests/test_arch_comparison.py

    # 只测试特定架构
    SYNTHESIZER_MODE=best_of_n python tests/test_c_version.py

架构模式:
    - default: 基线（单次LLM组装）
    - best_of_n: A1 多候选投票（并行3次，启发式选最优）
    - geo_cluster: A2 地理预聚类+TSP排序
    - self_refine: A3 维度导向自精炼
    - tournament: A4 并行策略锦标赛
    - constraint: A5 迭代约束满足

输出: docs/logs/arch_comparison_{timestamp}.json
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# 确保项目根目录在sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── 配置 ──
API_KEY = os.getenv("EVAL_API_KEY", os.getenv("LLM_API_KEY", ""))
API_URL = "https://api.deepseek.com/chat/completions"
EVAL_MODEL = "deepseek-chat"
PASS_THRESHOLD = 6.5
N_EVAL_RUNS = 3  # 每条路线跑3次eval取平均（减少方差）

ARCHITECTURES = [
    ("default", "基线（单次LLM组装）"),
    ("best_of_n", "A1: 多候选投票"),
    ("geo_cluster", "A2: 地理预聚类+TSP"),
    ("self_refine", "A3: 维度导向自精炼"),
    ("tournament", "A4: 并行策略锦标赛"),
    ("constraint", "A5: 迭代约束满足"),
]

TEST_SCENARIOS = [
    {"id": 1, "name": "情侣珠海一日游", "input": "情侣珠海一日游，预算500元，喜欢拍照打卡"},
    {"id": 2, "name": "亲子海洋王国", "input": "带6岁孩子去长隆海洋王国，预算1000元"},
    {"id": 3, "name": "美食探索", "input": "珠海美食一日游，想吃海鲜和本地特色"},
    {"id": 4, "name": "特种兵打卡", "input": "一天打卡珠海所有著名景点，时间紧"},
    {"id": 5, "name": "休闲养老游", "input": "珠海两日游，节奏慢，喜欢公园和海边"},
]

# DeepSeek评分prompt前缀（固定部分，前缀缓存命中）
_SCORE_PREFIX = """你是旅游路线质量评审。请客观公正地评估以下路线。

## 第一步：识别场景类型

先判断这个需求属于哪种场景（5选1）：
- **美食型**：用户核心目的是吃喝探索（"美食一日游""想吃海鲜"）
- **目的地型**：用户指定了具体大景区（"长隆海洋王国""圆明新园"），会在该景区停留大半天
- **特种兵型**：用户要求密集打卡，跨区域赶场是正常行为
- **休闲型**：节奏慢、少景点、重体验（"休闲""慢""散步"）
- **观光型**：常规观光游览（默认）

## 第二步：按场景类型调整评分标准

评分标准(每项0-10分):

**intent_match** (意图匹配):
- 美食型：路线以餐饮为主就是好匹配，不需要大量景点
- 目的地型：只要包含了用户指定的核心目的地，即算高分（7-9）
- 特种兵型：不可能"一天打卡所有景点"是正常的，只要覆盖了重要景点就给7-8
- 休闲型：景点少（3-4个）不代表匹配差，节奏慢本身是需求
- 观光型：通用标准
  - 9-10: 完美匹配  |  7-8: 大部分匹配  |  5-6: 部分匹配  |  3-4: 低匹配  |  0-2: 不相关

**poi_quality** (POI质量):
- 按POI本身质量评分，不因数量少而扣分
- 美食型：质量主要看餐厅口碑和菜品评价
- 9-10: 都是值得专程去的  |  7-8: 大部分不错  |  5-6: 一般  |  3-4: 偏低  |  0-2: 不值得

**geo_continuity** (地理合理性):
- 美食型：餐厅可以分散，但不应来回折返
- 目的地型：POI集中在同一区域是优点，给8-9
- 特种兵型：跨区域赶场是预期行为，不要因为跨度大就扣分
- 休闲型：景点少且距离近加分
- 观光型：通用标准
  - 9-10: 流畅  |  7-8: 基本合理  |  5-6: 有绕路  |  3-4: 不合理  |  0-2: 混乱

**scene_diversity** (场景多样性):
- 美食型：只看餐饮内部多样性！不需要景点/购物/文化！
  - 9-10: 4种以上不同餐饮子类型  |  7-8: 3种  |  5-6: 2种  |  3-4: 全同类型  |  0-2: 毫无变化
- 目的地型：多样性不是重点，给7-8
- 特种兵型：覆盖多种类型景点加分
- 休闲型：不要求多样性，1-2种大类就够（给7-8）
- 观光型：通用标准
  - 9-10: 涵盖4种以上大类  |  7-8: 涵盖3种  |  5-6: 只有1-2种  |  3-4: 几乎单一  |  0-2: 完全没有

**overall** (总体): 综合以上维度和场景类型，给出你的真实满意度评分。

## 评分底线规则
1. 3个以上POI且时间合理 → geo_continuity ≥ 6
2. 包含了用户明确提到的核心需求 → intent_match ≥ 7
3. 路线没有明显错误 → overall ≥ 6
4. 不要因为"还可以更好"就给低分，6分="及格"，7分="不错"，8分="很好"
5. 列出2-3个优点(good_points)和2-3个改进建议(bad_points)
"""


def format_route(route_steps: list[dict]) -> str:
    """格式化路线供LLM评估。使用_display_category提升evaluator对diversity的感知。"""
    lines = []
    for i, step in enumerate(route_steps, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("_display_category") or poi.get("category", "?")
        price = poi.get("avg_price", 0)
        tags = poi.get("_scene_tags", [])
        arrive = step.get("arrival_time", "?")
        lines.append(f"{i}. {name} [{cat}] ¥{price} 到达:{arrive} 标签:{tags}")
    return "\n".join(lines)


async def llm_score(user_input: str, route_text: str) -> dict | None:
    """用DeepSeek给路线打分。"""
    prompt = _SCORE_PREFIX + f"""用户需求: {user_input}

路线:
{route_text}

输出JSON: {{"scene_type":"美食型/目的地型/特种兵型/休闲型/观光型","scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["优点1","优点2"],"bad_points":["建议1","建议2"]}}"""

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": EVAL_MODEL,
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
                if r.status_code != 200:
                    continue
                text = r.json()["choices"][0]["message"]["content"].strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                data = json.loads(text.strip())

                if "scores" in data:
                    scores = data["scores"]
                else:
                    keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
                    scores = {k: data[k] for k in keys if k in data}

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


async def llm_score_averaged(user_input: str, route_text: str, n: int = N_EVAL_RUNS) -> dict | None:
    """多次评分取平均，减少方差。"""
    results = []
    for _ in range(n):
        r = await llm_score(user_input, route_text)
        if r:
            results.append(r)
        await asyncio.sleep(0.5)  # 避免rate limit

    if not results:
        return None

    # 平均各维度分数
    dims = ["intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"]
    avg_scores = {}
    for dim in dims:
        vals = [r["scores"].get(dim, 0) for r in results if dim in r.get("scores", {})]
        avg_scores[dim] = round(sum(vals) / len(vals), 1) if vals else 0

    # 合并good/bad points（去重取前3）
    all_good = []
    all_bad = []
    for r in results:
        all_good.extend(r.get("good_points", []))
        all_bad.extend(r.get("bad_points", []))
    # 简单去重
    seen_good = set()
    seen_bad = set()
    unique_good = []
    unique_bad = []
    for g in all_good:
        if g not in seen_good:
            seen_good.add(g)
            unique_good.append(g)
    for b in all_bad:
        if b not in seen_bad:
            seen_bad.add(b)
            unique_bad.append(b)

    return {
        "scores": avg_scores,
        "overall": avg_scores.get("overall", 0),
        "good_points": unique_good[:3],
        "bad_points": unique_bad[:3],
        "eval_runs": len(results),
        "raw_scores": [r["scores"] for r in results],
    }


async def run_scenario_with_mode(scenario: dict, mode: str) -> dict:
    """用指定模式运行单个场景。"""
    os.environ["SYNTHESIZER_MODE"] = mode

    # 重新import以应用新模式
    from backend.agents_v3 import get_graph_c, TravelState
    from backend.agents_v3.graph import _graph_c

    # 清除图缓存，强制重建（因为synthesizer模式可能不同）
    import backend.agents_v3.graph as graph_mod
    graph_mod._graph_c = None
    from backend.agents_v3.graph import get_graph_c as _get_graph

    # 清除POI缓存
    from backend.agents_v3.meituan_client import clear_cache
    clear_cache()

    graph = _get_graph()

    initial: TravelState = {
        "user_input": scenario["input"],
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
    }

    try:
        t0 = time.time()
        result = await asyncio.wait_for(graph.ainvoke(initial), timeout=300)
        elapsed = time.time() - t0

        route = result.get("route", {})
        steps = route.get("route", []) if route else []

        # 3次eval取平均
        route_text = format_route(steps) if steps else ""
        eval_result = None
        if route_text:
            eval_result = await llm_score_averaged(scenario["input"], route_text)

        return {
            "id": scenario["id"],
            "name": scenario["name"],
            "success": True,
            "elapsed": round(elapsed, 1),
            "route_steps": len(steps),
            "poi_names": [s.get("poi", {}).get("name", "?") for s in steps[:6]],
            "eval": eval_result,
        }
    except asyncio.TimeoutError:
        return {"id": scenario["id"], "name": scenario["name"], "success": False, "error": "超时"}
    except Exception as e:
        return {"id": scenario["id"], "name": scenario["name"], "success": False, "error": str(e)}


async def main():
    # 启动美团模拟服务器
    import subprocess
    import requests as req

    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.meituan_server.main:app",
         "--host", "127.0.0.1", "--port", "8001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            req.get("http://127.0.0.1:8001/api/area/boundaries", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("美团模拟服务器启动失败")
        server_proc.kill()
        return

    print("=" * 70)
    print("架构对比测试")
    print(f"每条路线跑{N_EVAL_RUNS}次eval取平均 | 通过线={PASS_THRESHOLD}")
    print(f"架构数={len(ARCHITECTURES)} | 场景数={len(TEST_SCENARIOS)}")
    print(f"预计总测试数={len(ARCHITECTURES) * len(TEST_SCENARIOS)}")
    print("=" * 70)

    all_results = {}

    for mode, mode_desc in ARCHITECTURES:
        print(f"\n{'─' * 70}")
        print(f"架构: {mode} — {mode_desc}")
        print(f"{'─' * 70}")

        mode_results = []
        for sc in TEST_SCENARIOS:
            print(f"  场景{sc['id']}: {sc['name']}...", end=" ", flush=True)
            r = await run_scenario_with_mode(sc, mode)
            mode_results.append(r)

            if r["success"] and r.get("eval"):
                ev = r["eval"]
                s = ev["scores"]
                status = "✅" if ev["overall"] >= PASS_THRESHOLD else "❌"
                print(f"{status} overall={ev['overall']} "
                      f"(intent={s.get('intent_match','?')} poi={s.get('poi_quality','?')} "
                      f"geo={s.get('geo_continuity','?')} div={s.get('scene_diversity','?')}) "
                      f"[{r['elapsed']}s, {r['route_steps']}站]")
            elif r["success"]:
                print(f"⚠ 评分失败 [{r['elapsed']}s]")
            else:
                print(f"💥 {r.get('error', '?')}")

        all_results[mode] = mode_results

        # 模式汇总
        scored = [r for r in mode_results if r.get("success") and r.get("eval")]
        passed = [r for r in scored if r["eval"]["overall"] >= PASS_THRESHOLD]
        if scored:
            avg_overall = sum(r["eval"]["overall"] for r in scored) / len(scored)
            avg_time = sum(r["elapsed"] for r in mode_results if r.get("success")) / max(1, sum(1 for r in mode_results if r.get("success")))
            print(f"  → 通过: {len(passed)}/{len(scored)} | 平均overall: {avg_overall:.1f} | 平均耗时: {avg_time:.1f}s")

    # ── 最终对比 ──
    print(f"\n{'=' * 70}")
    print("最终对比")
    print(f"{'=' * 70}")
    print(f"{'架构':<20} {'通过':>6} {'overall':>8} {'intent':>7} {'poi':>5} {'geo':>5} {'div':>5} {'耗时':>6}")
    print(f"{'─' * 70}")

    comparison = []
    for mode, mode_desc in ARCHITECTURES:
        results = all_results.get(mode, [])
        scored = [r for r in results if r.get("success") and r.get("eval")]
        passed = [r for r in scored if r["eval"]["overall"] >= PASS_THRESHOLD]

        if not scored:
            print(f"{mode:<20} {'N/A':>6}")
            continue

        avg = lambda dim: sum(r["eval"]["scores"].get(dim, 0) for r in scored) / len(scored)
        avg_time = sum(r["elapsed"] for r in results if r.get("success")) / max(1, sum(1 for r in results if r.get("success")))

        row = {
            "mode": mode,
            "passed": f"{len(passed)}/{len(scored)}",
            "overall": avg("overall"),
            "intent_match": avg("intent_match"),
            "poi_quality": avg("poi_quality"),
            "geo_continuity": avg("geo_continuity"),
            "scene_diversity": avg("scene_diversity"),
            "avg_time": avg_time,
        }
        comparison.append(row)
        print(f"{mode:<20} {row['passed']:>6} {row['overall']:>8.1f} {row['intent_match']:>7.1f} "
              f"{row['poi_quality']:>5.1f} {row['geo_continuity']:>5.1f} {row['scene_diversity']:>5.1f} {row['avg_time']:>6.1f}s")

    # 保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "timestamp": ts,
        "n_eval_runs": N_EVAL_RUNS,
        "pass_threshold": PASS_THRESHOLD,
        "architectures": {mode: results for mode, results in all_results.items()},
        "comparison": comparison,
    }
    out_path = f"docs/logs/arch_comparison_{ts}.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 {out_path}")

    server_proc.terminate()
    server_proc.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
