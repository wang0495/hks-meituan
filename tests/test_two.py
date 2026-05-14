"""单独测试 #05 和 #11 两个场景。"""

import asyncio, json, os, sys, time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
load_dotenv()

from backend.agents_v3 import get_graph_c
from backend.agents_v3.meituan_client import clear_cache

API_KEY = os.getenv("LLM_API_KEY")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

CASES = [
    {"id": 5, "name": "情侣穷游", "input": "4个人珠海玩一天，每人预算100"},
    {"id": 11, "name": "朋友聚餐", "input": "5个朋友珠海聚餐，吃吃喝喝"},
]

async def llm_score(user_input: str, route_text: str) -> dict:
    prompt = f"""评估以下旅行路线质量。用户需求: {user_input}\n\n路线:\n{route_text}\n\n输出JSON: {{"intent":N,"poi":N,"geo":N,"rhythm":N,"overall":N,"good":["优点"],"bad":["问题"]}}"""
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post(API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "max_tokens": 1000,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "response_format": {"type": "json_object"}})
        return json.loads(r.json()["choices"][0]["message"]["content"])

def fmt_route(steps):
    lines = []
    for i, s in enumerate(steps, 1):
        poi = s.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        arrive = s.get("arrival_time", "?")
        depart = s.get("departure_time", "?")
        t = s.get("_type", "")
        lines.append(f"{i}. {name} [{cat}] {arrive}-{depart} {f'({t})' if t else ''}")
    return "\n".join(lines)

async def run_one(sc):
    graph = get_graph_c()
    clear_cache()
    t0 = time.time()
    result = await asyncio.wait_for(graph.ainvoke({"user_input": sc["input"]}), timeout=180)
    elapsed = time.time() - t0

    route = result.get("route", {})
    steps = route.get("route", []) if route else []
    scene = result.get("scene_type", "?")

    names = [s.get("poi", {}).get("name", "?") for s in steps]
    cats = [(s.get("poi", {}).get("name", "?"), s.get("poi", {}).get("category", "?")) for s in steps]

    route_text = fmt_route(steps)
    scores = await llm_score(sc["input"], route_text)
    overall = scores.get("overall", 0)
    mark = "✅" if overall >= 6.5 else "❌"

    print(f"\n{mark} [{sc['id']:02d}] {sc['name']} ({elapsed:.0f}s, {len(steps)}站, {scene})")
    print(f"   路线: {' → '.join(names)}")
    for name, cat in cats:
        print(f"     - {name} [{cat}]")
    print(f"   评分: intent={scores.get('intent')} poi={scores.get('poi')} "
          f"geo={scores.get('geo')} rhythm={scores.get('rhythm')} overall={overall}")
    for g in scores.get("good", [])[:2]:
        print(f"   👍 {g}")
    for b in scores.get("bad", []):
        print(f"   ⚠️ {b}")

    # 额外诊断：看proposals
    proposals = result.get("proposals", [])
    reworked = result.get("reworked_proposals", [])
    all_props = reworked or proposals
    print(f"\n   --- 诊断 ---")
    print(f"   proposals总数: {len(all_props)}")
    for p in all_props:
        c = p.get("content", {})
        print(f"     agent={p.get('agent','?')} | {c.get('name','?')} [{c.get('category','?')}]")

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

    print("=" * 60)
    print("单独测试 #05 情侣穷游 + #11 朋友聚餐")
    print("=" * 60)

    for sc in CASES:
        await run_one(sc)

    server.terminate()
    server.wait(timeout=5)

if __name__ == "__main__":
    asyncio.run(main())
