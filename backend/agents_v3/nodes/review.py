"""Review节点：检查agent提案质量，不通过则返回反馈让对应agent重做。

讨论池核心机制：
- review是"质检员"，不是"决策者"
- 它只判断proposals是否匹配用户意图，缺什么就说什么
- feedback写入state，graph条件边把对应agent重新跑一遍
"""

from __future__ import annotations

import json
import os

from backend.agents_v3.state import TravelState


async def review(state: TravelState) -> dict:
    """审查所有agent提案质量，生成反馈。"""
    proposals = state.get("proposals", [])
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
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

    prompt = f"""你是旅行路线质量审查员。检查各Agent的提案是否匹配用户意图，找出明显问题。

用户需求: {user_input}
场景要求: {scene_reqs}
偏好类别: {preferred_cats}
群体: {group_type}
节奏: {pace}

Agent提案({len(proposal_summary)}个):
{json.dumps(proposal_summary, ensure_ascii=False)}

请检查以下问题（每个问题必须指明是哪个agent的问题）：
1. poi_agent: 是否选了与主题无关的POI？美食主题却3/5非餐饮？特种兵却缺地标？
2. food_agent: 是否选了餐厅？餐厅位置是否和景点地理接近？菜系/类型是否多样（不应全选海鲜或全选同一类型）？
3. poi_agent: 是否覆盖了用户提到的核心需求（海鲜、公园、景点等）？
4. 整体：路线中POI类型是否单一（如全是公园或全是博物馆），应包含不同类型？

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

    if "poi" in bad_agents:
        new_proposals = await _rework_poi(candidates, intent, user_input, old_names, feedback_text)
    elif "food" in bad_agents:
        new_proposals = await _rework_food(candidates, intent, user_input, old_names, feedback_text)
    else:
        new_proposals = []

    # 如果rework没产出，保留旧的
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
