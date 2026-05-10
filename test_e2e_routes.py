"""端到端路线规划测试 — 多场景验证路线质量。

用法: python test_e2e_routes.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx

BASE = "http://localhost:8000"

TEST_SCENARIOS = [
    # ── 基础场景 ──
    {"name": "海滩休闲", "input": "想去海边走走，一个人，安静点", "budget": 500},
    {"name": "亲子游", "input": "带5岁孩子去玩，轻松一点", "budget": 800},
    {"name": "情侣约会", "input": "和女朋友约会，浪漫一点", "budget": 1000},
    {"name": "美食之旅", "input": "想去吃好吃的，走走逛逛吃吃", "budget": 300},
    {"name": "文化历史", "input": "想去博物馆和历史文化景点", "budget": 200},
    {"name": "运动健身", "input": "想运动一下，爬山或者打球", "budget": 200},
    {"name": "省钱出行", "input": "一个人，预算有限，想省钱玩", "budget": 100},
    {"name": "摄影打卡", "input": "想去拍照出片的地方打卡", "budget": 300},
    {"name": "休闲购物", "input": "想去逛街购物，轻松半天", "budget": 600},
    # ── 边界/复杂场景 ──
    {"name": "短时2h", "input": "只有2小时空闲，珠海随便逛逛", "budget": 200},
    {"name": "短时3h情侣", "input": "和对象只有3小时，想浪漫一点", "budget": 300},
    {"name": "极低预算", "input": "学生党，预算50元以内，想出去走走", "budget": 50},
    {"name": "纯美食请求", "input": "就想吃吃吃，带我去吃好吃的", "budget": 500},
    {"name": "纯运动请求", "input": "想运动，爬山游泳打球都行", "budget": 100},
    {"name": "退休夫妻", "input": "退休了和老伴出去走走，不要太累", "budget": 300},
    {"name": "多人朋友", "input": "4个朋友周末出去玩，热闹一点", "budget": 400},
    {"name": "夜生活", "input": "晚上去哪玩，想看夜景", "budget": 300},
    {"name": "雨天备选", "input": "下雨天去哪玩，室内为主", "budget": 200},
]

# 黑名单POI关键词（不应该出现在路线中的）
BLACKLIST_KEYWORDS = ["消防", "社区", "瑜伽", "普拉提", "汽配", "五金"]

# 不应该出现的类别
BAD_CATEGORIES = {"酒店"}


def test_plan(scenario: dict) -> dict:
    """测试单个场景。"""
    print(f"\n{'='*60}")
    print(f"🧪 场景: {scenario['name']}")
    print(f"   输入: {scenario['input']}")
    print(f"{'='*60}")

    payload = {
        "user_input": scenario["input"],
        "user_id": f"test_{scenario['name']}",
        "start_location": "<auto>",
    }

    start = time.time()
    try:
        with httpx.Client(timeout=120.0) as client:
            # SSE 流式响应
            response = client.post(f"{BASE}/api/plan", json=payload)
            elapsed = time.time() - start
            print(f"   耗时: {elapsed:.1f}s")

            if response.status_code != 200:
                return {"pass": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}

            # 解析 SSE（event: xxx 行 + data: xxx 行的模式）
            result = {}
            lines = response.text.split("\n")
            current_event = None
            for line in lines:
                line = line.strip()
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                elif line.startswith("data: ") and current_event == "done":
                    try:
                        data = json.loads(line[6:])
                        result = data.get("full_route", data)
                    except json.JSONDecodeError:
                        pass
                elif line.startswith("data: ") and current_event == "error":
                    try:
                        err = json.loads(line[6:])
                        return {"pass": False, "error": err.get("message", "未知错误")}
                    except json.JSONDecodeError:
                        pass

            return analyze_result(scenario, result, elapsed)

    except Exception as e:
        return {"pass": False, "error": str(e)}


def analyze_result(scenario: dict, result: dict, elapsed: float) -> dict:
    """分析规划结果质量。"""
    issues = []
    route = result.get("route", [])
    intent = result.get("user_intent", {})
    audit = result.get("audit_issues", []) or result.get("_audit_issues", [])

    if not route:
        return {"pass": False, "error": "路线为空", "elapsed": elapsed}

    poi_names = [s.get("poi", {}).get("name", "?") for s in route]

    # 1. 黑名单检查
    for name in poi_names:
        for kw in BLACKLIST_KEYWORDS:
            if kw in name:
                issues.append(f"❌ 含黑名单POI: {name} (关键词:{kw})")

    # 2. 类别检查
    for step in route:
        cat = step.get("poi", {}).get("category", "")
        if cat in BAD_CATEGORIES:
            issues.append(f"❌ 含不应出现的类别: {step['poi']['name']} ({cat})")

    # 3. 距离跳跃检查（从audit_issues）
    geo_jumps = [a for a in audit if "距离" in a.get("message", "") and "跨区" in a.get("message", "")]
    for j in geo_jumps:
        issues.append(f"⚠️ {j['message']}")

    # 4. 重复POI检查
    name_counts = {}
    for name in poi_names:
        name_counts[name] = name_counts.get(name, 0) + 1
    for name, count in name_counts.items():
        if count > 1 and "休息" not in name:
            issues.append(f"❌ 重复POI: {name} (出现{count}次)")

    # 5. 路线长度
    if len(route) < 2:
        issues.append("⚠️ 路线太短")
    if len(route) > 8:
        issues.append("⚠️ 路线过长")

    # 6. category多样性检查
    cats = [s.get("poi", {}).get("category", "") for s in route]
    if len(cats) >= 3:
        from collections import Counter
        cat_dist = Counter(cats)
        max_cat_count = max(cat_dist.values())
        max_cat_ratio = max_cat_count / len(cats)
        # 纯主题请求放宽阈值（用户明确要求某类活动）
        name_lower = scenario.get("name", "").lower()
        input_lower = scenario.get("input", "").lower()
        is_focused = any(kw in name_lower or kw in input_lower for kw in ["运动", "美食", "购物", "文化"])
        threshold = 0.65 if is_focused else 0.5
        if max_cat_ratio > threshold:
            dominant = max(cat_dist, key=cat_dist.get)
            issues.append(f"❌ category过于集中: {dominant}占{max_cat_ratio*100:.0f}% ({max_cat_count}/{len(cats)})")
        # 连续同类检查
        max_consec = 1
        cur = 1
        for i in range(1, len(cats)):
            if cats[i] == cats[i-1]:
                cur += 1
                max_consec = max(max_consec, cur)
            else:
                cur = 1
        if max_consec >= 3:
            issues.append(f"❌ 连续同类POI过多: 最大连续{max_consec}个同category")

    # 6. 预算检查
    total_cost = sum(s.get("poi", {}).get("avg_price", 0) for s in route)
    budget_limit = scenario.get("budget", 500)
    if total_cost > budget_limit * 1.3:
        issues.append(f"⚠️ 超预算: ¥{total_cost} > ¥{budget_limit}")

    # 确定结果
    errors = [i for i in issues if i.startswith("❌")]
    warnings = [i for i in issues if i.startswith("⚠️")]
    passed = len(errors) == 0

    return {
        "pass": passed,
        "issues": issues,
        "errors": errors,
        "warnings": warnings,
        "route": poi_names,
        "total_cost": total_cost,
        "length": len(route),
        "elapsed": elapsed,
        "audit_count": len(audit),
    }


def print_report(results: list[dict]):
    """打印测试报告。"""
    passed = sum(1 for r in results if r.get("pass"))
    total = len(results)

    print(f"\n\n{'='*60}")
    print(f"📊 测试报告: {passed}/{total} 通过")
    print(f"{'='*60}")

    for i, r in enumerate(results):
        status = "✅" if r.get("pass") else "❌"
        name = TEST_SCENARIOS[i]["name"]
        route_str = " → ".join(r.get("route", ["(空)"]))
        elapsed = r.get("elapsed", 0)
        cost = r.get("total_cost", 0)

        print(f"\n{status} [{name}] ({elapsed:.1f}s, ¥{cost})")
        print(f"   路线: {route_str}")

        for issue in r.get("issues", []):
            print(f"   {issue}")

        if "error" in r:
            print(f"   💥 {r['error']}")

    print(f"\n{'='*60}")
    print(f"总计: {passed}/{total} 通过")


def main():
    print("🌿 CityFlow 端到端路线测试")
    print(f"   服务器: {BASE}")
    print(f"   场景数: {len(TEST_SCENARIOS)}")

    results = []
    for scenario in TEST_SCENARIOS:
        result = test_plan(scenario)
        results.append(result)
        # 写结果到文件持久化
        Path("test_e2e_results.json").write_text(
            json.dumps(
                [
                    {"scenario": s["name"], **r}
                    for s, r in zip(TEST_SCENARIOS, results)
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print_report(results)

    # 退出码
    failed = sum(1 for r in results if not r.get("pass"))
    sys.exit(failed if failed < 10 else 10)


if __name__ == "__main__":
    main()
