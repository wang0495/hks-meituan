"""方差对比测试：同一场景跑N次，统计路线一致性。"""
import asyncio
import json
import os
import sys
import time

# 确保env加载
from dotenv import load_dotenv
load_dotenv()

from backend.agents_v3.graph import get_graph_c


def extract_route_names(result: dict) -> list[str]:
    """提取路线中的POI名称列表。"""
    route = result.get("route")
    if not route or not route.get("route"):
        return []
    return [s.get("poi", {}).get("name", "?") for s in route["route"]]


def compare_runs(all_names: list[list[str]]) -> dict:
    """对比多次运行的路线一致性。"""
    if not all_names:
        return {"error": "no results"}

    # 所有名称的交集
    common = set(all_names[0])
    for names in all_names[1:]:
        common &= set(names)

    # 所有名称的并集
    all_unique = set()
    for names in all_names:
        all_unique |= set(names)

    return {
        "runs": len(all_names),
        "common_pois": sorted(common),
        "common_count": len(common),
        "total_unique": len(all_unique),
        "consistency": f"{len(common)}/{max(len(n) for n in all_names)}",
        "per_run_count": [len(n) for n in all_names],
        "all_names": all_names,
    }


async def run_once(query: str, run_id: int) -> dict:
    """单次运行。"""
    graph = get_graph_c()
    t0 = time.time()
    try:
        result = await graph.ainvoke({"user_input": query})
    except Exception as e:
        print(f"  Run {run_id} ERROR: {e}")
        return {"error": str(e)}

    elapsed = time.time() - t0
    names = extract_route_names(result)
    scene = result.get("scene_type", "?")
    errors = result.get("errors", [])

    print(f"  Run {run_id}: {len(names)} stops, scene={scene}, {elapsed:.1f}s")
    for n in names:
        print(f"    - {n}")
    if errors:
        print(f"    Errors: {errors}")

    return {
        "names": names,
        "scene": scene,
        "elapsed": elapsed,
        "errors": errors,
    }


async def test_scene(query: str, n_runs: int = 3):
    """测试一个场景。"""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"Runs: {n_runs}")
    print(f"{'='*60}")

    results = []
    # 推理模型需要更多token
    import httpx
    # 增大全局超时
    httpx_timeout = httpx.Timeout(300.0, connect=30.0)

    for i in range(n_runs):
        r = await run_once(query, i + 1)
        results.append(r)

    # 统计
    valid = [r for r in results if "names" in r]
    if len(valid) < 2:
        print("\nNot enough valid runs for comparison")
        return

    all_names = [r["names"] for r in valid]
    stats = compare_runs(all_names)

    print(f"\n--- 结果统计 ---")
    print(f"共同POI: {stats['common_count']} 个 → {stats['common_pois']}")
    print(f"一致性: {stats['consistency']}")
    print(f"每次POI数: {stats['per_run_count']}")
    print(f"总唯一POI: {stats['total_unique']}")

    # 每次运行独有的POI
    for i, names in enumerate(all_names):
        others = set()
        for j, n in enumerate(all_names):
            if i != j:
                others |= set(n)
        unique_to_i = set(names) - others
        if unique_to_i:
            print(f"  Run {i+1} 独有: {sorted(unique_to_i)}")

    return stats


async def main():
    scenes = [
        "情侣珠海一日游",
        # "珠海美食一日游",
    ]

    for query in scenes:
        await test_scene(query, n_runs=3)


if __name__ == "__main__":
    asyncio.run(main())
