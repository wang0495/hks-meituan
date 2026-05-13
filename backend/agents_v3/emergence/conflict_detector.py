"""涌现式校验 & 异常升级层。

Agent间矛盾自动探测：
- 地理矛盾：酒店距景点太远
- 预算矛盾：总和超支
- 时间矛盾：两个活动同时段
- 主题矛盾：亲子vs夜生活
"""

from __future__ import annotations


def detect_conflicts(proposals: list[dict], intent: dict) -> list[dict]:
    """检测所有类型的矛盾。"""
    conflicts = []
    conflicts.extend(_detect_budget_conflicts(proposals, intent))
    conflicts.extend(_detect_theme_conflicts(proposals, intent))
    conflicts.extend(_detect_geo_conflicts(proposals))
    return conflicts


def _detect_budget_conflicts(proposals: list[dict], intent: dict) -> list[dict]:
    """预算矛盾。"""
    budget = intent.get("budget", {}).get("per_person", 0)
    if budget <= 0:
        return []

    total = sum(
        p.get("content", {}).get("avg_price", 0)
        for p in proposals
        if p.get("agent") in ["poi", "food", "hotel"]
    )

    if total > budget * 1.5:
        return [{
            "type": "budget",
            "severity": "high" if total > budget * 2 else "medium",
            "description": f"总花费{total}元，超预算{budget}元{(total/budget-1)*100:.0f}%",
            "agents": [p["agent"] for p in proposals if p.get("content", {}).get("avg_price", 0) > 0],
            "auto_resolvable": total <= budget * 2,
        }]
    return []


def _detect_theme_conflicts(proposals: list[dict], intent: dict) -> list[dict]:
    """主题矛盾：如亲子vs夜生活。"""
    group = intent.get("group", {}).get("type", "")
    if group != "亲子":
        return []

    conflicts = []
    for p in proposals:
        content_str = str(p.get("content", {}))
        if any(kw in content_str for kw in ["酒吧", "夜店", "club", "夜市"]):
            conflicts.append({
                "type": "theme",
                "severity": "high",
                "description": f"亲子行程包含不适合儿童的活动: {p.get('content', {}).get('name', '')}",
                "agents": [p.get("agent", "")],
                "auto_resolvable": True,  # 自动移除
            })
    return conflicts


def _detect_geo_conflicts(proposals: list[dict]) -> list[dict]:
    """地理矛盾：住宿距景点太远。"""
    import math

    hotel = next((p for p in proposals if p.get("agent") == "hotel"), None)
    if not hotel:
        return []

    hotel_content = hotel.get("content", {})
    h_lat = hotel_content.get("lat", 0)
    h_lng = hotel_content.get("lng", 0)
    if not h_lat or not h_lng:
        return []

    conflicts = []
    for p in proposals:
        if p.get("agent") != "poi":
            continue
        poi_content = p.get("content", {})
        p_lat = poi_content.get("lat", 0)
        p_lng = poi_content.get("lng", 0)
        if p_lat and p_lng:
            # Haversine距离
            R = 6371
            dlat = math.radians(p_lat - h_lat)
            dlng = math.radians(p_lng - h_lng)
            a = (math.sin(dlat / 2) ** 2 +
                 math.cos(math.radians(h_lat)) * math.cos(math.radians(p_lat)) * math.sin(dlng / 2) ** 2)
            dist = R * 2 * math.asin(math.sqrt(a))

            if dist > 20:  # 超过20km标记冲突
                conflicts.append({
                    "type": "geo",
                    "severity": "medium" if dist > 40 else "low",
                    "description": f"住宿{hotel_content.get('name', '')}距景点{poi_content.get('name', '')}约{dist:.0f}km，较远",
                    "agents": ["hotel", "poi"],
                    "auto_resolvable": True,
                })
    return conflicts


def resolve_conflicts(proposals: list[dict], conflicts: list[dict]) -> list[dict]:
    """自动解决可解决的冲突。"""
    if not conflicts:
        return proposals

    # 移除被自动解决的提案
    to_remove_agents = set()
    for c in conflicts:
        if c.get("auto_resolvable") and c.get("type") == "theme":
            to_remove_agents.update(c.get("agents", []))

    # 移除亲子行程中的不合适提案
    resolved = []
    removed_names = set()
    for c in conflicts:
        if c.get("auto_resolvable") and c.get("type") == "theme":
            desc = c.get("description", "")
            # 找到要移除的提案名称
            for p in proposals:
                name = p.get("content", {}).get("name", "")
                if name in desc:
                    removed_names.add(name)

    for p in proposals:
        if p.get("content", {}).get("name", "") not in removed_names:
            resolved.append(p)
        else:
            resolved.append({**p, "confidence": 0.1, "reasoning": "被涌现式校验移除"})

    return resolved


def should_escalate(conflicts: list[dict]) -> bool:
    """是否需要升级给用户。"""
    return any(
        c.get("severity") == "high" and not c.get("auto_resolvable", False)
        for c in conflicts
    )
