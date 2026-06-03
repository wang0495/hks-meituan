"""Review节点：检查agent提案质量，不通过则返回反馈让对应agent重做。

讨论池核心机制：
- review是"质检员"，不是"决策者"
- 它只判断proposals是否匹配用户意图，缺什么就说什么
- feedback写入state，graph条件边把对应agent重新跑一遍
"""

from __future__ import annotations

import json
import math

from backend.agents_v3.experts.base import _llm_decide
from backend.agents_v3.state import AGENT_META, TravelState, sse_emit


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── 珠海区域分桶 ──
_AREA_BOUNDS = {
    "香洲": (22.24, 22.30, 113.53, 113.59),
    "吉大/拱北": (22.20, 22.26, 113.52, 113.56),
    "横琴": (22.08, 22.16, 113.50, 113.58),
    "金湾/斗门": (22.05, 22.20, 113.20, 113.40),
    "唐家湾/高新": (22.32, 22.40, 113.55, 113.62),
}


def _get_area(lat, lng):
    for name, (lat_min, lat_max, lng_min, lng_max) in _AREA_BOUNDS.items():
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return name
    return "其他"


_GEO_THRESHOLD_BY_SCENE: dict[str, float] = {
    "目的地型": 8.0, "特种兵型": 12.0, "美食型": 10.0, "休闲型": 15.0, "观光型": 12.0,
}


def _calc_max_distance(pois: list[dict]) -> float:
    """计算POI列表中最大站间距。"""
    max_dist = 0.0
    for i in range(len(pois)):
        for j in range(i + 1, len(pois)):
            d = _haversine_km(pois[i]["lat"], pois[i]["lng"], pois[j]["lat"], pois[j]["lng"])
            if d > max_dist:
                max_dist = d
    return max_dist


def _extract_pois_with_coords(proposals: list[dict]) -> list[dict]:
    """提取有坐标的POI。"""
    pois = []
    for p in proposals:
        c = p.get("content", {})
        lat, lng = c.get("lat", 0), c.get("lng", 0)
        if lat and lng:
            pois.append({"agent": p.get("agent", ""), "name": c.get("name", ""), "lat": lat, "lng": lng, "area": _get_area(lat, lng)})
    return pois


def _determine_keep_area(pois: list[dict], scene_type: str) -> str:
    """确定保留区域。"""
    if scene_type == "目的地型":
        for p in pois:
            if p["agent"] in ("destination", "destination_expert"):
                return p["area"]
    area_counts: dict[str, int] = {}
    for p in pois:
        area_counts[p["area"]] = area_counts.get(p["area"], 0) + 1
    return max(area_counts, key=area_counts.get)


def _rule_geo_check(proposals: list[dict], scene_type: str) -> list[dict]:
    """规则化地理检查：检测跨区POI，返回带坐标和区域信息的精确反馈。"""
    if len(proposals) < 2:
        return []

    pois = _extract_pois_with_coords(proposals)
    if len(pois) < 2:
        return []

    max_dist = _calc_max_distance(pois)
    if max_dist <= _GEO_THRESHOLD_BY_SCENE.get(scene_type, 15.0):
        return []

    keep_area = _determine_keep_area(pois, scene_type)
    keep_pois = [p for p in pois if p["area"] == keep_area]
    center_lat = sum(p["lat"] for p in keep_pois) / len(keep_pois)
    center_lng = sum(p["lng"] for p in keep_pois) / len(keep_pois)

    bad_agents = {p["agent"] for p in pois if p["area"] != keep_area}
    bad_names = [p["name"] for p in pois if p["area"] != keep_area]

    if not bad_agents:
        return []

    kept_names = [p["name"] for p in keep_pois[:5]]
    bad_desc = ", ".join(
        f"{p['name']}({p['area']})" for p in pois_with_coord if p["area"] != keep_area
    )

    feedback = []
    for agent in bad_agents:
        feedback.append(
            {
                "agent": agent,
                "issue": f"跨区跳跃{max_dist:.0f}km：{bad_desc} 距{keep_area}区域过远",
                "suggestion": f"在{keep_area}区域（中心{center_lat:.3f},{center_lng:.3f}）附近重选，替换{', '.join(bad_names)}。已保留: {', '.join(kept_names)}",
                "geo_context": {
                    "keep_area": keep_area,
                    "center_lat": round(center_lat, 4),
                    "center_lng": round(center_lng, 4),
                    "max_distance_km": round(max_dist, 1),
                    "bad_names": bad_names,
                },
            }
        )

    return feedback


_CHECK_RULES_BY_SCENE: dict[str, str] = {
    "美食型": """请检查以下问题（每个问题必须指明是哪个agent的问题）：
1. food_expert: 餐饮子类型是否多样？（不应全是海鲜排档/全是夜市/全是同一种类，应覆盖海鲜+小吃+甜品/饮品+正餐）
2. food_expert: 是否选了太多综合性场所？（夜市+美食街+海鲜街最多选1个，它们内部已有多种）
3. poi_expert: 美食路线不需要太多景点，1-2个散步点即可，选多了反而是问题
4. 整体：路线是否以餐饮为主线？不应为了多样性硬塞景点""",
    "目的地型": """请检查以下问题：
1. poi_expert: 是否包含了用户指定的核心目的地？
2. food_expert: 餐厅是否在目的地附近？（不应选很远的地方）
3. 整体：POI是否集中在目的地周围？（不应大范围跨区域）""",
    "特种兵型": """请检查以下问题：
1. poi_expert: 是否选了足够多的地标景点？（特种兵应覆盖5-8个）
2. poi_expert: 景点类型是否多样？（自然+文化+娱乐+地标，不应全是一种）
3. food_expert: 餐厅是否快节奏？（不应选需要久坐的正餐）
4. 整体：路线是否紧凑无空隙？""",
}


def _get_check_rules(scene_type: str) -> str:
    """获取场景对应的检查规则。"""
    if scene_type in _CHECK_RULES_BY_SCENE:
        return _CHECK_RULES_BY_SCENE[scene_type]
    return """请检查以下问题：
1. 景点是否多样？（不应全是同类型）
2. 餐厅选择是否合理？
3. 整体节奏是否合适？"""


async def review(state: TravelState) -> dict:
    """审查所有agent提案质量，生成反馈。"""
    meta = AGENT_META.get("review", {})
    await sse_emit(state, "agent_start", {"agent": "review", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "review", "text": f"审查 {len(state.get('proposals', []))} 个提案质量..."})

    proposals = list(state.get("reworked_proposals") or state.get("proposals", []))
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
    scene_type = state.get("scene_type", "观光型")
    round_num = state.get("review_round", 0)

    if round_num >= 2 or not proposals:
        return {"review_feedback": [], "review_round": round_num + 1}

    # 规则化地理检查
    rule_feedback = _rule_geo_check(proposals, scene_type)
    if rule_feedback:
        await sse_emit(state, "agent_result", {"agent": "review", "summary": f"地理检查发现{len(rule_feedback)}个跨区问题，触发rework"})
        return {"review_feedback": rule_feedback, "review_round": round_num + 1}

    # LLM语义审查
    proposal_summary = [{"agent": p.get("agent", ""), "name": p.get("content", {}).get("name", ""), "category": p.get("content", {}).get("category", ""), "lat": p.get("content", {}).get("lat"), "lng": p.get("content", {}).get("lng"), "rating": p.get("content", {}).get("rating")} for p in proposals]

    scene_reqs = intent.get("scene_requirements", [])
    preferred_cats = intent.get("preferred_categories", [])
    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")

    check_rules = _get_check_rules(scene_type)

    prompt = f"""你是旅行路线质量审查员。检查各Agent的提案是否匹配用户意图，找出明显问题。

场景类型: {scene_type}
用户需求: {user_input}
场景要求: {scene_reqs}
偏好类别: {preferred_cats}
群体: {group_type}
节奏: {pace}

Agent提案({len(proposal_summary)}个):
{json.dumps(proposal_summary, ensure_ascii=False)}

{check_rules}

输出JSON:
{{"issues":[{{"agent":"poi/food/hotel","issue":"问题描述","suggestion":"建议"}}],"approved":true/false}}

如果提案基本合理没有大问题，approved=true。只输出JSON。"""

    result = await _llm_review(prompt)

    if not result:
        return {"review_feedback": [], "review_round": round_num + 1}

    issues = result.get("issues", [])
    approved = result.get("approved", True)

    if approved or not issues:
        return {"review_feedback": [], "review_round": round_num + 1}

    # 转换为feedback格式
    feedback = []
    for issue in issues:
        feedback.append(
            {
                "agent": issue.get("agent", "poi"),
                "issue": issue.get("issue", ""),
                "suggestion": issue.get("suggestion", ""),
            }
        )

    await sse_emit(
        state,
        "agent_result",
        {
            "agent": "review",
            "summary": (
                f"通过，{len(proposals)}个提案有效"
                if not feedback
                else f"反馈{len(feedback)}个问题"
            ),
        },
    )

    return {"review_feedback": feedback, "review_round": round_num + 1}


async def _llm_review(prompt: str) -> dict | None:
    """调用LLM做review（委托给base._llm_decide）。"""
    return await _llm_decide("你是旅行路线质量审查员。", prompt, prefix="LLM")


# ---------------------------------------------------------------------------
# Rework节点：根据review反馈，用LLM替换有问题的proposals
# ---------------------------------------------------------------------------


async def rework(state: TravelState) -> dict:
    """根据review反馈重新选择有问题的POI/餐饮。"""

    feedback = state.get("review_feedback", [])
    proposals = list(state.get("proposals", []))
    candidates = state.get("candidates", [])
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")

    # 删除有问题的agent的旧proposals
    bad_agents = {f.get("agent", "") for f in feedback}
    kept_proposals = [p for p in proposals if p.get("agent", "") not in bad_agents]
    bad_old = [p for p in proposals if p.get("agent", "") in bad_agents]

    feedback_text = "; ".join(f"[{f['agent']}] {f['issue']} → {f['suggestion']}" for f in feedback)

    # 提取地理上下文（如果有规则检查的反馈）
    geo_ctx = None
    for f in feedback:
        if f.get("geo_context"):
            geo_ctx = f["geo_context"]
            break

    # 构建重选prompt
    old_names = [p.get("content", {}).get("name", "") for p in bad_old]

    new_proposals = []
    reworked_agents = set()

    if "poi" in bad_agents or "poi_expert" in bad_agents:
        poi_result = await _rework_poi(
            candidates, intent, user_input, old_names, feedback_text, geo_ctx
        )
        if poi_result:
            new_proposals.extend(poi_result)
            reworked_agents.add("poi")

    if "food" in bad_agents or "food_expert" in bad_agents:
        food_result = await _rework_food(
            candidates, intent, user_input, old_names, feedback_text, geo_ctx
        )
        if food_result:
            new_proposals.extend(food_result)
            reworked_agents.add("food")

    # 通用 rework: 处理其他有问题的 expert (hotel/traffic/local_expert/destination/budget_hacker)
    reworkable_generic = {
        "hotel",
        "hotel_expert",
        "traffic",
        "traffic_expert",
        "local_expert",
        "destination",
        "destination_expert",
        "budget_hacker",
    }
    generic_bad = bad_agents & reworkable_generic
    for agent_name in generic_bad:
        generic_result = await _rework_generic(
            agent_name, candidates, intent, user_input, old_names, feedback_text
        )
        if generic_result:
            new_proposals.extend(generic_result)
            reworked_agents.add(agent_name)

    # rework失败的agent保留旧proposals
    not_reworked = [p for p in bad_old if p.get("agent", "") not in reworked_agents]
    new_proposals.extend(not_reworked)

    if not new_proposals:
        new_proposals = bad_old

    all_proposals = kept_proposals + new_proposals

    return {
        "reworked_proposals": all_proposals,
        "review_feedback": [],  # 清空反馈
    }


async def _rework_poi(
    candidates: list[dict],
    intent: dict,
    user_input: str,
    old_names: list[str],
    feedback_text: str,
    geo_context: dict | None = None,
) -> list[dict]:
    """根据反馈重新选POI。geo_context 提供地理约束。"""
    import uuid

    # 过滤出景点类POI
    pool = [
        c
        for c in candidates
        if c.get("category", "") not in ["住宿", "酒店", "民宿", "餐饮", "美食"]
        and c.get("rating") is not None
        and c.get("name", "") not in old_names
    ]

    # 如果有地理约束，优先筛选保留区域附近的POI
    geo_hint = ""
    if geo_context:
        center_lat = geo_context.get("center_lat", 0)
        center_lng = geo_context.get("center_lng", 0)
        keep_area = geo_context.get("keep_area", "")
        max_km = geo_context.get("max_distance_km", 20)
        geo_hint = f"""

【地理硬约束】保留的POI集中在{keep_area}区域（中心坐标{center_lat},{center_lng}）。
新选的POI必须在该中心{max_km * 0.5:.0f}km范围内，确保路线紧凑不跨区。
候选POI已按距离中心由近到远排序，优先选前面的。"""

        # 按距离中心排序
        if center_lat and center_lng:
            pool.sort(
                key=lambda c: _haversine_km(
                    center_lat, center_lng, c.get("lat", 0), c.get("lng", 0)
                )
            )

    summaries = [
        {
            "name": c["name"],
            "category": c["category"],
            "rating": c.get("rating"),
            "tags": c.get("tags", [])[:3],
            "lat": c.get("lat"),
            "lng": c.get("lng"),
        }
        for c in pool[:150]
    ]

    prompt = f"""你是景点规划专家。之前的选景点有严重问题，需要重选。

用户需求: {user_input}
场景要求: {intent.get('scene_requirements', [])}
偏好类别: {intent.get('preferred_categories', [])}

之前选的（必须全部替换）: {old_names}

审查反馈: {feedback_text}
{geo_hint}

候选POI:
{json.dumps(summaries, ensure_ascii=False)}

请严格按反馈要求重选。输出JSON: {{"picks":[{{"name":"景点名","reason":"理由","confidence":0.8}}]}}"""

    result = await _llm_review(prompt)
    proposals = []
    if result and "picks" in result:
        name_map = {c.get("name", ""): c for c in candidates}
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for c in candidates:
                    if name in c.get("name", "") or c.get("name", "") in name:
                        content = c
                        break
            if content:
                proposals.append(
                    {
                        "proposal_id": f"prop_rework_{uuid.uuid4().hex[:6]}",
                        "agent": "poi",
                        "content": content,
                        "confidence": pick.get("confidence", 0.7),
                        "reasoning": pick.get("reason", "rework重选"),
                    }
                )
    return proposals


_AGENT_POOL_FILTERS: dict[str, tuple[str, callable]] = {
    "hotel": ("住宿", lambda c, old: c.get("category") in ("住宿", "酒店", "民宿") and c.get("name") not in old and c.get("rating") is not None),
    "hotel_expert": ("住宿", lambda c, old: c.get("category") in ("住宿", "酒店", "民宿") and c.get("name") not in old and c.get("rating") is not None),
    "traffic": ("交通", lambda c, old: c.get("rating") is not None and c.get("name") not in old),
    "traffic_expert": ("交通", lambda c, old: c.get("rating") is not None and c.get("name") not in old),
    "local_expert": ("本地特色", lambda c, old: c.get("rating", 4.0) >= 4.0 and c.get("name") not in old and c.get("category") not in ("住宿", "酒店", "民宿")),
    "destination": ("目的地", lambda c, old: c.get("category") not in ("住宿", "酒店", "民宿", "餐饮") and c.get("name") not in old and c.get("rating") is not None),
    "destination_expert": ("目的地", lambda c, old: c.get("category") not in ("住宿", "酒店", "民宿", "餐饮") and c.get("name") not in old and c.get("rating") is not None),
}
_DEFAULT_POOL_FILTER = ("省钱", lambda c, old: (c.get("avg_price", 9999) <= 50 or c.get("avg_price") == 0) and c.get("name") not in old and c.get("rating") is not None)


def _get_rework_pool(agent_name: str, candidates: list[dict], old_names: set[str]) -> tuple[list[dict], str]:
    """根据agent类型筛选候选池。"""
    label, filter_fn = _AGENT_POOL_FILTERS.get(agent_name, _DEFAULT_POOL_FILTER)
    pool = [c for c in candidates if filter_fn(c, old_names)]
    if agent_name in ("traffic", "traffic_expert"):
        pool = pool[:15]
    return pool, label


async def _rework_generic(
    agent_name: str,
    candidates: list[dict],
    intent: dict,
    user_input: str,
    old_names: list[str],
    feedback_text: str,
) -> list[dict]:
    """通用 rework: 适用于 hotel/traffic/local_expert/destination/budget_hacker。"""
    import uuid

    pool, expert_label = _get_rework_pool(agent_name, candidates, set(old_names))

    summaries = [
        {
            "name": c["name"],
            "category": c.get("category", ""),
            "rating": c.get("rating"),
            "avg_price": c.get("avg_price"),
            "lat": c.get("lat"),
            "lng": c.get("lng"),
        }
        for c in pool[:80]
    ]

    prompt = f"""你是{expert_label}专家。之前的选品有问题，需要重选。

用户需求: {user_input}
场景要求: {intent.get('scene_requirements', [])}

之前选的（必须全部替换）: {old_names}

审查反馈: {feedback_text}

候选:
{json.dumps(summaries, ensure_ascii=False)}

请严格按反馈要求重选3-5个最佳选择。输出JSON: {{"picks":[{{"name":"名称","reason":"理由","confidence":0.8}}]}}"""

    result = await _llm_review(prompt)
    proposals = []
    if result and "picks" in result:
        name_map = {c.get("name", ""): c for c in candidates}
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for c in candidates:
                    if name in c.get("name", "") or c.get("name", "") in name:
                        content = c
                        break
            if content:
                proposals.append(
                    {
                        "proposal_id": f"prop_rework_{uuid.uuid4().hex[:6]}",
                        "agent": agent_name,
                        "content": content,
                        "confidence": pick.get("confidence", 0.7),
                        "reasoning": pick.get("reason", "rework重选"),
                    }
                )
    return proposals


async def _rework_food(
    candidates: list[dict],
    intent: dict,
    user_input: str,
    old_names: list[str],
    feedback_text: str,
    geo_context: dict | None = None,
) -> list[dict]:
    """根据反馈重新选餐饮。geo_context 提供地理约束。"""
    import uuid

    food_cats = [
        "餐饮",
        "美食",
        "小吃",
        "海鲜",
        "餐厅",
        "夜市",
        "茶餐厅",
        "甜品",
        "饮品",
        "酒吧",
        "咖啡馆",
    ]
    food_names_kw = [
        "餐厅",
        "海鲜",
        "烧",
        "煲",
        "粉",
        "面",
        "火锅",
        "烧烤",
        "夜市",
        "粥",
        "蚝",
        "排档",
        "甜品",
        "奶茶",
        "冰",
        "茶餐厅",
        "柠檬",
        "咖啡",
        "酒吧",
        "点心",
        "早茶",
    ]

    pool = [
        c
        for c in candidates
        if (
            any(kw in c.get("category", "") for kw in food_cats)
            or any(kw in c.get("name", "") for kw in food_names_kw)
        )
        and c.get("name", "") not in old_names
        and c.get("rating") is not None
    ]

    geo_hint = ""
    if geo_context:
        center_lat = geo_context.get("center_lat", 0)
        center_lng = geo_context.get("center_lng", 0)
        keep_area = geo_context.get("keep_area", "")
        geo_hint = f"\n\n【地理硬约束】新选餐厅必须在{keep_area}区域（中心{center_lat},{center_lng}）附近，确保和景点在同一区域。"
        if center_lat and center_lng:
            pool.sort(
                key=lambda c: _haversine_km(
                    center_lat, center_lng, c.get("lat", 0), c.get("lng", 0)
                )
            )

    summaries = [
        {
            "name": c["name"],
            "category": c["category"],
            "rating": c.get("rating"),
            "price": c.get("avg_price"),
            "lat": c.get("lat"),
            "lng": c.get("lng"),
        }
        for c in pool[:50]
    ]

    prompt = f"""你是美食推荐专家。之前的选餐厅有问题，需要重选。

用户需求: {user_input}
场景要求: {intent.get('scene_requirements', [])}

之前选的（必须全部替换）: {old_names}

审查反馈: {feedback_text}
{geo_hint}

候选餐厅:
{json.dumps(summaries, ensure_ascii=False)}

请严格按反馈要求重选。输出JSON: {{"picks":[{{"name":"店名","reason":"理由","confidence":0.8,"meal_time":"午餐/晚餐"}}]}}"""

    result = await _llm_review(prompt)
    proposals = []
    if result and "picks" in result:
        name_map = {c.get("name", ""): c for c in candidates}
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for c in candidates:
                    if name in c.get("name", "") or c.get("name", "") in name:
                        content = c
                        break
            if content:
                proposals.append(
                    {
                        "proposal_id": f"prop_rework_{uuid.uuid4().hex[:6]}",
                        "agent": "food",
                        "content": content,
                        "confidence": pick.get("confidence", 0.7),
                        "reasoning": pick.get("reason", "rework重选"),
                    }
                )
    return proposals
