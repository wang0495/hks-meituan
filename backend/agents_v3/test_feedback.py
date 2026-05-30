"""多轮反馈测试：验证 feedback_entry 选择性重跑效果。

LLM 评分：给 LLM 看原始路线 + 反馈 + 新路线，让它判断：
1. 新路线是否响应了反馈（feedback_response 0-10）
2. 新路线整体质量（overall 0-10）
3. 对比原始路线是变好还是变差（improvement -1/0/+1）

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

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import httpx

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

# ── 场景定义 ────────────────────────────────────────────────────
SCENES = [
    ("美食型",     "珠海美食一日游，想吃海鲜和早茶"),
    ("目的地型",   "带孩子去珠海长隆海洋王国玩一天"),
    ("特种兵型",   "珠海特种兵一日游，打卡所有网红景点"),
    ("休闲型",     "珠海情侣周末休闲游，慢慢逛放松一下"),
    ("观光型",     "珠海经典观光一日游，看看地标建筑"),
]

# ── 反馈测试用例 ─────────────────────────────────────────────────
FEEDBACK_CASES = [
    {
        "scene_type": "美食型",
        "feedback": "我想多看海边，不要只在市区里",
        "rerun_experts": ["poi", "destination"],
        "weight_adjust": {"poi": +0.2, "destination": +0.3, "food": -0.1},
    },
    {
        "scene_type": "目的地型",
        "feedback": "多加几个好吃的，孩子想吃冰淇淋",
        "rerun_experts": ["food", "poi"],
        "weight_adjust": {"food": +0.3, "poi": +0.1},
    },
    {
        "scene_type": "特种兵型",
        "feedback": "景点太多了精简一下，但加上咖啡店",
        "rerun_experts": ["poi", "food"],
        "weight_adjust": {"poi": +0.1, "food": +0.2, "traffic": -0.2},
    },
    {
        "scene_type": "休闲型",
        "feedback": "换个更安静的区域，不想太商业化",
        "rerun_experts": ["poi", "local_expert"],
        "weight_adjust": {"poi": +0.2, "local_expert": +0.3},
    },
    {
        "scene_type": "观光型",
        "feedback": "想看更多文化类景点，少点自然风光",
        "rerun_experts": ["poi"],
        "weight_adjust": {"poi": +0.1},
    },
]


# ═══════════════════════════════════════════════════════════════════
# LLM 评分（反馈感知）
# ═══════════════════════════════════════════════════════════════════

_FEEDBACK_SCORE_RUBRIC = """你是路线规划评估专家。现在评估一次【路线调整】的效果。

用户原始需求: {user_input}
用户反馈: {feedback}

【调整前路线】:
{old_route_text}

【调整后路线】:
{new_route_text}

请评估调整后路线，输出JSON:
{{
  "feedback_response": <0-10, 调整后路线多大程度上响应了用户的反馈，10=完全响应>,
  "overall": <0-10, 调整后路线的整体质量>,
  "improvement": <-1/0/+1, 相比调整前路线整体是变差(-1)持平(0)还是变好(+1)>,
  "good_points": ["优点1", "优点2"],
  "bad_points": ["问题1", "问题2"]
}}

注意:
- feedback_response 是核心指标：用户说"想看海边"但路线全在市区=低分，路线加海边景点=高分
- overall 独立于 feedback_response：即使反馈响应了，路线本身也要合理
- improvement 基于整体判断：如果响应了反馈但引入了新问题（如距离太远），可以是-1
- 长隆等大型主题公园本身就是一天的行程，1-2站是合理的，不要因此扣分"""


def _format_route(route_list: list[dict]) -> str:
    """格式化路线供 LLM 评估。"""
    lines = []
    for i, s in enumerate(route_list, 1):
        poi = s.get("poi", s)
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        arrive = s.get("arrival_time", "?")
        lines.append(f"{i}. {name} [{cat}] ¥{price} 到达:{arrive}")
    return "\n".join(lines) if lines else "(空路线)"


async def llm_feedback_score(
    user_input: str,
    feedback: str,
    old_route: list[dict],
    new_route: list[dict],
) -> dict | None:
    """LLM 评估反馈调整效果。使用环境变量配置的模型。"""
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "")

    if not api_key or not base_url or not model:
        print("    [评分] 无 LLM 配置，跳过 LLM 评分")
        return None

    url = f"{base_url.rstrip('/')}/chat/completions"
    prompt = _FEEDBACK_SCORE_RUBRIC.format(
        user_input=user_input,
        feedback=feedback,
        old_route_text=_format_route(old_route),
        new_route_text=_format_route(new_route),
    )

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 1000,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                    },
                )
                if r.status_code != 200:
                    continue
                text = r.json()["choices"][0]["message"]["content"].strip()
                # 处理可能的 markdown 代码块包裹
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                data = json.loads(text.strip())

                scores = data.get("scores", data)
                fr = scores.get("feedback_response", 0)
                ov = scores.get("overall", 0)
                imp = scores.get("improvement", 0)

                # 验证范围
                if not (0 <= fr <= 10 and 0 <= ov <= 10 and imp in (-1, 0, 1)):
                    continue

                return {
                    "feedback_response": fr,
                    "overall": ov,
                    "improvement": imp,
                    "good_points": data.get("good_points", []),
                    "bad_points": data.get("bad_points", []),
                }
        except Exception as e:
            if attempt < 1:
                await asyncio.sleep(2)
    return None


# ═══════════════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════════════

async def run_normal(scene_type: str, user_input: str, max_retries: int = 2) -> dict:
    """Phase 1: 正常完整流程（超时重试）。"""
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

    for attempt in range(max_retries):
        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(graph.ainvoke(state), timeout=180)
        except Exception as e:
            elapsed = round(time.perf_counter() - t0, 1)
            if attempt < max_retries - 1:
                print(f"    ⚠ 超时/失败，重试 {attempt+1}/{max_retries}: {str(e)[:50]}")
                clear_cache()
                continue
            return {"error": str(e), "elapsed": elapsed}

        elapsed = time.perf_counter() - t0
        route = result.get("route") or {}
        route_list = route.get("route", [])
        proposals = list(result.get("proposals", []))
        stop_names = [s.get("poi", s).get("name", "?") for s in route_list]

        return {
            "elapsed": round(elapsed, 1),
            "stop_count": len(stop_names),
            "stops": stop_names,
            "route_list": route_list,
            "proposals": proposals,
            "route": route,
            "active_experts": result.get("active_experts", []),
            "expert_weights": result.get("expert_weights", {}),
            "user_intent": result.get("user_intent", {}),
            "scene_type": result.get("scene_type", scene_type),
            "candidates": result.get("candidates", []),
        }


async def run_feedback(prev: dict, fb_case: dict, max_retries: int = 2) -> dict:
    """Phase 2: 反馈重入流程（选择性 expert 重跑，超时重试）。"""
    from backend.agents_v3 import get_feedback_graph_c, TravelState
    from backend.agents_v3.meituan_client import clear_cache

    rerun_experts = fb_case["rerun_experts"]
    feedback = fb_case["feedback"]
    weight_adjust = fb_case["weight_adjust"]
    rerun_set = set(rerun_experts)

    cached = [p for p in prev.get("proposals", []) if p.get("agent") not in rerun_set]

    old_weights = dict(prev.get("expert_weights", {}))
    new_weights = {}
    for k, v in old_weights.items():
        new_weights[k] = max(0.1, min(1.0, v + weight_adjust.get(k, 0)))
    for name in rerun_experts:
        new_weights[name] = max(new_weights.get(name, 0.3), 0.3)

    prev_context = {
        "last_weights": old_weights,
        "last_score": 0,
        "last_stops": prev.get("stops", []),
        "reject_reason": feedback,
    }

    original_input = next(
        (inp for st, inp in SCENES if st == fb_case["scene_type"]), ""
    )
    combined_input = f"{original_input}（用户反馈：{feedback}）"

    state: TravelState = {
        "user_input": combined_input,
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
        "feedback_mode": True,
        "rerun_experts": rerun_experts,
        "cached_proposals": cached,
        "prev_round_context": prev_context,
        "user_intent": prev.get("user_intent", {}),
        "scene_type": prev.get("scene_type", fb_case["scene_type"]),
        "candidates": prev.get("candidates", []),
        "expert_weights": new_weights,
        "active_experts": rerun_experts,
    }

    clear_cache()
    graph = get_feedback_graph_c()

    for attempt in range(max_retries):
        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(graph.ainvoke(state), timeout=180)
        except Exception as e:
            elapsed = round(time.perf_counter() - t0, 1)
            if attempt < max_retries - 1:
                print(f"    ⚠ 超时/失败，重试 {attempt+1}/{max_retries}: {str(e)[:50]}")
                clear_cache()
                continue
            return {"error": str(e), "elapsed": elapsed}

        elapsed = time.perf_counter() - t0
        route = result.get("route") or {}
        route_list = route.get("route", [])
        proposals = list(result.get("proposals", []))
        stop_names = [s.get("poi", s).get("name", "?") for s in route_list]

        return {
            "elapsed": round(elapsed, 1),
            "stop_count": len(stop_names),
            "stops": stop_names,
            "route_list": route_list,
            "proposals_count": len(proposals),
            "cached_count": len(cached),
            "rerun_count": len(rerun_experts),
        }


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

async def main():
    print("=" * 70)
    print("  多轮反馈测试 — LLM 评分（反馈感知）")
    print("=" * 70)

    print("\n[预热] 编译 graph...")
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
        print(f"    耗时: {normal['elapsed']}s | 专家: {normal['active_experts']}")

        # Phase 2
        print(f"\n  [Phase 2] 反馈重入 ({len(rerun_experts)} expert重跑)...")
        fb = await run_feedback(normal, fb_case)

        if "error" in fb:
            print(f"    ✗ 失败: {fb['error'][:80]}")
            results.append({"scene": scene_type, "feedback": feedback, "phase": "feedback_error"})
            continue

        print(f"    路线 ({fb['stop_count']}站): {' → '.join(fb['stops'][:6])}")
        print(f"    耗时: {fb['elapsed']}s | 缓存: {fb['cached_count']}条")

        # Phase 3: LLM 评分
        print(f"\n  [Phase 3] LLM 评分...")
        score = await llm_feedback_score(
            scene_input, feedback,
            normal.get("route_list", []),
            fb.get("route_list", []),
        )

        if score:
            fr = score["feedback_response"]
            ov = score["overall"]
            imp = score["improvement"]
            imp_str = {1: "变好", 0: "持平", -1: "变差"}[imp]
            print(f"    反馈响应: {fr}/10 | 整体质量: {ov}/10 | 对比: {imp_str}")
            for g in score["good_points"][:2]:
                print(f"    ✓ {g}")
            for b in score["bad_points"][:2]:
                print(f"    ✗ {b}")
        else:
            print(f"    LLM 评分失败")
            score = {}

        # 对比
        time_saved = normal["elapsed"] - fb["elapsed"]
        print(f"\n  ┌─ 对比 ───────────────────────────────────────────────┐")
        print(f"  │ 耗时: {normal['elapsed']:5.0f}s → {fb['elapsed']:5.0f}s  ({'省' if time_saved > 0 else '多'}{abs(time_saved):.0f}s)")
        print(f"  │ 站数: {normal['stop_count']} → {fb['stop_count']}")
        if score:
            print(f"  │ 反馈响应: {score['feedback_response']}/10")
            print(f"  │ 整体质量: {score['overall']}/10")
            print(f"  │ 改善: {score['improvement']:+d}")
        print(f"  └{'─' * 52}┘")

        results.append({
            "scene": scene_type,
            "feedback": feedback,
            "rerun_experts": rerun_experts,
            "normal_elapsed": normal["elapsed"],
            "normal_stops": normal["stop_count"],
            "normal_stops_list": normal["stops"],
            "fb_elapsed": fb["elapsed"],
            "fb_stops": fb["stop_count"],
            "fb_stops_list": fb["stops"],
            "time_saved": round(time_saved, 1),
            **{f"llm_{k}": v for k, v in (score or {}).items()},
        })

    # ══════════════════════════════════════════════════════════════
    # 总结
    # ══════════════════════════════════════════════════════════════
    print(f"\n\n{'═' * 70}")
    print(f"  总结")
    print(f"{'═' * 70}")

    valid = [r for r in results if "llm_overall" in r]
    errors = [r for r in results if "error" in str(r.get("phase", ""))]

    if valid:
        avg_fr = sum(r["llm_feedback_response"] for r in valid) / len(valid)
        avg_ov = sum(r["llm_overall"] for r in valid) / len(valid)
        improved = sum(1 for r in valid if r.get("llm_improvement", 0) > 0)
        worse = sum(1 for r in valid if r.get("llm_improvement", 0) < 0)

        print(f"\n  {'场景':8s} │ {'反馈响应':>6s} │ {'整体质量':>6s} │ {'改善':>4s} │ {'耗时节省':>6s} │ 重跑expert")
        print(f"  {'─'*8}─┼─{'─'*6}─┼─{'─'*6}─┼─{'─'*4}─┼─{'─'*6}─┼─{'─'*12}")
        for r in valid:
            imp = {1: "变好", 0: "持平", -1: "变差"}[r.get("llm_improvement", 0)]
            print(f"  {r['scene']:8s} │ {r['llm_feedback_response']:6.1f} │ {r['llm_overall']:6.1f} │ {imp:4s} │ {r['time_saved']:+5.0f}s │ {','.join(r['rerun_experts'])}")

        print(f"\n  平均反馈响应: {avg_fr:.1f}/10 | 平均整体质量: {avg_ov:.1f}/10")
        print(f"  改善: {improved}/{len(valid)} | 变差: {worse}/{len(valid)}")
        print(f"  通过: {len(valid)}/{len(FEEDBACK_CASES)}")

        if errors:
            print(f"  失败: {len(errors)} ({', '.join(r['scene'] for r in errors)})")

    # 保存
    log_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "feedback_llm_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: docs/logs/feedback_llm_results.json")

    return len(valid) == len(FEEDBACK_CASES)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
