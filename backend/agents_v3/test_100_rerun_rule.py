"""补跑规则降级的场景 — 5并发重跑LLM评分，合并回原JSON。

用法: python -m backend.agents_v3.test_100_rerun_rule
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

import urllib.request
try:
    urllib.request.urlopen("http://localhost:8001/api/poi/search?limit=1", timeout=2)
except Exception:
    try:
        urllib.request.urlopen("http://localhost:8002/api/poi/search?limit=1", timeout=2)
        import backend.agents_v3.meituan_client as _mc
        _mc.BASE = "http://localhost:8002/api"
    except Exception:
        pass

RERUN_CONCURRENCY = 5
SCENE_TIMEOUT = 180

# 找到最新的 test_100_*.json
log_dir = Path(_project_root) / "docs" / "logs"
json_files = sorted(log_dir.glob("test_100_*.json"), reverse=True)
if not json_files:
    print("未找到 test_100_*.json，先跑 test_100_scenes")
    sys.exit(1)
SOURCE_FILE = json_files[0]
print(f"读取: {SOURCE_FILE}")


async def _rerun_one(r: dict, sem: asyncio.Semaphore) -> dict:
    """重跑单个场景（低并发）。"""
    from backend.agents_v3 import get_graph_c, TravelState
    from backend.agents_v3.test_5_scenes import llm_score_route, score_route

    idx = r["id"]
    scene_type = r["scene"]
    user_input = r["input"]

    async with sem:
        last_error = None
        for attempt in range(1, 3):
            t0 = time.perf_counter()
            try:
                graph = get_graph_c()
                state: TravelState = {
                    "user_input": user_input,
                    "proposals": [],
                    "negotiation_msgs": [],
                    "errors": [],
                }
                result = await asyncio.wait_for(graph.ainvoke(state), timeout=SCENE_TIMEOUT)
                elapsed = time.perf_counter() - t0

                route = result.get("route") or {}
                proposals = result.get("proposals", [])
                active = result.get("active_experts", [])
                route_list = route.get("route", [])
                stop_names = [s.get("poi", s).get("name", "?") for s in route_list] if route_list else []

                scoring = await llm_score_route(user_input, scene_type, route_list)
                if scoring is None:
                    scoring = score_route(route_list, scene_type, proposals)
                    scoring["source"] = "rule"
                else:
                    scoring["total"] = scoring.get("score", 0)
                    scoring["notes"] = scoring.get("bad_points", [])

                src = scoring.get("source", "rule")
                print(f"  #{idx:3d} [{scene_type[:2]}] {scoring['grade']} {scoring['total']:5.1f} [{src}] | {len(stop_names):2d}站 {elapsed:5.1f}s", flush=True)
                return {
                    "id": idx, "scene": scene_type, "input": user_input,
                    "elapsed": round(elapsed, 1), "active_experts": active,
                    "stops": stop_names, "stop_count": len(stop_names),
                    "errors": result.get("errors", []),
                    "route_ok": len(stop_names) >= 3,
                    "score": scoring["total"], "grade": scoring["grade"],
                    "source": src, "dims": scoring.get("dims", {}),
                    "score_notes": scoring.get("notes", []), "attempt": attempt,
                }
            except asyncio.TimeoutError:
                last_error = f"timeout({SCENE_TIMEOUT}s)"
            except Exception as e:
                last_error = str(e)[:120]
            if attempt < 2:
                await asyncio.sleep(3)

        print(f"  #{idx:3d} [{scene_type[:2]}] FAIL {last_error[:60]}", flush=True)
        r["error"] = last_error
        return r


async def main():
    data = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    results = data["results"]

    # 找出规则降级的场景
    rule_cases = [r for r in results if r.get("source") == "rule" and "route_ok" in r]
    # 也找出评分超100的（LLM评分bug）
    over100 = [r for r in results if r.get("score", 0) > 100]
    rerun_ids = {r["id"] for r in rule_cases} | {r["id"] for r in over100}

    rerun_list = [r for r in results if r["id"] in rerun_ids]
    print(f"\n规则降级: {len(rule_cases)} | 评分超100: {len(over100)} | 合计补跑: {len(rerun_list)}")

    # 预热
    print("[预热] 编译 LangGraph...")
    from backend.agents_v3 import get_graph_c
    from backend.agents_v3.meituan_client import clear_cache
    from backend.agents_v3.experts.base import clear_llm_cache
    get_graph_c()
    clear_cache()
    clear_llm_cache()
    print("[预热] 完成\n")

    sem = asyncio.Semaphore(RERUN_CONCURRENCY)
    t0 = time.perf_counter()
    tasks = [_rerun_one(r, sem) for r in rerun_list]
    new_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并：用新结果替换旧结果
    id_to_new = {}
    for nr in new_results:
        if isinstance(nr, Exception):
            continue
        id_to_new[nr["id"]] = nr

    updated = 0
    still_rule = 0
    for i, r in enumerate(results):
        if r["id"] in id_to_new:
            results[i] = id_to_new[r["id"]]
            updated += 1
            if id_to_new[r["id"]].get("source") == "rule":
                still_rule += 1

    elapsed = round(time.perf_counter() - t0, 1)

    # ── 重新统计 ──
    from collections import defaultdict
    valid = [r for r in results if r and "route_ok" in r]
    errors_list = [r for r in results if r and r.get("error")]
    ok_count = sum(1 for r in valid if r.get("route_ok"))
    scores = [min(r.get("score", 0), 100) for r in valid]  # clamp 100
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_time = sum(r.get("elapsed", 0) for r in valid) / len(valid) if valid else 0

    grade_order = "SABCDF"
    grades = []
    for r in valid:
        s = min(r.get("score", 0), 100)
        if s >= 90: grades.append("S")
        elif s >= 80: grades.append("A")
        elif s >= 70: grades.append("B")
        elif s >= 60: grades.append("C")
        elif s >= 40: grades.append("D")
        else: grades.append("F")
    grade_dist = {g: grades.count(g) for g in grade_order if grades.count(g) > 0}

    # 重新计算grade（clamp score）
    for r in valid:
        s = min(r.get("score", 0), 100)
        if s >= 90: r["grade"] = "S"
        elif s >= 80: r["grade"] = "A"
        elif s >= 70: r["grade"] = "B"
        elif s >= 60: r["grade"] = "C"
        elif s >= 40: r["grade"] = "D"
        else: r["grade"] = "F"

    by_scene = defaultdict(list)
    for r in valid:
        by_scene[r["scene"]].append(r)

    print(f"\n{'═' * 70}")
    print(f"  补跑完成: {updated} 个更新, {still_rule} 个仍为规则降级, 耗时 {elapsed}s")
    print(f"{'═' * 70}")
    print(f"\n  路线生成: {ok_count}/{len(results)}")
    print(f"  平均评分: {avg_score:.1f} (score clamped to 100)")
    print(f"  平均耗时: {avg_time:.1f}s")
    llm_count = sum(1 for r in valid if r.get("source") == "llm")
    rule_count = sum(1 for r in valid if r.get("source") == "rule")
    print(f"  评分来源: LLM {llm_count} / Rule {rule_count}")

    grade_str = "  ".join(f"{g}:{n}" for g, n in grade_dist.items())
    print(f"\n  等级分布: {grade_str}")

    print(f"\n  {'场景类型':8s} │ {'数量':>4s} │ {'均分':>6s} │ {'通过':>4s} │ S/A/B/C/D/F")
    print(f"  {'─'*8}─┼─{'─'*4}─┼─{'─'*6}─┼─{'─'*4}─┼─{'─'*20}")
    for st in ["美食型", "目的地型", "特种兵型", "休闲型", "观光型"]:
        rs = by_scene.get(st, [])
        if not rs:
            continue
        avg_s = sum(min(r["score"], 100) for r in rs) / len(rs)
        pass_n = sum(1 for r in rs if min(r["score"], 100) >= 60)
        g_counts = {g: sum(1 for r in rs if r.get("grade") == g) for g in grade_order}
        g_str = "/".join(str(g_counts[g]) for g in grade_order)
        print(f"  {st:8s} │ {len(rs):4d} │ {avg_s:6.1f} │ {pass_n:4d} │ {g_str}")

    # 最差10个
    if valid:
        print(f"\n  最差10个:")
        worst = sorted(valid, key=lambda r: min(r["score"], 100))[:10]
        for r in worst:
            print(f"    #{r['id']:3d} [{r['scene'][:2]}] {r['grade']} {min(r['score'],100):5.1f} | {r['input'][:35]}")
        print(f"\n  最佳10个:")
        best = sorted(valid, key=lambda r: min(r["score"], 100), reverse=True)[:10]
        for r in best:
            print(f"    #{r['id']:3d} [{r['scene'][:2]}] {r['grade']} {min(r['score'],100):5.1f} | {r['input'][:35]}")

    # 保存更新后的JSON
    data["summary"] = {
        "avg_score": round(avg_score, 1),
        "pass_rate": round(ok_count / len(results), 3),
        "grade_distribution": grade_dist,
        "by_scene_type": {
            st: {
                "count": len(rs),
                "avg": round(sum(min(r["score"], 100) for r in rs) / len(rs), 1),
                "pass": sum(1 for r in rs if min(r["score"], 100) >= 60),
            }
            for st, rs in by_scene.items()
        },
        "errors": len(errors_list),
        "llm_scored": llm_count,
        "rule_scored": rule_count,
    }
    data["meta"]["rerun_elapsed"] = elapsed
    data["meta"]["rerun_count"] = len(rerun_list)

    SOURCE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n  已更新: {SOURCE_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
