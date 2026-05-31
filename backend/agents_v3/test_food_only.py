"""美食型20场景快速测试 — 验证多样性修复效果。

使用方式:
    python -m backend.agents_v3.test_food_only
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agents_v3.test_100_scenes import TEST_CASES, _run_batch

# 筛选美食型
FOOD_CASES = [(st, ui) for st, ui in TEST_CASES if st == "美食型"]

NUM_WORKERS = 5
SCENE_TIMEOUT = 120


def _run_food_batch(batch):
    """运行一批美食场景（复用 test_100_scenes 的 _run_batch）。"""
    return _run_batch(batch)


def main():
    print("=" * 60)
    print("  美食型20场景测试 — 多样性修复验证")
    print("=" * 60)
    print(f"  场景数: {len(FOOD_CASES)}")
    print(f"  进程数: {NUM_WORKERS}")
    print(f"  开始: {datetime.now().strftime('%H:%M:%S')}")

    batches = [[] for _ in range(NUM_WORKERS)]
    for i, (st, ui) in enumerate(FOOD_CASES):
        batches[i % NUM_WORKERS].append((i + 1, st, ui))

    t0 = time.perf_counter()
    all_results = [None] * len(FOOD_CASES)

    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as pool:
        futures = {pool.submit(_run_batch, b): wi for wi, b in enumerate(batches)}
        for fut in as_completed(futures):
            batch_results = fut.result()
            for r in batch_results:
                all_results[r["id"] - 1] = r
            print(f"  batch done: {len(batch_results)} scenes | {round(time.perf_counter()-t0, 1)}s", flush=True)

    total_elapsed = round(time.perf_counter() - t0, 1)

    # 统计
    valid = [r for r in all_results if r and "route_ok" in r]
    errors_list = [r for r in all_results if r and r.get("error")]
    scores = [min(r.get("score", 0), 100) for r in valid]
    avg_score = sum(scores) / len(scores) if scores else 0
    ok_count = sum(1 for r in valid if r.get("route_ok"))
    grades = []
    for r in valid:
        s = min(r.get("score", 0), 100)
        r["grade"] = (
            "S" if s >= 90 else "A" if s >= 80 else "B" if s >= 70
            else "C" if s >= 60 else "D" if s >= 40 else "F"
        )
        grades.append(r["grade"])

    grade_dist = Counter(grades)

    print(f"\n{'═' * 60}")
    print(f"  美食型测试结果 ({total_elapsed}s)")
    print(f"{'═' * 60}")
    print(f"  路线生成: {ok_count}/{len(FOOD_CASES)}")
    print(f"  平均评分: {avg_score:.1f}")
    print(f"  通过率(≥60): {sum(1 for s in scores if s >= 60)}/{len(scores)}")
    print(f"  等级分布: {' '.join(f'{g}:{grade_dist.get(g,0)}' for g in 'SABCDF')}")

    print(f"\n  {'#':>3s} │ {'评分':>4s} │ {'等级':>3s} │ {'站点':>4s} │ 场景")
    print(f"  {'─'*3}─┼─{'─'*4}─┼─{'─'*3}─┼─{'─'*4}─┼─{'─'*30}")
    for r in valid:
        s = min(r.get("score", 0), 100)
        stops = r.get("stops", [])
        print(f"  {r['id']:>3d} │ {s:>4.0f} │ {r['grade']:>3s} │ {len(stops):>4d} │ {r['input'][:30]}")
        # 显示餐饮子类分布
        food_stops = []
        for st in stops:
            if any(kw in st for kw in ["餐厅", "海鲜", "粉", "面", "粥", "甜品", "茶餐厅", "烧烤", "火锅", "夜市", "小吃", "排档"]):
                food_stops.append(st)
        if food_stops:
            print(f"      餐饮: {', '.join(food_stops[:6])}")

    if errors_list:
        print(f"\n  错误 ({len(errors_list)}):")
        for r in errors_list:
            print(f"    #{r.get('id', '?')}: {r.get('error', 'unknown')[:80]}")

    # 保存结果
    result_file = Path(__file__).parent / "test_food_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "avg_score": round(avg_score, 1),
            "pass_rate": round(sum(1 for s in scores if s >= 60) / len(scores) if scores else 0, 3),
            "grades": dict(grade_dist),
            "results": all_results,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  结果已保存: {result_file}")


if __name__ == "__main__":
    main()
