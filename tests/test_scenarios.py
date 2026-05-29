"""CityFlow 综合测试 — 覆盖 10+ 场景。

用法:
    python test_scenarios.py                  全部测试
    python test_scenarios.py --api-only       只测 API 规划
    python test_scenarios.py "关键词"         测试指定输入
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000"
PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results: list[dict] = []


# ── 场景定义 ────────────────────────────────────────────────────

SCENARIOS = [
    # (测试名, 输入, 期望约束, 期望群体)
    ("社恐独居", "周末想一个人安静走走，不想去人多的地方", ["低人流"], "独居"),
    ("情侣约会", "和女朋友约会，想找有氛围的地方", [], "情侣"),
    ("亲子出游", "周末带娃出去玩，让他消耗体力", ["儿童友好"], "亲子"),
    ("宠物友好", "带狗子出去转转，找个户外空间", ["pet_friendly"], "独居"),
    ("朋友聚会", "周末和朋友们一起聚餐唱歌", [], "朋友"),
    ("退休散步", "退休了想出去走走，散散步", [], "退休"),
    ("文化探索", "想去博物馆和历史古迹看看", [], "独居"),
    ("美食探店", "想找好吃的餐厅探店", [], "朋友"),
    ("自然户外", "想去爬山呼吸新鲜空气", [], "独居"),
    ("摄影打卡", "想找拍照好看的地方出片", [], "独居"),
    ("三代同堂", "带老人和孩子一家人出去玩", ["无障碍"], "亲子"),
    ("商务休闲", "找个环境优雅的地方谈事情", [], "独居"),
    ("学生穷游", "预算不多，想找免费好玩的地方", [], "朋友"),
    ("艺术家", "想去看展览找灵感", [], "独居"),
]


# ── 测试函数 ────────────────────────────────────────────────────


async def test_intent_parsing() -> None:
    """只测试意图解析。"""
    sys.path.insert(0, str(Path(__file__).parent))
    from backend.services.intent_parser import parse_intent

    print(f"\n{'='*80}")
    print(f"📋 意图解析测试")
    print(f"{'='*80}")

    for name, user_input, exp_constraints, exp_group in SCENARIOS:
        print(f"\n  [{name}] {user_input}")
        print(f"    期望群体: {exp_group}")

        intent = await parse_intent(user_input)
        group = intent.get("group", {}).get("type", "?")
        constraints = intent.get("hard_constraints", [])
        llm = intent.get("_llm_used", False)

        ok = group == exp_group
        icon = PASS if ok else FAIL
        print(f"    {icon} 实际群体: {group}  LLM={'是' if llm else '否'}")
        print(f"      约束: {constraints}")

        results.append({
            "type": "intent", "name": name, "input": user_input,
            "expected": exp_group,
            "actual": group,
            "passed": ok,
            "intent": intent,
        })


async def test_api_plan() -> None:
    """测试 API 端到端规划。"""
    print(f"\n{'='*80}")
    print(f"📋 API 端到端测试")
    print(f"{'='*80}")

    passed = 0
    failed = 0

    for name, user_input, exp_constraints, exp_group in SCENARIOS:
        print(f"\n  [{name}] {user_input}")
        start = time.time()

        try:
            result = await _call_api(user_input)
            elapsed = time.time() - start

            if "error" in result:
                print(f"    {FAIL} API 错误: {result['error']}")
                failed += 1
                continue

            done = result.get("done", {})
            route_id = done.get("route_id", "?")
            steps = result.get("steps", [])
            step_count = len(steps)
            route = done.get("full_route", {})
            intent = route.get("user_intent", {})
            group = intent.get("group", {}).get("type", "?")
            llm = intent.get("_llm_used", False)
            anomalies = result.get("anomalies", [])

            print(f"    {PASS} route_id={route_id[:8]}  |  "
                  f"{step_count}步  |  {elapsed:.1f}s")
            print(f"      群体: {group}  |  LLM={'是' if llm else '否'}  |  "
                  f"异常:{len(anomalies)}")

            results.append({
                "type": "api", "name": name, "input": user_input,
                "expected": exp_group,
                "actual": group,
                "passed": step_count > 0,
                "steps": step_count,
                "time": f"{elapsed:.1f}s",
            })
            passed += 1

        except Exception as e:
            print(f"    {FAIL} 异常: {e}")
            failed += 1

    print(f"\n  {'='*40}")
    print(f"  API 测试: {passed} 通过, {failed} 失败 / {len(SCENARIOS)} 总")


async def _call_api(user_input: str) -> dict:
    """调用 /api/plan 收集结果。"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST", f"{API_BASE}/api/plan",
            json={"user_input": user_input},
        ) as resp:
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            result: dict = {}
            buf = ""
            evt = ""
            async for chunk in resp.aiter_bytes():
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line.startswith("event: "):
                        evt = line[7:].strip()
                    elif line.startswith("data: "):
                        if not evt:
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        if evt == "done":
                            result["done"] = data
                        elif evt == "step":
                            result.setdefault("steps", []).append(data)
                        elif evt == "error":
                            result["error"] = data.get("error", "?")
                        elif evt == "anomaly":
                            result.setdefault("anomalies", []).append(data)
                        evt = ""
            return result


# ── 报告 ────────────────────────────────────────────────────────


def print_report() -> None:
    """输出测试报告。"""
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    failed = total - passed

    print(f"\n\n{'='*80}")
    print(f"📊 测试报告")
    print(f"{'='*80}")
    print(f"  总计: {total}  通过: {PASS} {passed}  失败: {FAIL} {failed}")

    # 按类型分组
    for test_type in ["intent", "api"]:
        type_results = [r for r in results if r.get("type") == test_type]
        if not type_results:
            continue
        type_passed = sum(1 for r in type_results if r.get("passed"))
        type_failed = len(type_results) - type_passed

        label = {"intent": "意图解析", "api": "API端到端"}.get(test_type, test_type)
        print(f"\n  [{label}] {type_passed}/{len(type_results)} 通过")

        for r in type_results:
            icon = PASS if r.get("passed") else FAIL
            print(f"    {icon} {r['name']}: 期望={r['expected']} 实际={r['actual']}")


# ── 主入口 ──────────────────────────────────────────────────────


async def main() -> None:
    if "--api-only" in sys.argv:
        await test_api_plan()
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        # 测试指定输入
        from backend.services.intent_parser import parse_intent
        intent = await parse_intent(" ".join(sys.argv[1:]))
        print(json.dumps(intent, ensure_ascii=False, indent=2))
    else:
        await test_intent_parsing()
        print()
        print()
        await test_api_plan()

    print_report()


if __name__ == "__main__":
    asyncio.run(main())
