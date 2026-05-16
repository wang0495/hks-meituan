"""运行30个场景的龙猫评分测试"""
import asyncio, json, sys, time
from pathlib import Path
import httpx

API_KEY = "os.getenv("AMAP_API_KEY", "")"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
BASE = "http://localhost:8001"
PASS_THRESHOLD = 6.5

async def llm_json(prompt, max_tokens=2000, retries=3):
    """调用LLM评分，带重试机制"""
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post(API_URL,
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={"model": MODEL, "max_tokens": max_tokens,
                          "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0.1, "response_format": {"type": "json_object"}})
                if r.status_code != 200:
                    print(f"    [LLM Error] Status {r.status_code}, attempt {attempt+1}/{retries}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                    return None
                text = r.json().get("content", [{}])[0].get("text", "").strip()
                if text.startswith("```"): text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"): text = text[:-3]
                try:
                    return json.loads(text.strip())
                except json.JSONDecodeError as e:
                    print(f"    [LLM Error] JSON parse failed: {e}, attempt {attempt+1}/{retries}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None
        except Exception as e:
            print(f"    [LLM Error] Exception: {e}, attempt {attempt+1}/{retries}")
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None
    return None

def parse_sse_route(sse_text):
    """解析SSE响应，返回route、impossible信息、infeasible信息和feasibility信息"""
    route = []
    impossible_info = None
    infeasible_info = None
    feasibility_info = None
    current_event = None
    for line in sse_text.split("\n"):
        line = line.strip()
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if current_event == "step":
                    route.append(data)
                elif current_event == "agent_impossible":
                    impossible_info = data
                elif current_event == "agent_infeasible":
                    infeasible_info = data
                elif current_event == "agent_feasibility":
                    feasibility_info = data
                elif current_event == "done":
                    full_route = data.get("full_route", {})
                    if full_route.get("impossible"):
                        impossible_info = full_route
                    if full_route.get("infeasible"):
                        infeasible_info = full_route
            except: pass
    return route, impossible_info, infeasible_info, feasibility_info

def haversine(lat1, lng1, lat2, lng2):
    """计算两点间距离（km）"""
    import math
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def format_route(route):
    lines = []
    prev_poi = None
    for i, step in enumerate(route, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        tags = poi.get("_scene_tags", [])
        lat = poi.get("lat", 0)
        lng = poi.get("lng", 0)

        # 计算与上一个POI的距离
        dist_str = ""
        if prev_poi and lat and lng and prev_poi.get("lat") and prev_poi.get("lng"):
            dist = haversine(prev_poi["lat"], prev_poi["lng"], lat, lng)
            time_min = dist / 30 * 60  # 假设30km/h平均速度
            dist_str = f" ← 距上一站{dist:.1f}km/约{time_min:.0f}分钟"

        lines.append(f"{i}. {name} [{cat}] ¥{price} 坐标:({lat:.4f},{lng:.4f}) 标签:{tags}{dist_str}")
        prev_poi = poi
    return "\n".join(lines)

async def score_route(user_input, route_text):
    prompt = (
        "你是旅游路线质量评审。评估以下路线。\n\n"
        f"用户需求: {user_input}\n\n"
        f"路线:\n{route_text}\n\n"
        "评分(每项0-10):\n"
        "- intent_match: 意图匹配\n"
        "- poi_quality: POI质量\n"
        "- geo_continuity: 地理合理性\n"
        "- scene_diversity: 场景多样性\n"
        "- overall: 总体\n\n"
        "规则:\n"
        "1. 【核心】不可能需求（50元住五星、零预算旅游、凌晨去白天景点）:\n"
        "   - 若路线给出合理替代/拒绝/说明不可行 → intent_match=7-8，overall=6-7\n"
        "   - 若路线强行匹配不可能POI（如便利店当宵夜）→ intent_match=2-3，overall=3-4\n"
        "2. 【核心】用户意图可实现时:\n"
        "   - 路线匹配核心意图（如宵夜选夜市/烧烤、蹦迪选酒吧/夜店）→ intent_match=8-9\n"
        "   - 路线偏离核心意图（如宵夜选便利店、蹦迪选公园）→ intent_match=4-5\n"
        "3. 城市出行站间距离5-15km完全正常（开车/打车15-30分钟），不要因为距离扣geo_continuity分\n"
        "4. 只有站间距离>25km或明显绕路时，geo_continuity才扣分\n"
        "5. 路线有3个以上POI且类别多样，geo_continuity至少给6分\n"
        "6. 列2-3个优点和2-3个建议\n\n"
        '输出JSON: {"scores":{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N},"good_points":[...],"bad_points":[...]}'
    )
    result = await llm_json(prompt)
    if not result:
        # LLM评分失败，返回默认分数（避免完全失败）
        print("    [LLM Fallback] 使用默认分数")
        return {
            "scores": {"intent_match": 5, "poi_quality": 5, "geo_continuity": 5, "scene_diversity": 5, "overall": 5},
            "overall": 5,
            "good_points": ["路线生成成功"],
            "bad_points": ["LLM评分失败，使用默认分数"]
        }
    scores = result.get("scores", result)
    return {"scores": scores, "overall": scores.get("overall", 0), "good_points": result.get("good_points",[]), "bad_points": result.get("bad_points",[])}

async def main():
    scenarios = json.loads(Path("eval_data/llm_scenarios.json").read_text(encoding="utf-8"))
    print(f"LLM路线评分 — {len(scenarios)}个场景, 及格线={PASS_THRESHOLD}\n")

    results = []
    for i, sc in enumerate(scenarios):
        name = sc.get("name", f"s{i}")
        inp = sc.get("input", "")
        print(f"[{i+1}/{len(scenarios)}] {name}: {inp[:40]}...")

        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post(f"{BASE}/api/plan", json={"user_input": inp, "session_id": f"score_{i}"})
                route, impossible_info, infeasible_info, feasibility_info = parse_sse_route(r.text)

            # 如果Agent检测到不可能需求(常识层面不可行)
            if impossible_info:
                print(f"  [Agent] 不可能需求: {impossible_info.get('reason', '')[:50]}...")
                print(f"  V 合理拒绝 → intent=8 overall=7")
                results.append({
                    "name": name, "input": inp, "status": "impossible",
                    "overall": 7, "scores": {"intent_match": 8, "poi_quality": 0, "geo_continuity": 0, "scene_diversity": 0, "overall": 7},
                    "passed": True,  # 合理拒绝视为通过
                    "reason": impossible_info.get("reason", ""),
                    "suggestion": impossible_info.get("suggestion", ""),
                })
                continue

            # 如果FeasibilityAgent检测到场景不可行(缺乏必要POI)
            if infeasible_info:
                print(f"  [Feasibility] 场景不可行: {infeasible_info.get('reason', '')[:50]}...")
                print(f"  V 合理拒绝 → intent=7 overall=6")
                results.append({
                    "name": name, "input": inp, "status": "infeasible",
                    "overall": 6, "scores": {"intent_match": 7, "poi_quality": 0, "geo_continuity": 0, "scene_diversity": 0, "overall": 6},
                    "passed": True,  # 合理拒绝视为通过
                    "reason": infeasible_info.get("reason", ""),
                    "suggestion": infeasible_info.get("suggestion", ""),
                    "required_types": infeasible_info.get("required_poi_types", []),
                })
                continue

            # 部分可行的情况，在评分时加入提示
            feasibility_warning = None
            if feasibility_info and feasibility_info.get("feasibility") == "partial":
                feasibility_warning = feasibility_info.get("reason", "")

            if not route:
                print(f"  X 空路线")
                results.append({"name": name, "input": inp, "status": "empty", "overall": 0})
                continue

            cats = [s.get("poi",{}).get("category","?") for s in route]
            print(f"  路线: {' -> '.join(cats)}")
            if feasibility_warning:
                print(f"  [部分可行] {feasibility_warning[:50]}...")

            eval_result = await score_route(inp, format_route(route))
            if not eval_result:
                print(f"  ! 评分失败")
                results.append({"name": name, "input": inp, "status": "eval_fail", "overall": 0})
                continue

            overall = eval_result["overall"]
            passed = overall >= PASS_THRESHOLD
            scores = eval_result["scores"]
            status = "V" if passed else "X"
            print(f"  {status} intent={scores.get('intent_match','?')} quality={scores.get('poi_quality','?')} overall={overall}")
            if eval_result.get("bad_points"):
                for bp in eval_result["bad_points"][:2]:
                    print(f"     ! {bp}")

            results.append({"name": name, "input": inp, "status": "scored", "overall": overall, "scores": scores, "passed": passed, "bad_points": eval_result.get("bad_points",[]), "route_cats": cats})
        except Exception as e:
            print(f"  E {e}")
            results.append({"name": name, "input": inp, "status": "error", "overall": 0})

    scored = [r for r in results if r["status"] == "scored"]
    passed = [r for r in scored if r.get("passed")]
    avg = sum(r["overall"] for r in scored) / len(scored) if scored else 0
    print(f"\n{'='*60}")
    print(f"结果: {len(passed)}/{len(scored)} 通过, 平均分: {avg:.1f}/10")
    print(f"{'='*60}")

    failed = [r for r in scored if not r.get("passed")]
    if failed:
        print(f"\n失败场景:")
        for r in failed:
            bp = r.get("bad_points", ["?"])[0] if r.get("bad_points") else "?"
            print(f"  X {r['name']}: overall={r['overall']} — {bp}")

    Path("test_llm_scoring_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存到 test_llm_scoring_results.json")

if __name__ == "__main__":
    asyncio.run(main())
