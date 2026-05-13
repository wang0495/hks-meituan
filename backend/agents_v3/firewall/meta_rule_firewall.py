"""元规则防火墙层。

所有Agent提案必须通过硬约束检查。
软规则违反标记警告但不拒绝。
"""


def check_hard_rules(intent: dict, candidates: list[dict]) -> list[dict]:
    """检查硬约束，返回违规列表。"""
    violations = []
    budget = intent.get("budget", {}).get("per_person", 0)
    constraints = intent.get("hard_constraints", [])

    # 预算硬约束
    if budget > 0 and budget <= 300:
        over = [c for c in candidates if c.get("avg_price", 0) > budget * 1.2]
        if over:
            violations.append({
                "rule": "budget_hard",
                "severity": "warning",
                "description": f"{len(over)}个POI超过预算上限{int(budget*1.2)}元",
            })

    # 亲子必须有无障碍
    if "accessible" in constraints:
        no_access = [c for c in candidates if not c.get("accessible", True)]
        if no_access:
            violations.append({
                "rule": "accessible",
                "severity": "warning",
                "description": f"{len(no_access)}个POI缺少无障碍设施",
            })

    return violations


def filter_proposals_by_rules(proposals: list[dict], intent: dict) -> tuple[list[dict], list[dict]]:
    """过滤提案：硬规则违反的拒绝，软规则的保留。"""
    budget = intent.get("budget", {}).get("per_person", 0)
    violations = []
    passed = []

    for p in proposals:
        content = p.get("content", {})
        price = content.get("avg_price", 0)
        agent = p.get("agent", "")

        # 预算硬约束（超过2倍直接拒绝）
        if budget > 0 and price > budget * 2 and agent in ["poi", "food", "hotel"]:
            violations.append({
                "rule": "budget_hard",
                "agent": agent,
                "description": f"{content.get('name', '?')} ¥{price} 超预算2倍",
                "severity": "error",
            })
            continue

        passed.append(p)

    return passed, violations
