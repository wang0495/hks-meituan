"""100场景多进程压力测试 — 10进程×10场景，每进程独立连接池。

讯飞500并发零错误，多进程突破本地连接池瓶颈。

使用方式:
    python -m backend.agents_v3.test_100_scenes
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── 100 测试场景 ──

TEST_CASES: list[tuple[str, str]] = [
    # ── 美食型 × 20 ──
    ("美食型", "珠海美食一日游，想吃海鲜和早茶"),
    ("美食型", "珠海情侣浪漫晚餐约会，预算500元"),
    ("美食型", "珠海海鲜大排档攻略，越便宜越好"),
    ("美食型", "珠海夜市小吃一条龙，晚上出来觅食"),
    ("美食型", "珠海本地人推荐的茶餐厅和糖水铺"),
    ("美食型", "珠海亲子美食之旅，小孩子也爱吃的"),
    ("美食型", "珠海只有2小时吃点什么好"),
    ("美食型", "珠海退休老人粤式早茶慢生活"),
    ("美食型", "珠海湾仔海鲜街和周边美食"),
    ("美食型", "珠海下雨天有什么好吃的，室内美食"),
    ("美食型", "珠海朋友聚餐AA制，预算100元每人"),
    ("美食型", "珠海横琴新区附近有什么好吃的"),
    ("美食型", "珠海唐家湾古镇附近美食推荐"),
    ("美食型", "珠海拱北口岸附近美食下午茶"),
    ("美食型", "珠海带宠物出游顺便找吃的"),
    ("美食型", "珠海斗门农家乐一日吃"),
    ("美食型", "珠海金湾机场附近美食赶飞机前吃"),
    ("美食型", "珠海夏天吃甜品消暑攻略"),
    ("美食型", "珠海素菜素食餐厅推荐"),
    ("美食型", "珠海老字号美食打卡拍照好看"),

    # ── 目的地型 × 20 ──
    ("目的地型", "带孩子去珠海长隆海洋王国玩一天"),
    ("目的地型", "珠海海泉湾温泉度假村一日游"),
    ("目的地型", "珠海御温泉泡汤放松一天"),
    ("目的地型", "珠海圆明新园一日游攻略"),
    ("目的地型", "珠海渔女像和情侣路半日游"),
    ("目的地型", "珠海梦幻水城玩水一日"),
    ("目的地型", "珠海长隆晚上看烟花表演"),
    ("目的地型", "珠海外伶仃岛一日往返"),
    ("目的地型", "珠海金沙滩玩沙子带小孩"),
    ("目的地型", "珠海海滨公园野餐加放风筝"),
    ("目的地型", "珠海梅溪牌坊和农科奇观一日游"),
    ("目的地型", "珠海横琴创新方游玩一天"),
    ("目的地型", "珠海罗西尼钟表博物馆参观"),
    ("目的地型", "珠海野狸岛骑行环岛游"),
    ("目的地型", "珠海港珠澳大桥观光"),
    ("目的地型", "珠海东澳岛一日游攻略"),
    ("目的地型", "珠海景山公园爬山看日落"),
    ("目的地型", "珠海下雨天带娃去室内乐园"),
    ("目的地型", "珠海情侣去海泉湾泡温泉预算300"),
    ("目的地型", "珠海长隆只玩半天下午场"),

    # ── 特种兵型 × 20 ──
    ("特种兵型", "珠海特种兵一日游打卡所有网红景点"),
    ("特种兵型", "珠海6点出发一天打卡10个景点"),
    ("特种兵型", "珠海3小时极限打卡只看地标"),
    ("特种兵型", "珠海网红拍照点一天全打完"),
    ("特种兵型", "珠海特种兵穷游不花钱景点"),
    ("特种兵型", "珠海一天走完所有沙滩"),
    ("特种兵型", "珠海从拱北到横琴一天串完"),
    ("特种兵型", "珠海老城区特种兵步行为主"),
    ("特种兵型", "珠海亲子特种兵小孩也能跟上"),
    ("特种兵型", "珠海日出日落特种兵攻略"),
    ("特种兵型", "珠海10大公园一天刷完"),
    ("特种兵型", "珠海夜景特种兵18点到22点"),
    ("特种兵型", "珠海情侣网红打卡特种兵"),
    ("特种兵型", "珠海骑行特种兵骑车打卡"),
    ("特种兵型", "珠海博物馆特种兵一天看完所有博物馆"),
    ("特种兵型", "珠海海岛特种兵一天跳岛"),
    ("特种兵型", "珠海下雨特种兵室内景点一天搞定"),
    ("特种兵型", "珠海退休特种兵慢节奏版"),
    ("特种兵型", "珠海8点到20点特种兵12小时"),
    ("特种兵型", "珠海预算200特种兵吃喝全包"),

    # ── 休闲型 × 20 ──
    ("休闲型", "珠海情侣周末休闲游慢慢逛放松一下"),
    ("休闲型", "珠海海边发呆一下午什么都不干"),
    ("休闲型", "珠海书店咖啡店慢慢逛一天"),
    ("休闲型", "珠海公园野餐慢生活"),
    ("休闲型", "珠海情侣路散步看海聊天"),
    ("休闲型", "珠海下午茶慢慢喝不赶场"),
    ("休闲型", "珠海退休老两口逛公园喝茶"),
    ("休闲型", "珠海亲子慢游小朋友说停就停"),
    ("休闲型", "珠海下雨天咖啡馆窝一天"),
    ("休闲型", "珠海独处发呆看海的一天"),
    ("休闲型", "珠海傍晚散步看日落"),
    ("休闲型", "珠海金沙滩躺一天晒太阳"),
    ("休闲型", "珠海温泉慢泡养生一日"),
    ("休闲型", "珠海朋友周末chill找个地方坐坐聊聊天"),
    ("休闲型", "珠海民宿住一天附近逛逛"),
    ("休闲型", "珠海下雨了室内有什么休闲的"),
    ("休闲型", "珠海斗门乡村慢生活一日"),
    ("休闲型", "珠海情侣拍照休闲游"),
    ("休闲型", "珠海横琴半天休闲下午茶加散步"),
    ("休闲型", "珠海带狗去公园溜达顺便吃个饭"),

    # ── 观光型 × 20 ──
    ("观光型", "珠海经典观光一日游看看地标建筑"),
    ("观光型", "珠海渔女像日月贝圆明新园一天看完"),
    ("观光型", "珠海历史文化景点观光一日"),
    ("观光型", "珠海现代建筑观光看城市天际线"),
    ("观光型", "珠海海岛风光一日游"),
    ("观光型", "珠海夜景观光晚上好看的地方"),
    ("观光型", "珠海免费景点观光不花钱"),
    ("观光型", "珠海亲子观光寓教于乐"),
    ("观光型", "珠海情侣浪漫地标观光"),
    ("观光型", "珠海港珠澳大桥和周边观光"),
    ("观光型", "珠海半天观光精华路线"),
    ("观光型", "珠海老城区历史建筑观光"),
    ("观光型", "珠海横琴新区现代建筑观光"),
    ("观光型", "珠海唐家湾古镇文化观光"),
    ("观光型", "珠海教堂寺庙观光一日"),
    ("观光型", "珠海拍照观光出片好看的地方"),
    ("观光型", "珠海退休老人轻松观光"),
    ("观光型", "珠海朋友一起观光打卡"),
    ("观光型", "珠海雨天室内观光博物馆美术馆"),
    ("观光型", "珠海沿海公路自驾观光"),
]

NUM_WORKERS = 10
SCENE_TIMEOUT = 180


# ═══════════════════════════════════════════════════════════════════
# 子进程：每个进程跑一批场景（串行，各自连接池）
# ═══════════════════════════════════════════════════════════════════

def _init_worker():
    """子进程初始化：加载 .env + 预热graph。"""
    _env_file = Path(_project_root) / ".env"
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

    from backend.agents_v3 import get_graph_c
    from backend.agents_v3.meituan_client import clear_cache
    get_graph_c()
    clear_cache()


def _run_batch(batch: list[tuple[int, str, str]]) -> list[dict]:
    """子进程串行跑一批场景。"""
    from backend.agents_v3 import get_graph_c, TravelState
    from backend.agents_v3.test_5_scenes import llm_score_route_median, score_route

    results = []
    for idx, scene_type, user_input in batch:
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
                result = asyncio.run(
                    asyncio.wait_for(graph.ainvoke(state), timeout=SCENE_TIMEOUT)
                )
                elapsed = time.perf_counter() - t0

                route = result.get("route") or {}
                proposals = result.get("proposals", [])
                active = result.get("active_experts", [])
                route_list = route.get("route", [])
                stop_names = [
                    s.get("poi", s).get("name", "?") for s in route_list
                ] if route_list else []

                scoring = asyncio.run(
                    llm_score_route_median(user_input, scene_type, route_list, n_runs=3)
                )
                if scoring is None:
                    scoring = score_route(route_list, scene_type, proposals)
                    scoring["source"] = "rule"
                else:
                    scoring["total"] = scoring.get("score", 0)
                    scoring["notes"] = scoring.get("bad_points", [])

                results.append({
                    "id": idx, "scene": scene_type, "input": user_input,
                    "elapsed": round(elapsed, 1), "active_experts": active,
                    "stops": stop_names, "stop_count": len(stop_names),
                    "errors": result.get("errors", []),
                    "route_ok": len(stop_names) >= 3,
                    "score": scoring["total"], "grade": scoring["grade"],
                    "source": scoring.get("source", "rule"),
                    "dims": scoring.get("dims", {}),
                    "score_notes": scoring.get("notes", []),
                    "attempt": attempt,
                })
                break
            except asyncio.TimeoutError:
                last_error = f"timeout({SCENE_TIMEOUT}s)"
            except Exception as e:
                last_error = str(e)[:120]
            if attempt < 2:
                time.sleep(2)
        else:
            results.append({
                "id": idx, "scene": scene_type, "input": user_input,
                "error": last_error, "elapsed": 0, "score": 0, "grade": "F",
                "stops": [], "stop_count": 0, "dims": {}, "score_notes": [],
                "route_ok": False, "attempt": 2,
            })
    return results


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  100场景多进程压力测试 — agents_v3")
    print("=" * 70)
    print(f"  场景数: {len(TEST_CASES)}")
    print(f"  进程数: {NUM_WORKERS}")
    print(f"  超时: {SCENE_TIMEOUT}s/场景")
    print(f"  开始: {datetime.now().strftime('%H:%M:%S')}")

    # 分批：10进程×10场景
    batches: list[list[tuple[int, str, str]]] = [[] for _ in range(NUM_WORKERS)]
    for i, (st, ui) in enumerate(TEST_CASES):
        batches[i % NUM_WORKERS].append((i + 1, st, ui))

    t0 = time.perf_counter()

    all_results: list[dict] = [None] * len(TEST_CASES)
    done_workers = 0

    with ProcessPoolExecutor(max_workers=NUM_WORKERS, initializer=_init_worker) as pool:
        futures = {pool.submit(_run_batch, b): wi for wi, b in enumerate(batches)}
        for fut in as_completed(futures):
            done_workers += 1
            batch_results = fut.result()
            for r in batch_results:
                all_results[r["id"] - 1] = r
            elapsed = round(time.perf_counter() - t0, 1)
            print(f"  [worker {done_workers}/{NUM_WORKERS}] 完成 {len(batch_results)} 场景 | 总耗时 {elapsed}s", flush=True)

    total_elapsed = round(time.perf_counter() - t0, 1)

    # ══════════════════════════════════════════════════════════════
    # 统计
    # ══════════════════════════════════════════════════════════════
    valid = [r for r in all_results if r and "route_ok" in r]
    errors_list = [r for r in all_results if r and r.get("error")]
    ok_count = sum(1 for r in valid if r.get("route_ok"))
    scores = [min(r.get("score", 0), 100) for r in valid]
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_time = sum(r.get("elapsed", 0) for r in valid) / len(valid) if valid else 0

    # 重新计算grade（clamp 100）
    grade_order = "SABCDF"
    for r in valid:
        s = min(r.get("score", 0), 100)
        r["grade"] = (
            "S" if s >= 90 else "A" if s >= 80 else "B" if s >= 70
            else "C" if s >= 60 else "D" if s >= 40 else "F"
        )
    grades = [r["grade"] for r in valid]
    grade_dist = {g: grades.count(g) for g in grade_order if grades.count(g) > 0}

    by_scene = defaultdict(list)
    for r in valid:
        by_scene[r["scene"]].append(r)

    # ── 打印结果 ──
    print(f"\n\n{'═' * 70}")
    print(f"  总 结 ({len(valid)} 成功 / {len(errors_list)} 失败 / {total_elapsed}s)")
    print(f"{'═' * 70}")

    print(f"\n  路线生成: {ok_count}/{len(TEST_CASES)}")
    print(f"  平均评分: {avg_score:.1f}")
    print(f"  平均耗时: {avg_time:.1f}s")
    llm_count = sum(1 for r in valid if r.get("source") == "llm")
    rule_count = sum(1 for r in valid if r.get("source") == "rule")
    print(f"  评分来源: LLM {llm_count} / Rule {rule_count}")

    grade_str = "  ".join(f"{g}:{n}" for g, n in grade_dist.items())
    print(f"\n  等级分布: {grade_str}")

    # 按场景类型
    print(f"\n  {'场景类型':8s} │ {'数量':>4s} │ {'均分':>6s} │ {'通过':>4s} │ S/A/B/C/D/F")
    print(f"  {'─'*8}─┼─{'─'*4}─┼─{'─'*6}─┼─{'─'*4}─┼─{'─'*20}")
    for st in ["美食型", "目的地型", "特种兵型", "休闲型", "观光型"]:
        rs = by_scene.get(st, [])
        if not rs:
            continue
        avg_s = sum(min(r["score"], 100) for r in rs) / len(rs)
        pass_n = sum(1 for r in rs if min(r["score"], 100) >= 60)
        g_counts = {g: sum(1 for r in rs if r["grade"] == g) for g in grade_order}
        g_str = "/".join(str(g_counts[g]) for g in grade_order)
        print(f"  {st:8s} │ {len(rs):4d} │ {avg_s:6.1f} │ {pass_n:4d} │ {g_str}")

    # 按评分维度
    all_dims = sorted(set(d for r in valid for d in r.get("dims", {})))
    if all_dims:
        print(f"\n  {'场景':8s} | " + " | ".join(f"{d[:4]:>4s}" for d in all_dims))
        print(f"  {'─'*8}─┼─" + "─┼─".join("─"*4 for _ in all_dims))
        for st in ["美食型", "目的地型", "特种兵型", "休闲型", "观光型"]:
            rs = by_scene.get(st, [])
            if not rs:
                continue
            dim_avgs = []
            for d in all_dims:
                vals = [r.get("dims", {}).get(d, 0) for r in rs]
                dim_avgs.append(f"{sum(vals)/len(vals):4.0f}" if vals else "   -")
            print(f"  {st:8s} | " + " | ".join(dim_avgs))

    # 失败场景
    if errors_list:
        print(f"\n  失败场景 ({len(errors_list)}):")
        for r in errors_list:
            print(f"    #{r['id']:3d} [{r['scene'][:2]}] {r.get('input', '?')[:30]} → {r.get('error', '?')[:50]}")

    # 最差/最佳
    if valid:
        print(f"\n  最差10个:")
        worst = sorted(valid, key=lambda r: min(r["score"], 100))[:10]
        for r in worst:
            print(f"    #{r['id']:3d} [{r['scene'][:2]}] {r['grade']} {min(r['score'],100):5.1f} | {r['input'][:35]}")

        print(f"\n  最佳10个:")
        best = sorted(valid, key=lambda r: min(r["score"], 100), reverse=True)[:10]
        for r in best:
            print(f"    #{r['id']:3d} [{r['scene'][:2]}] {r['grade']} {min(r['score'],100):5.1f} | {r['input'][:35]}")

    # ══════════════════════════════════════════════════════════════
    # 保存JSON
    # ══════════════════════════════════════════════════════════════
    model = os.getenv("LLM_MODEL", "?")
    output = {
        "meta": {
            "model": model,
            "total_cases": len(TEST_CASES),
            "workers": NUM_WORKERS,
            "timeout": SCENE_TIMEOUT,
            "elapsed_total": total_elapsed,
            "timestamp": datetime.now().isoformat(),
        },
        "summary": {
            "avg_score": round(avg_score, 1),
            "pass_rate": round(ok_count / len(TEST_CASES), 3),
            "grade_distribution": grade_dist,
            "by_scene_type": {
                st: {
                    "count": len(rs),
                    "avg": round(sum(min(r["score"], 100) for r in rs) / len(rs), 1),
                    "pass": sum(1 for r in rs if min(r["score"], 100) >= 60),
                }
                for st, rs in by_scene.items()
            },
            "llm_scored": llm_count,
            "rule_scored": rule_count,
            "errors": len(errors_list),
        },
        "results": all_results,
    }

    log_dir = Path(_project_root) / "docs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"test_100_{ts}.json"
    log_file.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n  结果已保存: {log_file}")

    return avg_score >= 60


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
