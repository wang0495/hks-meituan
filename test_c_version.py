"""C版本测试：5场景LLM评分。"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime

import httpx

sys.path.insert(0, "backend")

from backend.agents_v3 import get_graph_c, TravelState

# ── LLM评分配置 ──
API_KEY = "sk-1aad8fc6f2bb4614be106bcdb747478f"
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
PASS_THRESHOLD = 6.5


TEST_SCENARIOS = [
    {"id": 1, "name": "情侣珠海一日游", "input": "情侣珠海一日游，预算500元，喜欢拍照打卡"},
    {"id": 2, "name": "亲子海洋王国", "input": "带6岁孩子去长隆海洋王国，预算1000元"},
    {"id": 3, "name": "美食探索", "input": "珠海美食一日游，想吃海鲜和本地特色"},
    {"id": 4, "name": "特种兵打卡", "input": "一天打卡珠海所有著名景点，时间紧"},
    {"id": 5, "name": "休闲养老游", "input": "珠海两日游，节奏慢，喜欢公园和海边"},
]


async def llm_score(user_input: str, route_text: str) -> dict | None:
    """用龙猫给路线打分（与test_llm_scoring.py相同逻辑）。"""
    prompt = f"""你是旅游路线质量评审。请客观公正地评估以下路线。

用户需求: {user_input}

路线:
{route_text}

## 第一步：识别场景类型

先判断这个需求属于哪种特殊场景：
- **目的地型**：用户指定了具体大景区（如"长隆海洋王国""圆明新园"），会在该景区停留大半天甚至全天
- **特种兵型**：用户要求密集打卡，跨区域赶场是正常行为
- **主题探索型**：围绕某个主题（美食、拍照、文化等）探索
- **休闲慢游型**：节奏慢、少景点、重体验
- **常规型**：以上都不是

## 第二步：按场景类型调整评分标准

评分标准(每项0-10分):

**intent_match** (意图匹配):
- 目的地型场景：只要包含了用户指定的核心目的地，即算高分（7-9）。POI数量少不代表匹配差
- 特种兵型场景：不可能"一天打卡所有景点"是正常的，只要覆盖了重要景点就给7-8
- 其他：按通用标准
  - 9-10: 完美匹配  |  7-8: 大部分匹配  |  5-6: 部分匹配  |  3-4: 低匹配  |  0-2: 不相关

**poi_quality** (POI质量):
- 按POI本身质量评分，不因数量少而扣分。3个优质POI > 8个平庸POI
- 9-10: 都是值得专程去的  |  7-8: 大部分不错  |  5-6: 一般  |  3-4: 偏低  |  0-2: 不值得

**geo_continuity** (地理合理性):
- 目的地型场景：POI集中在同一区域是优点（如都在长隆片区），给8-9
- 特种兵型场景：跨区域赶场是预期行为，不要因为跨度大就扣分。看单段是否折返即可
- 其他：看路线是否有不必要的折返
  - 9-10: 流畅  |  7-8: 基本合理  |  5-6: 有绕路  |  3-4: 不合理  |  0-2: 混乱

**scene_diversity** (场景多样性):
- 目的地型场景：多样性不是重点，主题一致性更重要（给7-8）
- 特种兵型场景：覆盖多种类型景点加分（自然+文化+娱乐+地标，每多一类+1）
- 美食/主题型场景：全选同类POI不算扣分！只要子类型多样就给高分。如美食主题下，海鲜+茶餐厅+小吃+甜品就是满分多样性，不需要强行加景点。穿插1个散步景点是加分项但不是必须
- 通用标准：
  - 9-10: 子类型丰富多样（主题场景）或涵盖4种以上大类（综合场景）
  - 7-8: 子类型较丰富，或涵盖3种大类
  - 5-6: 有一定多样性但不够丰富
  - 3-4: 同质化严重（如5个景点全是公园，或5个餐厅全是海鲜排档）
  - 0-2: 完全没有多样性

**overall** (总体): 综合以上维度和场景类型，给出你的真实满意度评分。

## 评分底线规则
1. 3个以上POI且时间合理 → geo_continuity ≥ 6
2. 包含了用户明确提到的核心目的地 → intent_match ≥ 7
3. 路线没有明显错误（如重复POI、深夜安排儿童活动等） → overall ≥ 6
4. 不要因为"还可以更好"就给低分，6分代表"及格"，7分代表"不错"，8分代表"很好"
5. 列出2-3个优点(good_points)和2-3个改进建议(bad_points)，不要只挑毛病

输出JSON: {{"scene_type":"目的地型/特种兵型/主题探索型/休闲慢游型/常规型","scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["优点1","优点2"],"bad_points":["建议1","建议2"]}}"""

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": MODEL,
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
                if r.status_code != 200:
                    continue
                # OpenAI格式响应
                text = r.json()["choices"][0]["message"]["content"].strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                data = json.loads(text.strip())

                # 兼容两种格式
                if "scores" in data:
                    scores = data["scores"]
                else:
                    keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
                    scores = {k: data[k] for k in keys if k in data}

                # 验证
                for v in scores.values():
                    if not isinstance(v, (int, float)) or v < 0 or v > 10:
                        return None
                vals = list(scores.values())
                if len(set(vals)) == 1 and len(vals) > 1:
                    return None

                return {
                    "scores": scores,
                    "overall": scores.get("overall", 0),
                    "good_points": data.get("good_points", []),
                    "bad_points": data.get("bad_points", []),
                }
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2)
    return None


def format_route(route_steps: list[dict]) -> str:
    """格式化路线供LLM评估。"""
    lines = []
    for i, step in enumerate(route_steps, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        tags = poi.get("_scene_tags", [])
        arrive = step.get("arrival_time", "?")
        lines.append(f"{i}. {name} [{cat}] ¥{price} 到达:{arrive} 标签:{tags}")
    return "\n".join(lines)


async def run_test(scenario: dict) -> dict:
    """运行单场景。"""
    graph = get_graph_c()

    initial: TravelState = {
        "user_input": scenario["input"],
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
    }

    try:
        t0 = time.time()
        result = await asyncio.wait_for(graph.ainvoke(initial), timeout=120)
        elapsed = time.time() - t0

        route = result.get("route", {})
        narrative = result.get("narrative", {})
        steps = route.get("route", []) if route else []
        proposals = result.get("proposals", [])
        conflicts = result.get("conflicts", [])

        # LLM评分
        route_text = format_route(steps) if steps else ""
        eval_result = None
        if route_text:
            eval_result = await llm_score(scenario["input"], route_text)

        return {
            "id": scenario["id"],
            "name": scenario["name"],
            "success": True,
            "elapsed": round(elapsed, 3),
            "route_steps": len(steps),
            "proposals": len(proposals),
            "conflicts": len(conflicts),
            "has_narrative": narrative is not None,
            "poi_names": [s.get("poi", {}).get("name", "?") for s in steps[:6]],
            "errors": result.get("errors", []),
            "eval": eval_result,
        }

    except asyncio.TimeoutError:
        return {"id": scenario["id"], "name": scenario["name"], "success": False, "error": "超时"}
    except Exception as e:
        return {"id": scenario["id"], "name": scenario["name"], "success": False, "error": str(e)}


async def main():
    # ── 启动美团模拟服务器 ──
    import subprocess
    import requests

    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.meituan_server.main:app",
         "--host", "127.0.0.1", "--port", "8001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # 等服务器就绪
    for _ in range(20):
        try:
            requests.get("http://127.0.0.1:8001/api/area/boundaries", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("❌ 美团模拟服务器启动失败")
        server_proc.kill()
        return

    print("=" * 60)
    print("C版本LLM评分测试：分布式智能体网络（美团API数据源）")
    print(f"评分模型: {MODEL} | 及格线: {PASS_THRESHOLD}")
    print("=" * 60)

    # 每个场景切换时清缓存
    from backend.agents_v3.meituan_client import clear_cache

    results = []
    for sc in TEST_SCENARIOS:
        clear_cache()
        r = await run_test(sc)
        results.append(r)

        if r["success"]:
            ev = r.get("eval")
            poi_str = " → ".join(r["poi_names"][:5])
            print(f"\n{'✅' if ev and ev['overall'] >= PASS_THRESHOLD else '❌'} 场景{r['id']}: {r['name']}")
            print(f"   路线: {poi_str}")
            print(f"   步骤:{r['route_steps']} 提案:{r['proposals']} 冲突:{r['conflicts']} ({r['elapsed']}s)")
            if ev:
                s = ev["scores"]
                print(f"   评分: intent={s.get('intent_match','?')} poi={s.get('poi_quality','?')} "
                      f"geo={s.get('geo_continuity','?')} diverse={s.get('scene_diversity','?')} "
                      f"overall={ev['overall']}")
                for bp in ev.get("bad_points", [])[:2]:
                    print(f"   ⚠ {bp}")
            else:
                print(f"   ⚠ LLM评分失败")
        else:
            print(f"\n❌ 场景{r['id']}: {r['name']} - {r.get('error', '?')}")

    # 汇总
    print("\n" + "=" * 60)
    successes = [r for r in results if r["success"]]
    scored = [r for r in successes if r.get("eval")]
    passed = [r for r in scored if r["eval"]["overall"] >= PASS_THRESHOLD]

    print(f"成功: {len(successes)}/{len(TEST_SCENARIOS)}")
    print(f"通过: {len(passed)}/{len(scored)} (及格线={PASS_THRESHOLD})")

    if scored:
        avgs = {}
        for dim in ["intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"]:
            vals = [r["eval"]["scores"].get(dim, 0) for r in scored if dim in r["eval"].get("scores", {})]
            if vals:
                avgs[dim] = sum(vals) / len(vals)
                print(f"  {dim}: {avgs[dim]:.1f}")

    # 差异化
    all_pois = [tuple(r["poi_names"]) for r in successes if r.get("poi_names")]
    unique_routes = len(set(all_pois))
    print(f"差异化: {unique_routes}/{len(successes)} 条不同路线")

    # 保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"docs/logs/test_c_version_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 关闭美团模拟服务器
    server_proc.terminate()
    server_proc.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
