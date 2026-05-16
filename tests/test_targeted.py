"""针对性测试：只跑之前路线有问题的11个场景。"""
from __future__ import annotations
import asyncio, json, sys, time, os
from datetime import datetime
from pathlib import Path

import httpx
os.environ.setdefault("LLM_API_KEY", os.getenv("LLM_API_KEY", ""))
os.environ.setdefault("LLM_BASE_URL", "https://api.deepseek.com")
os.environ.setdefault("LLM_MODEL", "deepseek-chat")

from backend.agents_v3 import get_graph_c, TravelState
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

# 之前路线有问题的场景 + 评分找茬的场景
SCENARIOS = [
    # test_output15 中失败的14个场景
    {"id": 5, "name":"情侣穷游",    "input":"4个人珠海玩一天，每人预算100"},
    {"id": 7, "name":"亲子科普",    "input":"珠海亲子游，孩子喜欢动物和科学"},
    {"id": 9, "name":"二胎家庭",    "input":"一家四口珠海，两岁和八岁，预算600"},
    {"id":11, "name":"朋友聚餐",    "input":"5个朋友珠海聚餐，吃吃喝喝"},
    {"id":12, "name":"兄弟特种兵",  "input":"兄弟几个珠海特种兵一天，打卡所有景点"},
    {"id":13, "name":"闺蜜逛街",    "input":"和闺蜜珠海逛街，想拍照+吃甜品"},
    {"id":14, "name":"朋友穷游",    "input":"4个大学生珠海穷游，不花钱"},
    {"id":16, "name":"社恐独居",    "input":"社恐一个人珠海，安静地方"},
    {"id":20, "name":"文艺独处",    "input":"一个人珠海文艺独处，咖啡馆书店"},
    {"id":21, "name":"海鲜大餐",    "input":"珠海吃海鲜，想吃最新鲜最划算的"},
    {"id":22, "name":"美食探索",    "input":"珠海美食一日游，想吃海鲜和本地特色"},
    {"id":24, "name":"茶餐厅打卡",  "input":"珠海茶餐厅打卡"},
    {"id":27, "name":"雨天方案",    "input":"下雨天珠海，室内活动"},
    {"id":30, "name":"模糊需求",    "input":"珠海有啥好玩的"},
]

SCORE_PROMPT = """你是旅游路线质量评审。请站在**用户实际体验**角度评估路线。

核心原则：路线好不好，取决于**是否满足用户需求**，而不是路线本身有多花哨。
- 用户想去海边，全安排海边就对了，不需要强行加博物馆凑多样性
- 带孩子不想跑远，3个POI就很好，不需要塞满8个
- 吃饭选一家好的，比选3家来回跑更合理
- 预算有限走免费景点，就是好匹配
- 用户想拍照+吃甜品，选了甜品店+拍照点就是好匹配
- 用户想吃5顿，安排了5顿餐饮就是好匹配
- 团建15人，选了团队互动项目就是好匹配

评分标准(每项0-10分):

**intent_match** (意图匹配) — 最重要:
用户真正想要什么？路线给了没有？
- 9-10: 用户核心需求全部满足
- 7-8: 核心需求满足，小细节有偏差
- 5-6: 部分满足，但方向对
- 3-4: 方向偏差
- 0-2: 完全不搭

**poi_quality** (POI质量):
POI本身值不值得去？不需要数量多，质量好就行。
- 9-10: 选的都是好地方
- 7-8: 大部分不错
- 5-6: 一般般
- 3-4: 多数不值得
- 0-2: 垃圾POI

**geo_continuity** (地理合理性):
路线顺不顺？有没有来回跑？考虑用户群体特征：
- 带孩子/老人：距离近就是好，不需要跨区
- 特种兵：跨区赶场是正常的
- 美食探索：餐厅分散也OK，吃本身就是目的
- 9-10: 路线顺畅 | 7-8: 基本合理 | 5-6: 有点绕但能接受 | 3-4: 不合理 | 0-2: 乱排

**rhythm** (节奏合理性):
时间和节奏安排是否舒服？
- 景点数量匹配用户节奏（闲逛3-4个OK，特种兵7-8个OK）
- 吃饭时间合理（午餐11-13点，晚餐17-19点）
- 没有赶场感（除非用户要赶场）
- 9-10: 节奏完美 | 7-8: 舒服 | 5-6: 稍紧/松 | 3-4: 节奏混乱 | 0-2: 完全不合理

**overall** (总体):
综合以上，你作为真实用户会满意吗？
- 3个POI+1家餐厅的亲子路线，如果POI质量好+距离近+节奏合适 → 7-8分
- 纯海边路线，如果用户想看海 → 8-9分
- 不要因为"还可以加更多"就扣分

输出JSON:
{"scene_type":"美食型/目的地型/特种兵型/休闲型/观光型",
 "scores":{"intent_match":N,"poi_quality":N,"geo_continuity":N,"rhythm":N,"overall":N},
 "good_points":["具体优点1","具体优点2"],
 "bad_points":["具体问题1","具体问题2"]}

重要：优点和缺点都要具体到POI名字，不要说空话。"""


async def llm_score(user_input: str, route_text: str) -> dict | None:
    prompt = SCORE_PROMPT + f"\n\n用户需求: {user_input}\n\n路线:\n{route_text}"
    for _ in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(API_URL,
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={"model": MODEL, "max_tokens": 2000,
                          "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0.1, "response_format": {"type": "json_object"}})
                if r.status_code != 200:
                    continue
                text = r.json()["choices"][0]["message"]["content"].strip()
                data = json.loads(text)
                scores = data.get("scores", data)
                for v in scores.values():
                    if not isinstance(v, (int, float)) or v < 0 or v > 10:
                        return None
                return {"scores": scores, "overall": scores.get("overall", 0),
                        "good_points": data.get("good_points", []),
                        "bad_points": data.get("bad_points", []),
                        "scene_type": data.get("scene_type", "")}
        except Exception:
            await asyncio.sleep(2)
    return None


def fmt_route(steps: list[dict]) -> str:
    lines = []
    for i, s in enumerate(steps, 1):
        poi = s.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        arrive = s.get("arrival_time", "?")
        depart = s.get("departure_time", "?")
        t = s.get("_type", "")
        label = f"({t})" if t else ""
        lines.append(f"{i}. {name} [{cat}] ¥{price} {arrive}-{depart} {label}")
    return "\n".join(lines)


async def run_one(sc: dict) -> dict:
    graph = get_graph_c()
    t0 = time.time()
    try:
        result = await asyncio.wait_for(graph.ainvoke({"user_input": sc["input"]}), timeout=180)
        elapsed = time.time() - t0

        route = result.get("route", {})
        steps = route.get("route", []) if route else []
        scene_type = result.get("scene_type", "?")
        errors = result.get("errors", [])

        route_text = fmt_route(steps) if steps else ""
        eval_result = None
        if route_text:
            eval_result = await llm_score(sc["input"], route_text)

        return {
            "id": sc["id"], "name": sc["name"], "input": sc["input"],
            "success": True, "elapsed": round(elapsed, 1),
            "scene_type": scene_type,
            "route_steps": len(steps),
            "poi_names": [s.get("poi", {}).get("name", "?") for s in steps],
            "poi_cats": [(s.get("poi", {}).get("name", "?"), s.get("poi", {}).get("category", "?")) for s in steps],
            "route_text": route_text,
            "errors": errors,
            "eval": eval_result,
        }
    except asyncio.TimeoutError:
        return {"id": sc["id"], "name": sc["name"], "success": False, "error": "超时180s"}
    except Exception as e:
        return {"id": sc["id"], "name": sc["name"], "success": False, "error": str(e)}


async def main():
    import subprocess, requests
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.meituan_server.main:app",
         "--host", "127.0.0.1", "--port", "8001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        try:
            requests.get("http://127.0.0.1:8001/api/area/boundaries", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("美团模拟服务器启动失败")
        server.kill()
        return

    print("=" * 60)
    print(f"针对性测试 — {len(SCENARIOS)}场景（POI选错修复验证）")
    print("=" * 60)

    from backend.agents_v3.meituan_client import clear_cache
    results = []
    for sc in SCENARIOS:
        clear_cache()
        r = await run_one(sc)
        results.append(r)

        if r["success"]:
            ev = r.get("eval")
            names = " → ".join(r["poi_names"][:6])
            passed = ev and ev["overall"] >= 6.5
            icon = "✅" if passed else "❌"
            print(f"\n{icon} [{r['id']:02d}] {r['name']} ({r['elapsed']}s, {r['route_steps']}站, {r['scene_type']})")
            print(f"   路线: {names}")
            # 显示POI类别
            for name, cat in r.get("poi_cats", []):
                print(f"     - {name} [{cat}]")
            if ev:
                s = ev["scores"]
                print(f"   评分: intent={s.get('intent_match','?')} poi={s.get('poi_quality','?')} "
                      f"geo={s.get('geo_continuity','?')} rhythm={s.get('rhythm','?')} "
                      f"overall={ev['overall']}")
                for gp in ev.get("good_points", [])[:2]:
                    print(f"   👍 {gp}")
                for bp in ev.get("bad_points", []):
                    print(f"   ⚠️ {bp}")
            else:
                print("   ⚠ 评分失败")
            if r.get("errors"):
                for e in r["errors"][:2]:
                    print(f"   🔧 {e}")
        else:
            print(f"\n❌ [{r['id']:02d}] {r['name']} - {r.get('error','?')}")

    # 汇总
    successes = [r for r in results if r["success"]]
    scored = [r for r in successes if r.get("eval")]
    passed = [r for r in scored if r["eval"]["overall"] >= 6.5]

    print(f"\n{'='*60}")
    print(f"📊 汇总: {len(passed)}/{len(scored)} 通过(≥6.5)")
    if scored:
        avg = sum(r["eval"]["overall"] for r in scored) / len(scored)
        print(f"   平均分: {avg:.1f}/10")

    server.terminate()
    server.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
