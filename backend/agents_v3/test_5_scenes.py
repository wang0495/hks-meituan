"""五场景 E2E 验证：完整 graph 跑通 5 种场景类型 + 多维评分。

使用方式：
    cd backend
    python -m agents_v3.test_5_scenes
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持 cd backend && python -m agents_v3.test_5_scenes）
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── 加载 .env ──────────────────────────────────────────────────────
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# ── Monkey-patch meituan_client BASE if 8001 unavailable ──────────
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


# ── 五场景定义 ──────────────────────────────────────────────────────
SCENES = [
    ("美食型",     "珠海美食一日游，想吃海鲜和早茶"),
    ("目的地型",   "带孩子去珠海长隆海洋王国玩一天"),
    ("特种兵型",   "珠海特种兵一日游，打卡所有网红景点"),
    ("休闲型",     "珠海情侣周末休闲游，慢慢逛放松一下"),
    ("观光型",     "珠海经典观光一日游，看看地标建筑"),
]

# ── 每种场景的评分期望 ──────────────────────────────────────────────
_SCENE_EXPECT = {
    "美食型": {
        "min_stops": 3, "max_stops": 8,
        "must_categories": {"餐饮"},
        "nice_categories": {"景点"},
        "forbidden_categories": set(),
        "food_ratio_min": 0.4,  # 至少40%餐饮
        "max_leg_km": 25,
    },
    "目的地型": {
        "min_stops": 1, "max_stops": 8,
        "must_categories": {"景点", "娱乐"},
        "nice_categories": {"餐饮"},
        "forbidden_categories": set(),
        "must_keywords": ["长隆", "海洋"],
        "max_leg_km": 20,
    },
    "特种兵型": {
        "min_stops": 6, "max_stops": 15,
        "must_categories": {"景点"},
        "nice_categories": {"餐饮", "文化"},
        "forbidden_categories": set(),
        "max_leg_km": 20,
    },
    "休闲型": {
        "min_stops": 3, "max_stops": 9,
        "must_categories": {"景点"},
        "nice_categories": {"餐饮", "公园", "文化"},
        "forbidden_categories": set(),
        "max_leg_km": 18,
    },
    "观光型": {
        "min_stops": 3, "max_stops": 10,
        "must_categories": {"景点"},
        "nice_categories": {"餐饮", "文化"},
        "forbidden_categories": set(),
        "must_keywords": ["渔女", "情侣路", "日月贝", "圆明新园"],
        "max_leg_km": 20,
    },
}


# ═══════════════════════════════════════════════════════════════════
# LLM 评分函数
# ═══════════════════════════════════════════════════════════════════

_LLM_SCORE_RUBRIC = """你是路线规划评估专家。评估以下城市一日游路线的质量。

用户需求: {user_input}
场景类型: {scene_type}

【生成的路线】:
{route_text}

请评估这条路线，输出JSON:
{{
  "score": <0-100, 综合评分>,
  "grade": "<S/A/B/C/D/F>",
  "dims": {{
    "场景匹配": <0-100, 路线是否符合场景类型>,
    "逻辑合理": <0-100, 时间/距离/顺序是否合理>,
    "体验丰富": <0-100, 类型多样性/节奏感>,
    "POI质量": <0-100, 景点/餐厅评分和口碑>
  }},
  "good_points": ["优点1", "优点2"],
  "bad_points": ["问题1", "问题2"],
  "suggestion": "改进建议"
}}

评分标准:
- S(90+): 完美路线，逻辑自洽，体验丰富
- A(80-89): 优秀，有小瑕疵但整体很好
- B(70-79): 良好，基本合理但有改进空间
- C(60-69): 及格，能用但问题较多
- D(40-59): 较差，明显不合理
- F(<40): 失败，路线不可用

注意:
- 长隆等大型主题公园本身就是一天行程，1站是合理的
- "114.7分"之类的超100分是不可能的，满分100
- 美食型路线餐饮占比应>=40%
- 目的地型路线应围绕核心目的地展开"""


def _format_route_text(route_list: list[dict]) -> str:
    """格式化路线供 LLM 评估。"""
    lines = []
    for i, s in enumerate(route_list, 1):
        poi = s.get("poi", s)
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        arrive = s.get("arrival_time", "?")
        depart = s.get("departure_time", "?")
        rating = poi.get("rating", 0)
        lines.append(f"{i}. {name} [{cat}] 评分:{rating} 均价:¥{price} 到达:{arrive} 离开:{depart}")
    return "\n".join(lines) if lines else "(空路线)"


async def llm_score_route(
    user_input: str,
    scene_type: str,
    route_list: list[dict],
) -> dict | None:
    """LLM 评估路线质量。"""
    import httpx

    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "")

    if not api_key or not base_url or not model:
        return None

    url = f"{base_url.rstrip('/')}/chat/completions"
    prompt = _LLM_SCORE_RUBRIC.format(
        user_input=user_input,
        scene_type=scene_type,
        route_text=_format_route_text(route_list),
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
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                data = json.loads(text.strip())

                score = data.get("score", 0)
                grade = data.get("grade", "F")
                dims = data.get("dims", {})

                if not (0 <= score <= 100):
                    continue

                return {
                    "score": score,
                    "grade": grade,
                    "dims": dims,
                    "good_points": data.get("good_points", []),
                    "bad_points": data.get("bad_points", []),
                    "suggestion": data.get("suggestion", ""),
                    "source": "llm",
                }
        except Exception as e:
            if attempt < 1:
                await asyncio.sleep(2)
    return None

def _haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_route(route_list: list[dict], scene_type: str, proposals: list[dict]) -> dict:
    """多维评分，返回各维度分数 + 总分 + 评语。"""
    expect = _SCENE_EXPECT.get(scene_type, {})
    dims = {}
    notes = []

    if not route_list:
        return {"total": 0, "dims": {}, "grade": "F", "notes": ["路线为空"]}

    # 提取每个 stop 的信息
    stops_info = []
    for s in route_list:
        poi = s.get("poi", s)
        stops_info.append({
            "name": poi.get("name", "?"),
            "category": poi.get("category", ""),
            "lat": poi.get("lat", 0),
            "lng": poi.get("lng", 0),
            "rating": poi.get("rating", 0),
            "avg_price": poi.get("avg_price", 0),
            "tags": poi.get("tags", []),
            "arrival": s.get("arrival_time", ""),
            "departure": s.get("departure_time", ""),
            "travel_from_prev": s.get("travel_from_prev", {}),
        })

    n = len(stops_info)
    categories = [s["category"] for s in stops_info]
    cat_set = set(categories)

    # ── 1. 路线完整性 (0~100) ──
    min_s = expect.get("min_stops", 3)
    max_s = expect.get("max_stops", 10)
    if n < min_s:
        completeness = max(0, (n / min_s) * 100)
        notes.append(f"站数不足: {n} < {min_s}")
    elif n > max_s:
        completeness = max(50, 100 - (n - max_s) * 10)
        notes.append(f"站数偏多: {n} > {max_s}")
    else:
        completeness = 100
    dims["完整性"] = round(completeness, 1)

    # ── 2. 类别匹配 (0~100) ──
    must_cats = expect.get("must_categories", set())
    nice_cats = expect.get("nice_categories", set())
    forbidden = expect.get("forbidden_categories", set())

    # 必须类别（模糊匹配：category包含关键字即可）
    def _cat_hit(cat: str, target_set: set) -> bool:
        return any(t in cat or cat in t for t in target_set)

    must_hit = sum(1 for c in categories if _cat_hit(c, must_cats))
    cat_score = (must_hit / len(must_cats) * 70) if must_cats else 70

    # 加分类别
    nice_hit = sum(1 for c in categories if _cat_hit(c, nice_cats))
    cat_score += min(30, nice_hit * 15) if nice_cats else 30

    # 禁止类别惩罚
    forbid_hit = cat_set & forbidden
    if forbid_hit:
        cat_score -= len(forbid_hit) * 20
        notes.append(f"包含禁止类别: {forbid_hit}")

    # 美食型额外检查: 餐饮占比
    food_ratio_min = expect.get("food_ratio_min", 0)
    if food_ratio_min:
        food_count = sum(1 for c in categories if c in ("餐饮", "夜市小吃"))
        ratio = food_count / n if n else 0
        if ratio < food_ratio_min:
            cat_score -= (food_ratio_min - ratio) * 100 * 0.5
            notes.append(f"餐饮占比不足: {ratio:.0%} < {food_ratio_min:.0%}")

    dims["类别匹配"] = round(max(0, cat_score), 1)

    # ── 3. 地理连贯性 (0~100) ──
    max_leg = expect.get("max_leg_km", 20)
    legs = []
    for i, s in enumerate(stops_info):
        dist = s["travel_from_prev"].get("distance_m", 0) / 1000
        if dist > 0:
            legs.append(dist)
        elif i > 0 and s["lat"] and stops_info[i-1]["lat"]:
            dist = _haversine(stops_info[i-1]["lat"], stops_info[i-1]["lng"],
                              s["lat"], s["lng"])
            legs.append(dist)

    if legs:
        avg_leg = sum(legs) / len(legs)
        max_actual = max(legs)
        bad_legs = sum(1 for l in legs if l > max_leg)
        geo_score = 100
        if avg_leg > 15:
            geo_score -= (avg_leg - 15) * 5
        if bad_legs:
            geo_score -= bad_legs * 15
            notes.append(f"有{bad_legs}段距离>{max_leg}km")
        geo_score = max(0, min(100, geo_score))
    else:
        geo_score = 70  # 无距离数据给中等分

    dims["地理连贯"] = round(geo_score, 1)

    # ── 4. 时间可行性 (0~100) ──
    time_score = 100
    has_time = any(s["arrival"] for s in stops_info)
    if has_time and n >= 2:
        # 检查时间顺序递增
        times = []
        for s in stops_info:
            t = s["arrival"]
            if t and ":" in t:
                h, m = t.split(":")[:2]
                times.append(int(h) * 60 + int(m))
        if len(times) >= 2:
            # 时间应递增
            inversions = sum(1 for i in range(1, len(times)) if times[i] <= times[i-1])
            if inversions:
                time_score -= inversions * 20
                notes.append(f"时间顺序有{inversions}处倒退")
            # 总时长检查 (应在 4~14 小时)
            total_min = times[-1] - times[0]
            if total_min < 120:
                time_score -= 30
                notes.append(f"总行程过短: {total_min}分钟")
            elif total_min > 840:
                time_score -= 20
                notes.append(f"总行程过长: {total_min}分钟")
    else:
        # 1站或无时间数据：目的地型合理，其他给中等分
        time_score = 100 if (scene_type == "目的地型" and n == 1) else 60
        if time_score < 100:
            notes.append("无时间数据")

    dims["时间可行"] = round(max(0, time_score), 1)

    # ── 5. 多样性 (0~100) ──
    if n > 1:
        unique_cats = len(cat_set)
        diversity = min(100, unique_cats * 25)
        # 惩罚连续同类
        consec = 0
        max_consec = 0
        for i in range(1, n):
            if categories[i] == categories[i-1]:
                consec += 1
                max_consec = max(max_consec, consec)
            else:
                consec = 0
        if max_consec >= 3:
            diversity -= (max_consec - 2) * 10
            notes.append(f"连续{max_consec+1}站同类别")
    elif scene_type == "目的地型" and n == 1:
        # 目的地型单站合理（如长隆玩一天），不罚分
        diversity = 100
    else:
        diversity = 50

    dims["多样性"] = round(max(0, diversity), 1)

    # ── 6. POI 质量 (0~100) ──
    ratings = [s["rating"] for s in stops_info if s["rating"]]
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        quality = min(100, (avg_rating / 5.0) * 100)
        if avg_rating < 4.0:
            notes.append(f"平均评分偏低: {avg_rating:.1f}")
    else:
        quality = 50
        notes.append("无评分数据")

    dims["POI质量"] = round(quality, 1)

    # ── 总分 (加权) ──
    weights = {
        "完整性": 15,
        "类别匹配": 20,
        "地理连贯": 15,
        "时间可行": 10,
        "多样性": 15,
        "POI质量": 25,
    }
    total = sum(dims.get(k, 0) * w for k, w in weights.items()) / sum(weights.values())

    # 等级
    if total >= 90:
        grade = "S"
    elif total >= 80:
        grade = "A"
    elif total >= 70:
        grade = "B"
    elif total >= 60:
        grade = "C"
    elif total >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "total": round(total, 1),
        "dims": dims,
        "grade": grade,
        "notes": notes,
    }


# ═══════════════════════════════════════════════════════════════════
# 运行单个场景
# ═══════════════════════════════════════════════════════════════════

async def run_scene(scene_type: str, user_input: str) -> dict:
    """Run one scene through the full graph and return metrics."""
    from backend.agents_v3 import get_graph_c, TravelState

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
        return {"scene": scene_type, "input": user_input, "error": str(e),
                "elapsed": round(time.perf_counter() - t0, 1)}

    elapsed = time.perf_counter() - t0

    # ── 提取结果 ──
    route = result.get("route") or {}
    proposals = result.get("proposals", [])
    errors = result.get("errors", [])
    narrative = result.get("narrative") or {}
    active = result.get("active_experts", [])
    weights = result.get("expert_weights", {})

    # 路线列表
    route_list = route.get("route", [])
    stop_names = [s.get("poi", s).get("name", "?") for s in route_list] if route_list else []

    # 按agent统计提案
    agent_counts = {}
    for p in proposals:
        a = p.get("agent", "?")
        has_name = bool(p.get("content", {}).get("name"))
        key = f"{a}{'*' if has_name else ''}"
        agent_counts[key] = agent_counts.get(key, 0) + 1

    # 评分（LLM优先，规则降级）
    scoring = await llm_score_route(user_input, scene_type, route_list)
    if scoring is None:
        scoring = score_route(route_list, scene_type, proposals)
        scoring["source"] = "rule"
    else:
        # LLM评分结果，补上total和grade
        scoring["total"] = scoring.get("score", 0)
        scoring["notes"] = scoring.get("bad_points", [])

    return {
        "scene": scene_type,
        "input": user_input,
        "elapsed": round(elapsed, 1),
        "active_experts": active,
        "stops": stop_names,
        "stop_count": len(stop_names),
        "errors": errors,
        "route_ok": len(stop_names) >= 3,
        "total_proposals": len(proposals),
        "agent_counts": agent_counts,
        "score": scoring["total"],
        "grade": scoring["grade"],
        "source": scoring.get("source", "rule"),
        "dims": scoring["dims"],
        "score_notes": scoring["notes"],
        "narrative_preview": (narrative.get("description") or "")[:120],
    }


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

async def main():
    print("=" * 70)
    print("  五场景 E2E 验证 + 多维评分 — agents_v3")
    print("=" * 70)

    # 预加载
    print("\n[预热] 编译 LangGraph...")
    from backend.agents_v3 import get_graph_c
    get_graph_c()
    from backend.agents_v3.meituan_client import clear_cache
    clear_cache()
    print("[预热] 完成\n")

    # 全并发跑5场景
    print("\n  启动5场景并发...")
    tasks = [run_scene(st, ui) for st, ui in SCENES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理异常
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            results[i] = {"scene": SCENES[i][0], "input": SCENES[i][1],
                          "error": str(r)[:100], "score": 0, "grade": "F",
                          "stops": [], "stop_count": 0, "elapsed": 0,
                          "dims": {}, "score_notes": [], "route_ok": False}

    # 打印结果
    for r in results:
        print(f"\n{'━' * 70}")
        print(f"  {r.get('scene', '?')}  |  {r.get('input', '?')}")
        print(f"{'━' * 70}")

        if "error" in r and "route_ok" not in r:
            print(f"  ✗ 失败: {r['error']}")
            continue

        print(f"  耗时: {r['elapsed']}s | 激活专家: {', '.join(r.get('active_experts', []))}")
        print(f"  路线 ({r['stop_count']}站): {' → '.join(r.get('stops', []))}")

        src = r.get("source", "rule")
        print(f"\n  ┌─ 评分: {r['score']:5.1f} / 100  等级 {r['grade']}  [{src}] ─┐")
        for dim_name, dim_val in r.get("dims", {}).items():
            bar_len = int(dim_val / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  │ {dim_name:6s} {bar} {dim_val:5.1f}")
        for gp in r.get("good_points", []):
            print(f"  │ ✓ {gp}")
        for bp in r.get("bad_points", []):
            print(f"  │ ✗ {bp}")
        if r.get("suggestion"):
            print(f"  │ → {r['suggestion']}")
        for note in r.get("score_notes", []):
            print(f"  │ ※ {note}")
        print(f"  └{'─' * 38}┘")

        if r.get("errors"):
            print(f"  ⚠ 错误: {r['errors']}")

    # ══════════════════════════════════════════════════════════════
    # 总结
    # ══════════════════════════════════════════════════════════════
    print(f"\n\n{'═' * 70}")
    print(f"  总  结")
    print(f"{'═' * 70}")

    ok_count = sum(1 for r in results if r.get("route_ok"))
    avg_score = sum(r.get("score", 0) for r in results) / len(results)
    avg_time = sum(r.get("elapsed", 0) for r in results) / len(results)

    print(f"\n  路线生成: {ok_count}/{len(SCENES)}")
    print(f"  平均耗时: {avg_time:.1f}s")
    print(f"  平均评分: {avg_score:.1f}")

    # 每个场景一行
    print(f"\n  {'场景':8s} │ {'等级':3s} │ {'评分':5s} │ {'耗时':5s} │ {'站数':3s} │ 路线")
    print(f"  {'─'*8}─┼─{'─'*3}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*3}─┼─{'─'*30}")
    for r in results:
        if "route_ok" not in r:
            print(f"  {r['scene']:8s} │ F   │ {'0.0':5s} │ {r.get('elapsed','?'):>5}s │  -  │ (执行失败)")
            continue
        status = "✓" if r["route_ok"] else "✗"
        route_short = " → ".join(r["stops"][:5])
        if len(r["stops"]) > 5:
            route_short += "..."
        print(f"  {r['scene']:8s} │ {r['grade']:3s} │ {r['score']:5.1f} │ {r['elapsed']:>4.0f}s │ {r['stop_count']:>3} │ {route_short}")

    # 等级统计
    grades = [r.get("grade", "F") for r in results if "route_ok" in r]
    grade_order = "SABCDF"
    grade_summary = {g: grades.count(g) for g in grade_order if grades.count(g) > 0}
    grade_str = "  ".join(f"{g}:{n}" for g, n in grade_summary.items())

    print(f"\n  等级分布: {grade_str}")

    fail = sum(1 for r in results if not r.get("route_ok"))
    all_pass = fail == 0 and avg_score >= 60

    if all_pass:
        print(f"\n  ✓ 全部 {len(SCENES)} 场景通过，平均 {avg_score:.1f} 分")
    else:
        print(f"\n  ⚠ {fail} 个场景失败" + (f"，平均 {avg_score:.1f} 分偏低" if avg_score < 60 else ""))

    return all_pass


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
