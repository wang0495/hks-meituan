"""多模型全并发基准测试。

5进程(每模型1进程) 并发，进程内场景串行避免API过载。
使用方式:
    LLM_API_KEY=xxx LLM_BASE_URL=xxx python scripts/benchmarks/test_model_bench
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)

MODELS = [
    "xsparkx2flash",
    "xopqwen36v35b",
    "xopqwen35v35b",
    "xop3qwencodernext",
    "xopglmv47flash",
]
MAX_RETRIES = 3
SCENE_TIMEOUT = 180


def _init():
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    _env_file = Path(_project_root) / ".env"
    if _env_file.exists():
        for line in _env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())
    # Monkey-patch meituan_client (must happen before importing agents_v3)
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
    # Pre-import to catch errors early
    from test_5_scenes import SCENES  # noqa: F401


def _run_model(model: str, api_key: str, base_url: str) -> dict:
    """子进程：一个模型跑5个场景（串行避免单模型内API过载）。"""
    os.environ["LLM_API_KEY"] = api_key
    os.environ["LLM_BASE_URL"] = base_url
    os.environ["LLM_MODEL"] = model
    os.environ["EXPERT_LLM_MODEL"] = model
    return asyncio.run(_run_model_async(model))


async def _run_model_async(model: str) -> dict:
    from backend.agents_v3 import get_graph_c, TravelState
    from backend.agents_v3.experts.base import clear_llm_cache
    from backend.agents_v3.meituan_client import clear_cache
    from test_5_scenes import SCENES, score_route

    clear_llm_cache()
    clear_cache()
    get_graph_c()

    t0 = time.perf_counter()
    scene_results = []

    for scene_type, user_input in SCENES:
        r = await _run_one(scene_type, user_input, model)
        sn = r.get("scene", "?")
        sc = r.get("score", 0)
        gr = r.get("grade", "?")
        st = r.get("stops", 0)
        el = r.get("elapsed", 0)
        att = r.get("attempt", 1)
        names = r.get("route_names", [])
        route_str = " → ".join(names[:5]) + ("..." if len(names) > 5 else "") if names else "无路线"
        retry = f" (x{att})" if att > 1 else ""
        print(f"  [{model}][{sn}] {gr} {sc:5.1f} | {st:2d}站 {el:5.1f}s{retry} | {route_str}", flush=True)
        if r.get("error"):
            print(f"    错误: {r['error'][:80]}", flush=True)
        scene_results.append(r)

    elapsed = round(time.perf_counter() - t0, 1)
    avg = sum(r.get("score", 0) for r in scene_results) / max(len(scene_results), 1)
    print(f"  [{model}] >> 平均 {avg:.1f} | {elapsed}s", flush=True)
    return {"model": model, "total_elapsed": elapsed, "avg_score": round(avg, 1), "scenes": scene_results}


async def _run_one(scene_type: str, user_input: str, model: str) -> dict:
    from backend.agents_v3 import get_graph_c, TravelState
    from backend.agents_v3.experts.base import clear_llm_cache
    from backend.agents_v3.meituan_client import clear_cache
    from test_5_scenes import score_route

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.perf_counter()
        try:
            clear_llm_cache()
            clear_cache()
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

            guide_route = next((p for p in proposals if p.get("agent") == "guide_route"), None)
            guide_order = guide_route.get("content", {}).get("suggested_order", []) if guide_route else []
            scoring = score_route(route_list, scene_type, proposals, guide_order)

            return {
                "scene": scene_type, "model": model,
                "elapsed": round(elapsed, 1), "stops": len(route_list),
                "route_names": stop_names, "score": scoring["total"],
                "grade": scoring["grade"], "dims": scoring["dims"],
                "active_experts": active, "attempt": attempt,
            }
        except asyncio.TimeoutError:
            last_error = f"timeout({SCENE_TIMEOUT}s)"
            print(f"    [{model}][{scene_type}] 超时 ({attempt}/{MAX_RETRIES})", flush=True)
        except Exception as e:
            last_error = str(e)[:120]
            print(f"    [{model}][{scene_type}] 错误: {last_error[:80]} ({attempt}/{MAX_RETRIES})", flush=True)
        if attempt < MAX_RETRIES:
            await asyncio.sleep(3)

    return {"scene": scene_type, "model": model, "elapsed": 0, "error": last_error,
            "score": 0, "grade": "F", "stops": 0, "attempt": MAX_RETRIES}


def main():
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2")

    print("=" * 60)
    print("  多模型全并发基准测试 (5进程 x 场景串行)")
    print("=" * 60)
    print(f"  模型: {', '.join(MODELS)}")
    print(f"  API: {base_url}")
    print(f"  重试: {MAX_RETRIES} | 超时: {SCENE_TIMEOUT}s/场景")
    print(f"  开始: {datetime.now().strftime('%H:%M:%S')}")

    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=len(MODELS), initializer=_init) as pool:
        futures = {pool.submit(_run_model, m, api_key, base_url): m for m in MODELS}
        model_results = []
        for fut in futures:
            model = futures[fut]
            try:
                result = fut.result(timeout=SCENE_TIMEOUT * 5 * MAX_RETRIES)
                model_results.append(result)
            except Exception as e:
                model_results.append({"model": model, "avg_score": 0, "total_elapsed": 0, "scenes": [], "_error": str(e)})
                print(f"  [{model}] 进程失败: {e}", flush=True)

    total_elapsed = round(time.perf_counter() - t0, 1)

    # 排名
    from test_5_scenes import SCENES as _SCENES
    ranked = sorted(model_results, key=lambda x: x.get("avg_score", 0), reverse=True)

    print(f"\n{'=' * 60}")
    print("  排名结果")
    print(f"{'=' * 60}")
    print(f"\n  {'#':>2s}  {'模型':<22s} {'平均':>6s} {'耗时':>7s}  各场景")
    print(f"  {'─' * 65}")
    for i, mr in enumerate(ranked):
        sc = "  ".join(f"{s.get('scene', '?')[:2]}:{s.get('score', 0):.0f}" for s in mr.get("scenes", []))
        print(f"  {i+1:2d}  {mr.get('model', '?'):<22s} {mr.get('avg_score', 0):6.1f} {mr.get('total_elapsed', 0):6.0f}s  {sc}")

    print(f"\n  {'场景':6s} 最优模型")
    print(f"  {'─' * 50}")
    for st, _ in _SCENES:
        best_model, best_score = "?", -1
        for mr in model_results:
            for s in mr.get("scenes", []):
                if s.get("scene") == st and s.get("score", 0) > best_score:
                    best_score = s.get("score", 0)
                    best_model = mr.get("model", "?")
        print(f"  {st:6s} {best_model} ({best_score:.1f})")

    print(f"\n  总耗时: {total_elapsed}s ({len(MODELS)} 模型并发)")

    log_dir = Path(_project_root) / "docs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"model_bench_{ts}.json"
    log_file.write_text(json.dumps(ranked, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"  结果已保存: {log_file}")
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
