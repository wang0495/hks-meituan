"""分析基线结果并更新论文 baseline_compare 表格数据。

读取 baseline_single_llm_*_full.json 和 baseline_rag_*_full.json，
计算幻觉率、多样性等指标，输出可直接替换论文表格的数据。
"""
import json, glob, sys
from pathlib import Path
from collections import defaultdict

PROJECT = Path(__file__).resolve().parent
LOGS_DIR = PROJECT / "docs" / "logs"
POI_DB_PATHS = [
    PROJECT / "backend" / "data" / "city_poi_db.json",
    PROJECT / "data" / "city_poi_db.json",
]


def load_real_pois():
    for p in POI_DB_PATHS:
        if p.exists():
            data = json.load(open(p, encoding="utf-8"))
            if isinstance(data, dict) and "pois" in data:
                return set(pp.get("name", "") for pp in data["pois"])
            elif isinstance(data, list):
                return set(pp.get("name", "") for pp in data)
    return set()


def load_latest_result(method):
    """Load the latest _full.json or _partial.json for a method."""
    pattern = str(LOGS_DIR / f"baseline_{method}_*_full.json")
    files = sorted(glob.glob(pattern))
    if not files:
        # fallback to partial
        pattern = str(LOGS_DIR / f"baseline_{method}_*_partial.json")
        files = sorted(glob.glob(pattern))
    if not files:
        return None
    return json.load(open(files[-1], encoding="utf-8"))


def compute_hallucination(results, real_poi_names):
    """Compute hallucination rate: % of stop names not in real POI db."""
    total_stops = 0
    hallucinated = 0
    for r in results:
        stops = r.get("stops", [])
        for name in stops:
            total_stops += 1
            # Fuzzy match: check if the real name is contained or contains
            matched = False
            for real_name in real_poi_names:
                if name == real_name or name in real_name or real_name in name:
                    matched = True
                    break
            if not matched:
                hallucinated += 1
    return hallucinated / total_stops if total_stops > 0 else 0


def compute_diversity(results, test_cases):
    """Count unique route tuples per scene type."""
    type_routes = defaultdict(set)
    for i, r in enumerate(results):
        if i < len(test_cases):
            scene_type = test_cases[i][0]
        else:
            scene_type = r.get("scene", "?")
        route_tuple = tuple(r.get("stops", []))
        type_routes[scene_type].add(route_tuple)
    return {st: len(routes) for st, routes in type_routes.items()}


def main():
    real_pois = load_real_pois()
    print(f"Real POIs loaded: {len(real_pois)}")

    # Load test cases from test_baselines.py
    # We'll load from the result metadata
    test_cases_count = 100  # known

    # Greedy results
    greedy = load_latest_result("greedy")
    # Single-LLM results
    single_llm = load_latest_result("single_llm")
    # RAG results
    rag = load_latest_result("rag")

    # Load CityFlow results for reference
    cf_files = sorted(glob.glob(str(LOGS_DIR / "test_100_*.json")))
    cityflow = json.load(open(cf_files[0], encoding="utf-8")) if cf_files else None

    print("\n" + "=" * 70)
    print("  BASELINE ANALYSIS RESULTS")
    print("=" * 70)

    for name, data in [("Greedy", greedy), ("Single-LLM", single_llm),
                       ("RAG", rag), ("CityFlow", cityflow)]:
        if data is None:
            print(f"\n  {name}: NO DATA")
            continue

        results = data.get("results", [])
        summary = data.get("summary", {})
        n = len(results)
        partial = data.get("meta", {}).get("partial", False)

        pass_count = sum(1 for r in results if r.get("route_ok"))
        pass_rate = pass_count / n if n else 0
        avg_score = sum(r.get("score", 0) for r in results) / n if n else 0
        avg_stops = sum(r.get("stop_count", 0) for r in results) / n if n else 0

        halluc_rate = compute_hallucination(results, real_pois) if real_pois else -1

        # Diversity
        # Need test cases for diversity calculation
        type_div = {}
        if name != "CityFlow":
            # We know the test case structure
            from scripts.benchmarks.test_baselines import TEST_CASES
            div = compute_diversity(results, TEST_CASES)
            type_div = div

        print(f"\n  {name} ({n} scenes{' [PARTIAL]' if partial else ''})")
        print(f"    Pass Rate:  {pass_rate*100:.0f}% ({pass_count}/{n})")
        print(f"    Avg Score:  {avg_score:.1f}")
        print(f"    Avg Stops:  {avg_stops:.1f}")
        if halluc_rate >= 0:
            print(f"    Hallucination: {halluc_rate*100:.1f}%")
        if type_div:
            for st, cnt in sorted(type_div.items()):
                print(f"    Diversity {st}: {cnt} unique")

    # Generate LaTeX table replacement
    print("\n" + "=" * 70)
    print("  LATEX TABLE VALUES (for tab:baseline_compare)")
    print("=" * 70)

    # Collect all three baselines
    all_data = {}
    for name, data in [("greedy", greedy), ("single_llm", single_llm), ("rag", rag)]:
        if data:
            results = data.get("results", [])
            n = len(results)
            all_data[name] = {
                "n": n,
                "partial": data.get("meta", {}).get("partial", False),
                "pass_rate": sum(1 for r in results if r.get("route_ok")) / n if n else 0,
                "avg_score": sum(r.get("score", 0) for r in results) / n if n else 0,
                "avg_stops": sum(r.get("stop_count", 0) for r in results) / n if n else 0,
                "halluc": compute_hallucination(results, real_pois) if real_pois else 0,
            }
            from scripts.benchmarks.test_baselines import TEST_CASES
            div = compute_diversity(results, TEST_CASES)
            all_data[name]["diversity"] = div

    for name in ["greedy", "single_llm", "rag"]:
        d = all_data.get(name)
        if not d:
            print(f"  {name}: NO DATA")
            continue
        print(f"\n  {name} ({d['n']} scenes{' [PARTIAL]' if d['partial'] else ''}):")
        print(f"    Pass Rate      = {d['pass_rate']*100:.0f}\\%")
        print(f"    Avg Route Score = {d['avg_score']:.1f}")
        print(f"    Hallucination  = {d['halluc']*100:.1f}\\%")
        div_vals = d.get("diversity", {})
        if div_vals:
            div_str = "/".join(str(v) for v in div_vals.values())
            type_count = len(div_vals)
            print(f"    Route Diversity = {div_str} per type ({type_count} types)")
        else:
            print(f"    Route Diversity = N/A")
        print(f"    Avg Stops      = {d['avg_stops']:.1f}")

    # Also output if RAG is missing
    if "rag" not in all_data:
        print("\n  [WARNING] RAG baseline data not yet available.")
    if "single_llm" not in all_data:
        print("\n  [WARNING] Single-LLM baseline data not yet available.")

    # Output greedy diversity for reference
    if "greedy" in all_data and all_data["greedy"]["diversity"]:
        print(f"\n  Greedy diversity detail: {all_data['greedy']['diversity']}")


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT))
    main()
