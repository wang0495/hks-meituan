"""Review节点：检查agent提案质量，不通过则返回反馈让对应agent重做。

讨论池核心机制：
- review是"质检员"，不是"决策者"
- 它只判断proposals是否匹配用户意图，缺什么就说什么
- feedback写入state，graph条件边把对应agent重新跑一遍
"""

from __future__ import annotations

import json
import os

from backend.agents_v3.state import TravelState, AGENT_META, sse_emit


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

    # 超过2轮强制通过
    if round_num >= 2:
        return {"review_feedback": [], "review_round": round_num + 1}

    if not proposals:
        return {"review_feedback": [], "review_round": round_num + 1}

    # 按agent分类提案
    proposal_summary = []
    for p in proposals:
        c = p.get("content", {})
        proposal_summary.append({
            "agent": p.get("agent", ""),
            "name": c.get("name", ""),
            "category": c.get("category", ""),
            "lat": c.get("lat"),
            "lng": c.get("lng"),
            "rating": c.get("rating"),
        })

    scene_reqs = intent.get("scene_requirements", [])
    preferred_cats = intent.get("preferred_categories", [])
    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")

    # 按scene_type分化检查规则
    if scene_type == "美食型":
        check_rules = """请检查以下问题（每个问题必须指明是哪个agent的问题）：
1. food_expert: 餐饮子类型是否多样？（不应全是海鲜排档/全是夜市/全是同一种类，应覆盖海鲜+小吃+甜品/饮品+正餐）
2. food_expert: 是否选了太多综合性场所？（夜市+美食街+海鲜街最多选1个，它们内部已有多种）
3. poi_expert: 美食路线不需要太多景点，1-2个散步点即可，选多了反而是问题
4. 整体：路线是否以餐饮为主线？不应为了多样性硬塞景点"""
    elif scene_type == "目的地型":
        check_rules = """请检查以下问题：
1. poi_expert: 是否包含了用户指定的核心目的地？
2. food_expert: 餐厅是否在目的地附近？（不应选很远的地方）
3. 整体：POI是否集中在目的地周围？（不应大范围跨区域）"""
    elif scene_type == "特种兵型":
        check_rules = """请检查以下问题：
1. poi_expert: 是否选了足够多的地标景点？（特种兵应覆盖5-8个）
2. poi_expert: 景点类型是否多样？（自然+文化+娱乐+地标，不应全是一种）
3. food_expert: 餐厅是否快节奏？（不应选需要久坐的正餐）
4. 整体：路线是否紧凑无空隙？"""
    elif scene_type == "休闲型":
        check_rules = """请检查以下问题：
1. poi_expert: 景点是否太多？（休闲应3-4个，不应超过5个）
2. food_expert: 餐厅是否环境好、适合久坐？
3. 整体：路线节奏是否舒缓？"""
    else:
        check_rules = """请检查以下问题：
1. poi_expert: 是否选了与主题无关的POI？
2. food_expert: 餐厅位置是否和景点地理接近？菜系/类型是否多样？
3. poi_expert: 是否覆盖了用户提到的核心需求？
4. 整体：路线中POI类型是否过于单一？"""

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
        feedback.append({
            "agent": issue.get("agent", "poi"),
            "issue": issue.get("issue", ""),
            "suggestion": issue.get("suggestion", ""),
        })

    await sse_emit(state, "agent_result", {"agent": "review", "summary": f"通过，{len(proposals)}个提案有效" if not feedback else f"反馈{len(feedback)}个问题"})

    return {"review_feedback": feedback, "review_round": round_num + 1}


_review_client: "AsyncOpenAI | None" = None


def _get_review_client():
    global _review_client
    if _review_client is None:
        from openai import AsyncOpenAI
        _review_client = AsyncOpenAI(
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        )
    return _review_client


async def _llm_review(prompt: str) -> dict | None:
    """调用LLM做review。"""
    client = _get_review_client()
    for _ in range(2):
        try:
            resp = await client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            text = resp.choices[0].message.content or ""
            return json.loads(text)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Rework节点：根据review反馈，用LLM替换有问题的proposals
# ---------------------------------------------------------------------------

async def rework(state: TravelState) -> dict:
    """根据review反馈重新选择有问题的POI/餐饮。"""
    import uuid

    feedback = state.get("review_feedback", [])
    proposals = list(state.get("proposals", []))
    candidates = state.get("candidates", [])
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")

    # 删除有问题的agent的旧proposals
    bad_agents = {f.get("agent", "") for f in feedback}
    kept_proposals = [p for p in proposals if p.get("agent", "") not in bad_agents]
    bad_old = [p for p in proposals if p.get("agent", "") in bad_agents]

    feedback_text = "; ".join(
        f"[{f['agent']}] {f['issue']} → {f['suggestion']}" for f in feedback
    )

    # 构建重选prompt
    old_names = [p.get("content", {}).get("name", "") for p in bad_old]

    new_proposals = []
    reworked_agents = set()

    if "poi" in bad_agents or "poi_expert" in bad_agents:
        poi_result = await _rework_poi(candidates, intent, user_input, old_names, feedback_text)
        if poi_result:
            new_proposals.extend(poi_result)
            reworked_agents.add("poi")

    if "food" in bad_agents or "food_expert" in bad_agents:
        food_result = await _rework_food(candidates, intent, user_input, old_names, feedback_text)
        if food_result:
            new_proposals.extend(food_result)
            reworked_agents.add("food")

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
) -> list[dict]:
    """根据反馈重新选POI。"""
    import uuid

    # 过滤出景点类POI
    pool = [
        c for c in candidates
        if c.get("category", "") not in ["住宿", "酒店", "民宿", "餐饮", "美食"]
        and c.get("rating") is not None
        and c.get("name", "") not in old_names
    ]

    summaries = [
        {"name": c["name"], "category": c["category"], "rating": c.get("rating"),
         "tags": c.get("tags", [])[:3], "lat": c.get("lat"), "lng": c.get("lng")}
        for c in pool[:150]
    ]

    prompt = f"""你是景点规划专家。之前的选景点有严重问题，需要重选。

用户需求: {user_input}
场景要求: {intent.get('scene_requirements', [])}
偏好类别: {intent.get('preferred_categories', [])}

之前选的（必须全部替换）: {old_names}

审查反馈: {feedback_text}

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
                proposals.append({
                    "proposal_id": f"prop_rework_{uuid.uuid4().hex[:6]}",
                    "agent": "poi",
                    "content": content,
                    "confidence": pick.get("confidence", 0.7),
                    "reasoning": pick.get("reason", "rework重选"),
                })
    return proposals


async def _rework_food(
    candidates: list[dict],
    intent: dict,
    user_input: str,
    old_names: list[str],
    feedback_text: str,
) -> list[dict]:
    """根据反馈重新选餐饮。"""
    import uuid

    food_cats = ["餐饮", "美食", "小吃", "海鲜", "餐厅", "夜市", "茶餐厅", "甜品", "饮品", "酒吧", "咖啡馆"]
    food_names_kw = ["餐厅", "海鲜", "烧", "煲", "粉", "面", "火锅", "烧烤", "夜市", "粥", "蚝", "排档",
                     "甜品", "奶茶", "冰", "茶餐厅", "柠檬", "咖啡", "酒吧", "点心", "早茶"]

    pool = [
        c for c in candidates
        if (any(kw in c.get("category", "") for kw in food_cats)
            or any(kw in c.get("name", "") for kw in food_names_kw))
        and c.get("name", "") not in old_names
        and c.get("rating") is not None
    ]

    summaries = [
        {"name": c["name"], "category": c["category"], "rating": c.get("rating"),
         "price": c.get("avg_price"), "lat": c.get("lat"), "lng": c.get("lng")}
        for c in pool[:50]
    ]

    prompt = f"""你是美食推荐专家。之前的选餐厅有问题，需要重选。

用户需求: {user_input}
场景要求: {intent.get('scene_requirements', [])}

之前选的（必须全部替换）: {old_names}

审查反馈: {feedback_text}

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
                proposals.append({
                    "proposal_id": f"prop_rework_{uuid.uuid4().hex[:6]}",
                    "agent": "food",
                    "content": content,
                    "confidence": pick.get("confidence", 0.7),
                    "reasoning": pick.get("reason", "rework重选"),
                })
    return proposals
