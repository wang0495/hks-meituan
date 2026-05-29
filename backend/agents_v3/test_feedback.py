"""多轮反馈测试：验证 feedback_entry 选择性重跑效果。

测试流程：
1. 正常流程 → 完整 graph 生成路线 + 评分
2. 构造反馈状态 → 选择性重跑部分 expert + 缓存其余
3. 反馈流程 → feedback_entry → 选择性 expert 重跑 → 评分
4. 对比：评分变化、耗时节省、路线差异

使用方式：
    cd backend
    LLM_API_KEY=... python -m agents_v3.test_feedback
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# ── 加载 .env ──────────────────────────────────────────────────────
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# ── Monkey-patch meituan_client ────────────────────────────────────
import urllib.request
try:
    urllib.request.urlopen("http://localhost:8001/api/poi/search?limit=1", timeout=2)
except Exception:
    try:
        urllib.request.urlopen("http://localhost:8002/api/poi/search?limit=1", timeout=2)
        import backend.agents_v3.meituan_client as _mc
        _mc.BASE = "http://localhost:8002/api"
        print("[配置] meituan_client.BASE → 8002")
    except Exception:
        print("[警告] 8001 和 8002 均无 POI API，将降级到本地 JSON")


# ── 复用 test_5_scenes 的评分函数和场景定义 ─────────────────────
from backend.agents_v3.test_5_scenes import score_route, SCENES


# ── 反馈测试用例 ─────────────────────────────────────────────────
# 每个用例指定：反馈内容、需要重跑的 expert、权重调整（模拟 feedback_router）
FEEDBACK_CASES = [
    {
        "scene_type": "美食型",
        "feedback": "我想多看海边，不要只在市区里",
        "rerun_experts": ["poi", "destination"],
        "weight_adjust": {"poi": +0.2, "destination": +0.3, "food": -0.1},
        "reason": "海边POI重选，food不变",
    },
    {
        "scene_type": "目的地型",
        "feedback": "多加几个好吃的，孩子想吃冰淇淋",
        "rerun_experts": ["food", "poi"],
        "weight_adjust": {"food": +0.3, "poi": +0.1},
        "reason": "food重新选甜品冰淇淋，poi微调",
    },
    {
        "scene_type": "特种兵型",
        "feedback": "景点太多了精简一下，但加上咖啡店",
        "rerun_experts": ["poi", "food"],
        "weight_adjust": {"poi": +0.1, "food": +0.2, "traffic": -0.2},
        "reason": "poi数量调整+加咖啡，food重选",
    },
    {
        "scene_type": "休闲型",
        "feedback": "换个更安静的区域，不想太商业化",
        "rerun_experts": ["poi", "local_expert"],
        "weight_adjust": {"poi": +0.2, "local_expert": +0.3},
        "reason": "poi重选安静区域，local_expert推隐藏宝藏",
    },
    {
        "scene_type": "观光型",
        "feedback": "想看更多文化类景点，少点自然风光",
        "rerun_experts": ["poi"],
        "weight_adjust": {"poi": +0.1},
        "reason": "poi重新筛选偏好文化类",
    },
]


# ═══════════════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════════════

async def run_normal(scene_type: str, user_input: str) -> dict:
    """Phase 1: 正常完整流程。"""
    from backend.agents_v3 import get_graph_c, TravelState
    from backend.agents_v3.meituan_client import clear_cache

    clear_cache()
    graph = get_graph_c()

    state: TravelState = {
        "user_input": user_input,
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
    }

    t0 = time.perf_counter()
    try:
        result = await asyncio.wait_for(graph.ainvoke(state), timeout=180)
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.perf_counter() - t0, 1)}

    elapsed = time.perf_counter() - t0
    route = result.get("route") or {}
    route_list = route.get("route", [])
    proposals = list(result.get("proposals", []))
    stop_names = [s.get("poi", s).get("name", "?") for s in route_list]
    scoring = score_route(route_list, scene_type, proposals, [])

    return {
        "elapsed": round(elapsed, 1),
        "stop_count": len(stop_names),
        "stops": stop_names,
        "score": scoring["total"],
        "grade": scoring["grade"],
        "dims": scoring["dims"],
        "notes": scoring["notes"],
        "proposals": proposals,
        "route": route,
        "active_experts": result.get("active_experts", []),
        "expert_weights": result.get("expert_weights", {}),
        "user_intent": result.get("user_intent", {}),
        "scene_type": result.get("scene_type", scene_type),
        "candidates": result.get("candidates", []),
    }


async def run_feedback(prev: dict, fb_case: dict) -> dict:
    """Phase 2: 反馈重入流程（选择性 expert 重跑）。"""
    from backend.agents_v3 import get_feedback_graph_c, TravelState
    from backend.agents_v3.meituan_client import clear_cache

    clear_cache()
    graph = get_feedback_graph_c()

    rerun_experts = fb_case["rerun_experts"]
    feedback = fb_case["feedback"]
    weight_adjust = fb_case["weight_adjust"]
    rerun_set = set(rerun_experts)

    # 缓存非重跑 expert 的提案
    cached = [p for p in prev.get("proposals", []) if p.get("agent") not in rerun_set]

    # 调整权重（模拟 feedback_router 的 LLM 输出）
    old_weights = dict(prev.get("expert_weights", {}))
    new_weights = {}
    for k, v in old_weights.items():
        new_weights[k] = max(0.1, min(1.0, v + weight_adjust.get(k, 0)))
    # 确保重跑 expert 的权重 >= 0.3
    for name in rerun_experts:
        new_weights[name] = max(new_weights.get(name, 0.3), 0.3)

    # prev_round_context
    prev_context = {
        "last_weights": old_weights,
        "score_5dim": prev.get("dims", {}),
        "last_score": prev.get("score", 0),
        "last_stops": prev.get("stops", []),
        "reject_reason": feedback,
    }

    # 构造反馈状态 — 拼接原始输入 + 反馈，让 expert 有完整上下文
    original_input = next(
        (inp for st, inp in SCENES if st == fb_case["scene_type"]), ""
    )
    combined_input = f"{original_input}（用户反馈：{feedback}）"

    state: TravelState = {
        "user_input": combined_input,
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
        # 反馈重入
        "feedback_mode": True,
        "rerun_experts": rerun_experts,
        "cached_proposals": cached,
        "prev_round_context": prev_context,
        # 复用上轮上下文（不重跑 rule_guard）
        "user_intent": prev.get("user_intent", {}),
        "scene_type": prev.get("scene_type", fb_case["scene_type"]),
        "candidates": prev.get("candidates", []),
        # 调整后的权重
        "expert_weights": new_weights,
        "active_experts": rerun_experts,
    }

    t0 = time.perf_counter()
    try:
        result = await asyncio.wait_for(graph.ainvoke(state), timeout=180)
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.perf_counter() - t0, 1)}

    elapsed = time.perf_counter() - t0
    route = result.get("route") or {}
    route_list = route.get("route", [])
    proposals = list(result.get("proposals", []))
    stop_names = [s.get("poi", s).get("name", "?") for s in route_list]
    scoring = score_route(route_list, fb_case["scene_type"], proposals, [])

    return {
        "elapsed": round(elapsed, 1),
        "stop_count": len(stop_names),
        "stops": stop_names,
        "score": scoring["total"],
        "grade": scoring["grade"],
        "dims": scoring["dims"],
        "notes": scoring["notes"],
        "proposals_count": len(proposals),
        "cached_count": len(cached),
        "rerun_count": len(rerun_experts),
    }


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

async def main():
    print("=" * 70)
    print("  多轮反馈测试 — feedback_entry 选择性重跑效果对比")
    print("=" * 70)

    # 预加载
    print("\n[预热] 编译 normal graph + feedback graph...")
    from backend.agents_v3 import get_graph_c, get_feedback_graph_c
    get_graph_c()
    get_feedback_graph_c()
    from backend.agents_v3.meituan_client import clear_cache
    clear_cache()
    print("[预热] 完成\n")

    results = []

    for fb_case in FEEDBACK_CASES:
        scene_type = fb_case["scene_type"]
        feedback = fb_case["feedback"]
        rerun_experts = fb_case["rerun_experts"]

        scene_input = next((inp for st, inp in SCENES if st == scene_type), "")
        if not scene_input:
            print(f"  ⚠ {scene_type}: 无对应场景，跳过")
            continue

        print(f"\n{'━' * 70}")
        print(f"  {scene_type}")
        print(f"  原始: {scene_input}")
        print(f"  反馈: {feedback}")
        print(f"  重跑: {rerun_experts}")
        print(f"{'━' * 70}")

        # Phase 1
        print(f"\n  [Phase 1] 正常流程...")
        normal = await run_normal(scene_type, scene_input)

        if "error" in normal:
            print(f"    ✗ 失败: {normal['error'][:80]}")
            results.append({"scene": scene_type, "feedback": feedback, "phase": "normal_error"})
            continue

        print(f"    路线 ({normal['stop_count']}站): {' → '.join(normal['stops'][:6])}")
        print(f"    评分: {normal['score']} ({normal['grade']}) | 耗时: {normal['elapsed']}s")
        print(f"    专家: {normal['active_experts']}")

        # Phase 2
        print(f"\n  [Phase 2] 反馈重入 ({len(rerun_experts)} expert重跑)...")
        fb = await run_feedback(normal, fb_case)

        if "error" in fb:
            print(f"    ✗ 失败: {fb['error'][:80]}")
            results.append({
                "scene": scene_type, "feedback": feedback,
                "phase": "feedback_error", "normal_score": normal["score"],
            })
            continue

        print(f"    路线 ({fb['stop_count']}站): {' → '.join(fb['stops'][:6])}")
        print(f"    评分: {fb['score']} ({fb['grade']}) | 耗时: {fb['elapsed']}s")
        print(f"    缓存: {fb['cached_count']}条 | 提案总数: {fb['proposals_count']}")

        # 对比
        score_diff = fb["score"] - normal["score"]
        time_saved = normal["elapsed"] - fb["elapsed"]

        print(f"\n  ┌─ 对比 ───────────────────────────────────────────────┐")
        print(f"  │ 评分: {normal['score']:5.1f} → {fb['score']:5.1f}  ({'+' if score_diff >= 0 else ''}{score_diff:+.1f})")
        print(f"  │ 耗时: {normal['elapsed']:5.0f}s → {fb['elapsed']:5.0f}s  ({'省' if time_saved > 0 else '多'}{abs(time_saved):.0f}s)")
        print(f"  │ 站数: {normal['stop_count']} → {fb['stop_count']}")
        # 变化的维度
        for dim in set(list(normal.get("dims", {})) + list(fb.get("dims", {}))):
            old_v = normal.get("dims", {}).get(dim, 0)
            new_v = fb.get("dims", {}).get(dim, 0)
            if abs(old_v - new_v) > 3:
                arrow = "↑" if new_v > old_v else "↓"
                print(f"  │ {dim}: {old_v:.0f} → {new_v:.0f} {arrow}")
        print(f"  └{'─' * 52}┘")

        results.append({
            "scene": scene_type,
            "feedback": feedback,
            "rerun_experts": rerun_experts,
            "normal_score": normal["score"],
            "normal_grade": normal["grade"],
            "normal_elapsed": normal["elapsed"],
            "normal_stops": normal["stop_count"],
            "normal_stops_list": normal["stops"],
            "fb_score": fb["score"],
            "fb_grade": fb["grade"],
            "fb_elapsed": fb["elapsed"],
            "fb_stops": fb["stop_count"],
            "fb_stops_list": fb["stops"],
            "score_diff": round(score_diff, 1),
            "time_saved": round(time_saved, 1),
        })

    # ══════════════════════════════════════════════════════════════
    # 总结
    # ══════════════════════════════════════════════════════════════
    print(f"\n\n{'═' * 70}")
    print(f"  总结")
    print(f"{'═' * 70}")

    valid = [r for r in results if "fb_score" in r]
    errors = [r for r in results if "error" in str(r.get("phase", ""))]

    if valid:
        avg_normal = sum(r["normal_score"] for r in valid) / len(valid)
        avg_fb = sum(r["fb_score"] for r in valid) / len(valid)
        avg_time_n = sum(r["normal_elapsed"] for r in valid) / len(valid)
        avg_time_fb = sum(r["fb_elapsed"] for r in valid) / len(valid)

        print(f"\n  {'场景':8s} │ {'正常':>5s} │ {'反馈':>5s} │ {'差值':>5s} │ {'正常耗时':>7s} │ {'反馈耗时':>7s} │ {'节省':>5s} │ 重跑expert")
        print(f"  {'─'*8}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*7}─┼─{'─'*7}─┼─{'─'*5}─┼─{'─'*12}")
        for r in valid:
            d = r["score_diff"]
            s = r["time_saved"]
            print(f"  {r['scene']:8s} │ {r['normal_score']:5.1f} │ {r['fb_score']:5.1f} │ {d:+5.1f} │ {r['normal_elapsed']:5.0f}s  │ {r['fb_elapsed']:5.0f}s  │ {s:+5.0f}s │ {','.join(r['rerun_experts'])}")

        score_improved = sum(1 for r in valid if r["score_diff"] > 0)
        time_saved_count = sum(1 for r in valid if r["time_saved"] > 0)

        print(f"\n  平均评分: 正常 {avg_normal:.1f} → 反馈 {avg_fb:.1f} ({avg_fb - avg_normal:+.1f})")
        print(f"  平均耗时: 正常 {avg_time_n:.1f}s → 反馈 {avg_time_fb:.1f}s (节省 {avg_time_n - avg_time_fb:.1f}s)")
        print(f"  评分提升: {score_improved}/{len(valid)} | 耗时节省: {time_saved_count}/{len(valid)}")
        print(f"  通过: {len(valid)}/{len(FEEDBACK_CASES)}")

        if errors:
            print(f"  失败: {len(errors)} ({', '.join(r['scene'] for r in errors)})")

    # 保存结果
    log_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "feedback_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: docs/logs/feedback_test_results.json")

    return len(valid) == len(FEEDBACK_CASES)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
