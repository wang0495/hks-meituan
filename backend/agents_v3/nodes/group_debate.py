"""三阶段结构化Agent群聊：约束反驳。

Phase 1（并行）已在graph中完成：各Agent独立提交提案。
Phase 2（本节点）：结构化冲突检测 + Agent间反驳。
Phase 3（coordinator）：solver路线优化。

设计原则：
- 不做自由对话，只做结构化冲突检测
- 1轮反驳，被挑战者只能：接受 / 让步修改
- 冲突在进入solver之前被源头化解
"""

from __future__ import annotations

import json
import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState

logger = logging.getLogger(__name__)


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


_NIGHTLIFE_KEYWORDS = ["酒吧", "夜店", "club", "夜总会"]


def _check_theme_conflicts(proposals: list[dict], group_type: str) -> list[dict]:
    """检查主题矛盾。"""
    if group_type != "亲子":
        return []
    conflicts = []
    for p in proposals:
        name = p.get("content", {}).get("name", "")
        tags = str(p.get("content", {}).get("tags", []))
        if any(kw in name + tags for kw in _NIGHTLIFE_KEYWORDS):
            conflicts.append({"type": "theme", "severity": "high", "challenger": "rule_guard", "defendant": p.get("agent", ""), "target_name": name, "issue": f"亲子行程包含不适合儿童的活动: {name}", "resolution": "remove"})
    return conflicts


def _check_budget_conflicts(proposals: list[dict], budget: float) -> list[dict]:
    """检查预算超支。"""
    if budget <= 0:
        return []
    total = sum(p.get("content", {}).get("avg_price", 0) for p in proposals if p.get("agent") in ("poi", "food", "hotel"))
    if total <= budget * 1.5:
        return []
    expensive = sorted([p for p in proposals if p.get("agent") in ("food", "hotel") and p.get("content", {}).get("avg_price", 0) > 0], key=lambda p: p.get("content", {}).get("avg_price", 0), reverse=True)
    if not expensive:
        return []
    target = expensive[0]
    return [{"type": "budget", "severity": "high" if total > budget * 2 else "medium", "challenger": "rule_guard", "defendant": target.get("agent", ""), "target_name": target.get("content", {}).get("name", ""), "issue": f"总花费{total}元超预算{budget}元{(total/budget-1)*100:.0f}%", "resolution": "suggest_cheaper"}]


def _check_geo_conflicts(proposals: list[dict]) -> list[dict]:
    """检查地理矛盾。"""
    poi_coords = [(p.get("content", {}).get("lat", 0), p.get("content", {}).get("lng", 0)) for p in proposals if p.get("agent") == "poi" and p.get("content", {}).get("lat") and p.get("content", {}).get("lng")]
    if not poi_coords:
        return []

    center_lat = sum(la for la, _ in poi_coords) / len(poi_coords)
    center_lng = sum(lg for _, lg in poi_coords) / len(poi_coords)
    max_poi_dist = max(_haversine_km(la, lg, center_lat, center_lng) for la, lg in poi_coords)
    allowed = max(max_poi_dist + 5, 10)

    conflicts = []
    for p in proposals:
        if p.get("agent") != "food":
            continue
        content = p.get("content", {})
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if not lat or not lng:
            continue
        dist = _haversine_km(lat, lng, center_lat, center_lng)
        if dist > allowed:
            conflicts.append({"type": "geo_food", "severity": "medium", "challenger": "poi_agent", "defendant": "food_agent", "target_name": content.get("name", ""), "issue": f"餐厅{content.get('name', '')}距景点中心{dist:.0f}km（允许{allowed:.0f}km）", "resolution": "remove_food"})
    return conflicts


def _detect_rule_conflicts(proposals: list[dict], intent: dict) -> list[dict]:
    """规则层冲突检测（不调LLM，纯规则判断）。"""
    conflicts = []
    group_type = intent.get("group", {}).get("type", "")
    budget = intent.get("budget", {}).get("per_person", 0)

    conflicts.extend(_check_theme_conflicts(proposals, group_type))
    conflicts.extend(_check_budget_conflicts(proposals, budget))
    conflicts.extend(_check_geo_conflicts(proposals))

    return conflicts


async def _llm_debate_round(
    proposals: list[dict], rule_conflicts: list[dict], intent: dict, user_input: str
) -> list[dict]:
    """LLM结构化反驳：各Agent看到他人提案，标记跨Agent冲突。"""
    # 提取跨Agent关联信息
    proposal_details = []
    for p in proposals:
        content = p.get("content", {})
        proposal_details.append(
            {
                "agent": p.get("agent", "unknown"),
                "name": content.get("name", ""),
                "category": content.get("category", ""),
                "price": content.get("avg_price", 0),
                "rating": content.get("rating", 0),
                "lat": round(content.get("lat", 0), 4),
                "lng": round(content.get("lng", 0), 4),
                "confidence": p.get("confidence", 0.5),
                "reasoning": p.get("reasoning", "")[:100],
            }
        )

    conflict_summary = []
    for c in rule_conflicts:
        conflict_summary.append(f"- [{c['type']}] {c['issue']} → 建议: {c['resolution']}")

    system = """你是行程协调员（群聊主持人）。各Agent已提交提案，你需要检查跨Agent冲突。

你只能标记以下类型的冲突：
1. "geo_far": 景点间距离>15km，路线会来回跳跃
2. "type_repeat": 3个以上同类POI（如全是海滨类）
3. "time_conflict": 两个景点需要同一时段
4. "scene_mismatch": 景点类型与用户需求不匹配（如亲子场景选了夜生活场所）

对每个冲突，你必须给出明确的处理意见：
- "remove": 移除该POI（附理由）
- "swap": 建议替换为同区域更合适的POI（附建议名称特征）
- "keep": 保留但标记注意事项

输出JSON: {"debate_results":[{"conflict_type":"geo_far","challenger":"哪个Agent发起","defendant":"被挑战的Agent","target_name":"被挑战的POI","resolution":"remove/swap/keep","reason":"理由","swap_hint":"如果swap，建议的替换方向"}]}
没有冲突则输出 {"debate_results":[]}"""

    user = f"""用户需求: {user_input}
群体: {intent.get('group', {}).get('type', '未知')}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
节奏: {intent.get('pace', '平衡型')}

各Agent提案:
{json.dumps(proposal_details, ensure_ascii=False)}

已由规则引擎检测到的冲突:
{chr(10).join(conflict_summary) if conflict_summary else '无'}

请检查是否还有其他跨Agent冲突。"""

    from backend.agents_v3.nodes.agents import _llm_decide

    result = await _llm_decide(system, user)
    if result and "debate_results" in result:
        return result["debate_results"]
    return []


def _execute_rule_conflicts(proposals: list[dict], rule_conflicts: list[dict]) -> tuple[set[str], list[dict]]:
    """执行规则层决议，返回 (remove_names, negotiation_msgs)。"""
    remove_names: set[str] = set()
    msgs: list[dict] = []

    for c in rule_conflicts:
        resolution = c.get("resolution", "")
        target = c.get("target_name", "")

        if resolution in ("remove", "remove_food"):
            remove_names.add(target)
            msgs.append({"type": c["type"], "from": c.get("challenger", "rule"), "message": f"[规则驳回] {c['issue']} → 移除 {target}", "severity": c.get("severity", "medium")})
        elif resolution == "suggest_cheaper":
            for p in proposals:
                if p.get("content", {}).get("name", "") == target:
                    p["confidence"] = min(p.get("confidence", 0.5), 0.3)
                    p["reasoning"] = f"[预算警告] {p.get('reasoning', '')}"
            msgs.append({"type": "budget", "from": "rule_guard", "message": f"[预算警告] {c['issue']} → 降低 {target} 优先级", "severity": "medium"})

    return remove_names, msgs


def _execute_debate_results(cleaned: list[dict], debate_results: list[dict], negotiation_msgs: list[dict]) -> list[dict]:
    """执行LLM反驳决议。"""
    for d in debate_results:
        resolution = d.get("resolution", "keep")
        target = d.get("target_name", "")

        if resolution == "remove" and target:
            cleaned = [p for p in cleaned if p.get("content", {}).get("name", "") != target]
            negotiation_msgs.append({"type": d.get("conflict_type", ""), "from": d.get("challenger", "debate"), "message": f"[反驳移除] {d.get('reason', '')} → 移除 {target}", "severity": "medium"})
        elif resolution == "swap" and target:
            for p in cleaned:
                if p.get("content", {}).get("name", "") == target:
                    p["_needs_swap"] = True
                    negotiation_msgs.append({"type": d.get("conflict_type", ""), "from": d.get("challenger", "debate"), "message": f"[反驳替换] {d.get('reason', '')} → 替换 {target}", "severity": "medium"})
                    break
    return cleaned


async def group_debate(state: TravelState) -> dict:
    """三阶段群聊 — Phase 2: 结构化约束反驳。"""
    proposals = list(state.get("proposals", []))
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")

    if not proposals:
        return {"proposals": [], "negotiation_msgs": [], "conflicts": []}

    rule_conflicts = _detect_rule_conflicts(proposals, intent)
    remove_names, negotiation_msgs = _execute_rule_conflicts(proposals, rule_conflicts)
    cleaned = [p for p in proposals if p.get("content", {}).get("name", "") not in remove_names]

    debate_results = []
    try:
        debate_results = await _llm_debate_round(cleaned, rule_conflicts, intent, user_input)
    except Exception:
        logger.debug("LLM debate round failed, using rule-layer results only", exc_info=True)

    cleaned = _execute_debate_results(cleaned, debate_results, negotiation_msgs)

    return {
        "proposals": cleaned,
        "negotiation_msgs": negotiation_msgs,
        "conflicts": rule_conflicts + [{"type": d.get("conflict_type", ""), "target_name": d.get("target_name", ""), "resolution": d.get("resolution", "keep"), "severity": "medium"} for d in debate_results if d.get("resolution") in ("remove", "swap")],
    }
