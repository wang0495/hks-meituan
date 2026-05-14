"""诊断脚本：看expert proposals和synthesizer输入输出，定位问题在哪个环节。"""

import asyncio
import json
import time

from dotenv import load_dotenv
load_dotenv()

from backend.agents_v3.meituan_client import fetch_pois, clear_cache
from backend.agents_v3.nodes.rule_guard import rule_guard
from backend.agents_v3.nodes.expert_router import expert_router
from backend.agents_v3.experts.poi_expert import poi_expert
from backend.agents_v3.experts.food_expert import food_expert

CASES = [
    ("05", "4个人珠海玩一天，每人预算100"),
    ("11", "5个朋友珠海聚餐，吃吃喝喝"),
]


async def diagnose(case_id: str, user_input: str):
    print(f"\n{'='*60}")
    print(f"[{case_id}] {user_input}")
    print(f"{'='*60}")

    # 1. rule_guard
    state = {"user_input": user_input, "messages": []}
    r1 = await rule_guard(state)
    state.update(r1)
    print(f"\n--- rule_guard ---")
    print(f"  candidates: {len(state.get('candidates', []))}")
    intent = state.get("user_intent", {})
    print(f"  prefs: {intent.get('preferred_categories', [])}")
    print(f"  budget: {intent.get('budget', {})}")

    # 2. expert_router
    r2 = await expert_router(state)
    state.update(r2)
    print(f"\n--- expert_router ---")
    print(f"  scene_type: {state.get('scene_type')}")
    weights = state.get("expert_weights", {})
    print(f"  weights: {json.dumps({k: round(v, 2) for k, v in weights.items() if v >= 0.3}, ensure_ascii=False)}")
    active = state.get("active_experts", [])
    print(f"  active: {active}")
    pools = state.get("expert_candidates", {})
    for k, v in pools.items():
        if v:
            print(f"  pool[{k}]: {len(v)} items")

    # 3. poi_expert
    if "poi" in active:
        r3 = await poi_expert(state)
        poi_props = r3.get("proposals", [])
        print(f"\n--- poi_expert (weight={weights.get('poi', 0):.2f}) ---")
        print(f"  proposals: {len(poi_props)}")
        for p in poi_props:
            c = p.get("content", {})
            print(f"    {c.get('name', '?')} [{c.get('category', '?')}] "
                  f"lat={c.get('lat', '?')} lng={c.get('lng', '?')} "
                  f"conf={p.get('confidence', '?')}")

    # 4. food_expert
    if "food" in active:
        r4 = await food_expert(state)
        food_props = r4.get("proposals", [])
        print(f"\n--- food_expert (weight={weights.get('food', 0):.02f}) ---")
        print(f"  proposals: {len(food_props)}")
        for p in food_props:
            c = p.get("content", {})
            print(f"    {c.get('name', '?')} [{c.get('category', '?')}] "
                  f"price={c.get('avg_price', '?')} conf={p.get('confidence', '?')}")


async def main():
    for cid, inp in CASES:
        clear_cache()
        await diagnose(cid, inp)


if __name__ == "__main__":
    asyncio.run(main())
