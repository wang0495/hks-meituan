"""CityFlow 综合测试 — 覆盖 10+ 场景。

用法:
    python test_scenarios.py                  全部测试
    python test_scenarios.py --profile-only   只测画像匹配
    python test_scenarios.py --api-only   只测 API 规划
    python test_scenarios.py "关键词"       测试指定输入
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
    # (测试名, 输入, 期望画像, 期望约束, 期望群体)
    ("社恐独居", "周末想一个人安静走走，不想去人多的地方", "P1", ["低人流"], "独居"),
    ("情侣约会", "和女朋友约会，想找有氛围的地方", "P2", [], "情侣"),
    ("亲子出游", "周末带娃出去玩，让他消耗体力", "P3", ["儿童友好"], "亲子"),
    ("宠物友好", "带狗子出去转转，找个户外空间", "P12", ["pet_friendly"], "独居"),
    ("朋友聚会", "周末和朋友们一起聚餐唱歌", "P4", [], "朋友"),
    ("退休散步", "退休了想出去走走，散散步", "P5", [], "退休"),
    ("文化探索", "想去博物馆和历史古迹看看", "P6", [], "独居"),
    ("美食探店", "想找好吃的餐厅探店", "P7", [], "朋友"),
    ("自然户外", "想去爬山呼吸新鲜空气", "P8", [], "独居"),
    ("摄影打卡", "想找拍照好看的地方出片", "P10", [], "独居"),
    ("三代同堂", "带老人和孩子一家人出去玩", "P14", ["无障碍"], "亲子"),
    ("商务休闲", "找个环境优雅的地方谈事情", "P15", [], "独居"),
    ("学生穷游", "预算不多，想找免费好玩的地方", "P16", [], "朋友"),
    ("艺术家", "想去看展览找灵感", "P17", [], "独居"),
]


# ── 测试函数 ────────────────────────────────────────────────────


async def test_intent_parsing() -> None:
    """只测试意图解析 + 画像匹配。"""
    sys.path.insert(0, str(Path(__file__).parent))
    from backend.services.intent_parser import parse_intent, PROFILES

    print(f"\n{'='*80}")
    print(f"📋 意图解析测试（使用 intent_parser.PROFILES）")
    print(f"{'='*80}")

    for name, user_input, exp_pid, exp_constraints, exp_group in SCENARIOS:
        print(f"\n  [{name}] {user_input}")
        print(f"    期望: {exp_pid} ({exp_group})")

        intent = await parse_intent(user_input, PROFILES)
        pid = intent.get("matched_profile_id", "?")
        group = intent.get("group", {}).get("type", "?")
        constraints = intent.get("hard_constraints", [])
        llm = intent.get("_llm_used", False)

        ok = pid == exp_pid
        icon = PASS if ok else FAIL
        print(f"    {icon} 实际: {pid} ({group})  LLM={'是' if llm else '否'}")
        print(f"      约束: {constraints}")

        results.append({
            "type": "intent", "name": name, "input": user_input,
            "expected": f"{exp_pid}({exp_group})",
            "actual": f"{pid}({group})",
            "passed": ok,
            "intent": intent,
        })


async def test_user_profiles_matching() -> None:
    """使用 user_profiles.USER_PROFILES + match_profile 匹配。"""
    sys.path.insert(0, str(Path(__file__).parent))
    from backend.services.intent_parser import parse_intent, PROFILES
    from backend.services.user_profiles import match_profile, USER_PROFILES

    print(f"\n{'='*80}")
    print(f"📋 画像匹配测试（使用 user_profiles.match_profile）")
    print(f"{'='*80}")

    for name, user_input, exp_pid, exp_constraints, exp_group in SCENARIOS:
        print(f"\n  [{name}] {user_input}")

        # 先用 intent_parser 解析（用 PROFILES 做关键词匹配更准）
        intent = await parse_intent(user_input, PROFILES)

        # 再用 user_profiles 的余弦相似度匹配
        matched_id = match_profile(intent)
        profile = USER_PROFILES.get(matched_id, {})
        profile_name = profile.get("name", "?")

        # 期望映射（USER_PROFILES 的 ID 可能不同）
        ok = matched_id == exp_pid
        icon = PASS if ok else FAIL
        print(f"    {icon} 匹配: {matched_id} - {profile_name}")

        results.append({
            "type": "profile", "name": name, "input": user_input,
            "expected": exp_pid,
            "actual": f"{matched_id}({profile_name})",
            "passed": ok,
        })


async def test_api_plan() -> None:
    """测试 API 端到端规划。"""
    print(f"\n{'='*80}")
    print(f"📋 API 端到端测试")
    print(f"{'='*80}")

    passed = 0
    failed = 0

    for name, user_input, exp_pid, exp_constraints, exp_group in SCENARIOS:
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
            pid = intent.get("matched_profile_id", "?")
            group = intent.get("group", {}).get("type", "?")
            llm = intent.get("_llm_used", False)
            anomalies = result.get("anomalies", [])

            print(f"    {PASS if pid == exp_pid else WARN} route_id={route_id[:8]}  |  "
                  f"{step_count}步  |  {elapsed:.1f}s")
            print(f"      画像: {pid}({group})  |  LLM={'是' if llm else '否'}  |  "
                  f"异常:{len(anomalies)}")

            results.append({
                "type": "api", "name": name, "input": user_input,
                "expected": exp_pid,
                "actual": f"{pid}({group})",
                "passed": pid == exp_pid or step_count > 0,
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
    for test_type in ["intent", "profile", "api"]:
        type_results = [r for r in results if r.get("type") == test_type]
        if not type_results:
            continue
        type_passed = sum(1 for r in type_results if r.get("passed"))
        type_failed = len(type_results) - type_passed

        label = {"intent": "意图解析", "profile": "画像匹配", "api": "API端到端"}.get(test_type, test_type)
        print(f"\n  [{label}] {type_passed}/{len(type_results)} 通过")

        for r in type_results:
            icon = PASS if r.get("passed") else FAIL
            print(f"    {icon} {r['name']}: 期望={r['expected']} 实际={r['actual']}")


# ── 主入口 ──────────────────────────────────────────────────────


async def main() -> None:
    if "--profile-only" in sys.argv:
        await test_intent_parsing()
        await test_user_profiles_matching()
    elif "--api-only" in sys.argv:
        await test_api_plan()
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        # 测试指定输入
        from backend.services.intent_parser import parse_intent, PROFILES
        intent = await parse_intent(" ".join(sys.argv[1:]), PROFILES)
        print(json.dumps(intent, ensure_ascii=False, indent=2))
    else:
        await test_intent_parsing()
        await test_user_profiles_matching()
        print()
        print()
        await test_api_plan()

    print_report()


if __name__ == "__main__":
    asyncio.run(main())
