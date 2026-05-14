"""Food expert: select restaurants/food venues using LLM decision.

Extracted from agents.py food_agent.  Handles:
- Loading all food POIs via _load_all_pois() and merging with expert_candidates
- Stratified sampling by 5 subcategories (seafood, main, snacks, dessert, food street)
- Scene-type-aware LLM prompting (food-centric vs non-food-centric)
- Sub-intent detection via _food_intent_hint()
- Post-hoc diversity check with retry loop
- Smart rule-engine fallback when LLM fails
"""

from __future__ import annotations

import json
from collections import Counter

from backend.agents_v3.experts.base import (
    sse_expert,
    _food_intent_hint,
    _haversine_km,
    _is_likely_macau,
    _llm_decide,
    _load_all_pois,
    _proposal,
    _tag_similarity,
)
from backend.agents_v3.state import TravelState


# ---------------------------------------------------------------------------
# Food subcategory definitions
# ---------------------------------------------------------------------------

_FOOD_SUBCATS: dict[str, list[str]] = {
    "海鲜": ["海鲜", "蚝", "鱼排", "渔港"],
    "正餐": ["餐厅", "烧", "煲", "火锅", "烧烤"],
    "小吃": ["粉", "面", "粥", "小吃", "排档"],
    "茶餐厅/甜品": ["茶餐厅", "甜品", "奶茶", "冰", "柠檬", "饮品"],
    "综合美食街": ["夜市", "美食街", "海鲜街", "老街"],
}

_FOOD_CATS = ["餐饮", "美食", "小吃", "海鲜", "餐厅", "夜市", "茶餐厅", "甜品", "饮品"]

_FOOD_NAMES = [
    "餐厅", "海鲜", "烧", "煲", "粉", "面", "火锅", "烧烤", "夜市", "粥", "蚝", "排档",
    "甜品", "奶茶", "冰", "茶餐厅", "柠檬", "美食街", "海鲜街", "老街",
]

# Fixed LLM system prefix (cache-friendly -- kept at module level)
_FOOD_SYSTEM_PREFIX = """你是珠海美食推荐专家。根据用户需求从候选餐厅中挑选最合适的组合。

核心要求（按优先级）：
1. 【地理就近】午餐选上午游览景点附近（坐标相近的），晚餐选下午/傍晚景点附近
2. 【时段匹配】
   - 午餐(11:00-13:00)：用户通常在第2-3个景点后用餐，选该区域的特色餐厅
   - 晚餐(17:00-19:00)：用户通常在最后1-2个景点附近，选评价好的正餐
3. 【预算合理】人均不超预算，高评分优先
4. 【类型搭配·硬约束】
   - 夜市/美食街/海鲜街属于综合性美食场所，内部已有小吃+海鲜+甜品等多种，选1个就够了
   - 搭配原则：1个正餐（如海鲜餐厅/茶餐厅）+ 1个休闲（咖啡/甜品）+ 最多1个夜市/美食街
   - 禁止选2个以上夜市/美食街/海鲜街
   - 禁止全选同类型（如全是海鲜排档）
   - 参考UGC评价中提到的菜品和口碑来选择"""


# ---------------------------------------------------------------------------
# Subcategory helpers
# ---------------------------------------------------------------------------


def _get_food_subcat(name: str, subcat_defs: dict[str, list[str]] | None = None) -> str:
    """Return the food subcategory for a POI by name."""
    if subcat_defs is None:
        subcat_defs = _FOOD_SUBCATS
    for sub_name, kws in subcat_defs.items():
        if any(kw in name for kw in kws):
            return sub_name
    return "其他"


def _check_food_diversity_issues(
    proposals: list[dict],
    subcat_defs: dict[str, list[str]] | None = None,
    scene_type: str = "观光型",
) -> list[str]:
    """Check subcategory diversity of food proposals.  Empty list = pass."""
    if subcat_defs is None:
        subcat_defs = _FOOD_SUBCATS
    if len(proposals) < 2:
        return []

    subcats = [
        _get_food_subcat(p.get("content", {}).get("name", ""), subcat_defs)
        for p in proposals
    ]
    counts = Counter(subcats)
    issues: list[str] = []

    # 综合美食街最多1个
    street_count = counts.get("综合美食街", 0)
    if street_count > 1:
        street_names = [
            p.get("content", {}).get("name", "")
            for p in proposals
            if _get_food_subcat(p.get("content", {}).get("name", ""), subcat_defs) == "综合美食街"
        ]
        issues.append(
            f"选了{street_count}个综合美食场所（{', '.join(street_names)}），"
            "内部已有多种美食，最多选1个"
        )

    # 任何子类不超过2个
    for sub, cnt in counts.items():
        if cnt > 2:
            issues.append(f"{sub}类选了{cnt}个，同类型最多2个")

    # 美食型需要>=3种子类
    if scene_type == "美食型" and len(set(subcats)) < 3:
        issues.append(
            f"只覆盖{len(set(subcats))}种子类（{', '.join(set(subcats))}），"
            "美食路线需要>=3种不同子类"
        )

    return issues


# ---------------------------------------------------------------------------
# LLM pick matcher
# ---------------------------------------------------------------------------


def _match_food_picks(picks_data: list[dict], foods: list[dict]) -> list[dict]:
    """Match LLM-picked names back to food POI dicts and wrap as proposals."""
    matched: list[dict] = []
    name_map = {f.get("name", ""): f for f in foods}
    for pick in picks_data:
        name = pick.get("name", "")
        content = name_map.get(name)
        if not content:
            for f in foods:
                if name in f.get("name", "") or f.get("name", "") in name:
                    content = f
                    break
        if content:
            matched.append(
                _proposal("food", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐"))
            )
    return matched


# ---------------------------------------------------------------------------
# Smart rule-engine fallback
# ---------------------------------------------------------------------------


def _smart_food_selection(foods: list[dict], intent: dict, user_input: str) -> list[dict]:
    """Rule-based food selection when LLM fails."""
    if not foods:
        return [_proposal("food", {"name": "(无餐饮数据)", "category": "餐饮"}, 0.2, "无餐饮POI")]

    text = user_input.lower()
    budget = intent.get("budget", {}).get("per_person", 500)
    keywords: list[str] = []
    if "海鲜" in text:
        keywords.extend(["海鲜", "蚝", "鱼"])
    if "本地" in text or "特色" in text:
        keywords.extend(["本地", "特色", "传统", "老字号"])
    if "小吃" in text:
        keywords.extend(["小吃", "街边", "排档"])

    scored: list[tuple[dict, float]] = []
    for f in foods:
        score = 0.0
        rating = f.get("rating", 4.0)
        score += (rating - 3.5) * 0.2
        tag_sim = _tag_similarity(f, keywords) if keywords else 0
        score += tag_sim * 0.3
        price = f.get("avg_price", 0)
        if budget > 0 and price <= budget * 0.3:
            score += 0.15
        scored.append((f, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [
        _proposal("food", f, round(min(0.4 + s, 0.9), 3), f"规则引擎选餐{s:.2f}")
        for f, s in scored[:3]
    ]


# ---------------------------------------------------------------------------
# Main expert function
# ---------------------------------------------------------------------------


@sse_expert("food")
async def food_expert(state: TravelState) -> dict:
    """Food expert: LLM selects restaurants from food POI pool, with diversity checks.

    Reads expert_weights and expert_candidates from MoE state.  Always calls
    _load_all_pois() and merges with expert_candidates["food"], matching the
    original food_agent behaviour.

    Weight-gated max_food:
      - 美食型: 0.8+ -> 5 picks, 0.5-0.8 -> 4 picks, <0.5 -> 3 picks
      - non-美食型: max 2-3 picks
    """
    # ── Weight gate ──
    weight = state.get("expert_weights", {}).get("food", 0)
    if weight < 0.3:
        return {"proposals": []}

    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
    scene_type = state.get("scene_type", "观光型")
    errors: list[str] = []

    # ── Read review feedback (for rework rounds) ──
    feedback = state.get("review_feedback", [])
    food_feedback = [f for f in feedback if f.get("agent") == "food"]
    feedback_hint = ""
    if food_feedback:
        hints = "; ".join(f"{f['issue']} -> {f['suggestion']}" for f in food_feedback)
        feedback_hint = (
            "\n\n【上一轮审查反馈，必须据此调整】\n"
            f"{hints}\n"
            "请严格按照反馈要求重新选择，不要重复之前的错误。"
        )

    # ── Load all food POIs from data source (same as original food_agent) ──
    all_pois = await _load_all_pois()
    target_city = intent.get("city", "珠海")
    all_pois = [p for p in all_pois if p.get("city", "") == target_city or not p.get("city")]

    foods: list[dict] = [
        c
        for c in all_pois
        if (any(kw in c.get("category", "") for kw in _FOOD_CATS)
            or any(kw in c.get("name", "") for kw in _FOOD_NAMES))
        and c.get("category", "") not in ["购物", "酒店", "住宿"]
        and not _is_likely_macau(c.get("name", ""))
        and c.get("rating") is not None
    ]

    # Merge with expert_candidates["food"] (add any not already present)
    candidates_from_state = state.get("expert_candidates", {}).get("food", [])
    if candidates_from_state:
        existing_names = {f.get("name", "") for f in foods}
        for c in candidates_from_state:
            if c.get("name", "") not in existing_names:
                foods.append(c)
                existing_names.add(c.get("name", ""))

    # If still too few, also check state["candidates"]
    if len(foods) < 3:
        state_candidates = state.get("candidates", [])
        existing_names = {f.get("name", "") for f in foods}
        for c in state_candidates:
            if any(kw in c.get("name", "") for kw in _FOOD_NAMES):
                if c.get("name", "") not in existing_names:
                    foods.append(c)
                    existing_names.add(c.get("name", ""))

    # ── Extract POI locations for geo context ──
    state_candidates = state.get("candidates", [])
    poi_locations: list[dict] = []
    for c in state_candidates[:20]:
        if c.get("category", "") not in ["住宿", "酒店", "民宿", "餐饮", "美食"]:
            lat, lng = c.get("lat", 0), c.get("lng", 0)
            if lat and lng:
                poi_locations.append({
                    "name": c.get("name", ""),
                    "lat": round(lat, 3),
                    "lng": round(lng, 3),
                    "category": c.get("category", ""),
                })

    # POI cluster center (for rule scoring)
    _poi_center: tuple[float, float] | None = None
    if poi_locations:
        _poi_center = (
            sum(p["lat"] for p in poi_locations) / len(poi_locations),
            sum(p["lng"] for p in poi_locations) / len(poi_locations),
        )

    def _food_rule_score(f: dict) -> float:
        s = f.get("rating", 0)
        if _poi_center:
            lat, lng = f.get("lat", 0), f.get("lng", 0)
            if lat and lng:
                dist = _haversine_km(lat, lng, _poi_center[0], _poi_center[1])
                s -= dist * 0.05
        return s

    # ── Stratified sampling by 5 subcategories ──
    stratified: list[dict] = []
    subcat_map: dict[str, str] = {}
    seen_names: set[str] = set()
    for sub_name, kws in _FOOD_SUBCATS.items():
        bucket = [
            f for f in foods
            if any(kw in f.get("name", "") or kw in f.get("category", "") for kw in kws)
            and f.get("name", "") not in seen_names
        ]
        bucket.sort(key=_food_rule_score, reverse=True)
        for f in bucket[:3]:
            stratified.append(f)
            subcat_map[f.get("name", "")] = sub_name
            seen_names.add(f.get("name", ""))

    # Build LLM summaries (with coords + UGC)
    summaries = [
        {
            "name": f.get("name", ""),
            "type": subcat_map.get(f.get("name", ""), "其他"),
            "cat": f.get("category", ""),
            "price": f.get("avg_price", 0),
            "rating": f.get("rating", 0),
            "tags": f.get("tags", [])[:3],
            "lat": round(f.get("lat", 0), 3) if f.get("lat") else None,
            "lng": round(f.get("lng", 0), 3) if f.get("lng") else None,
            "reviews": f.get("_ugc_summary", ""),
        }
        for f in stratified[:15]
    ]

    group_type = intent.get("group", {}).get("type", "")

    # ── Determine max_food by weight and scene_type ──
    if scene_type == "美食型":
        # 0.8+ -> 5 picks, 0.5-0.8 -> 4 picks, <0.5 -> 3 picks
        max_food = 5 if weight >= 0.8 else (4 if weight >= 0.5 else 3)
    else:
        # non-美食型: max 2-3
        max_food = 3 if weight >= 0.8 else (3 if weight >= 0.5 else 2)

    # ── LLM prompting (scene-type-aware) ──
    if scene_type == "美食型":
        scene_reqs_text = " ".join(intent.get("scene_requirements", []))
        intent_hint = _food_intent_hint(scene_reqs_text, user_input)

        system = _FOOD_SYSTEM_PREFIX + f"""
5. 【美食场景特化·重要】
   - 用户就是为了吃来的！这是美食探索路线，餐饮是核心不是配角
   - 选4-5家不同类型的餐厅/小吃，必须覆盖至少3种子类：
     · 正餐（海鲜餐厅/粤菜餐厅）
     · 小吃（粉面粥/排档）
     · 甜品/饮品（茶餐厅/奶茶/甜品铺）
     · 综合美食场所（夜市/美食街/海鲜街）——最多只选1个！这类场所内部已有多种
   - 禁止选2个以上综合美食场所（夜市+美食街+海鲜街 都属于同一类）
   - 禁止全是海鲜（排档+海鲜市场+海鲜夜市都算海鲜一类）
   - 可以安排午餐+下午茶+晚餐的完整美食时间线
   - 每家之间的地理位置可以稍远（美食探索本身就是目的）
{intent_hint}
输出JSON: {{"picks":[{{"name":"店名","reason":"推荐理由","confidence":0.8,"meal_time":"午餐/下午茶/晚餐"}}]}}
选{max_food}个。只输出JSON。"""
    else:
        _GROUP_HINT = "亲子：选环境好、有儿童餐的；" if group_type == "亲子" else ""
        _GROUP_HINT += "情侣：选氛围好的特色餐厅；" if group_type == "情侣" else ""
        _GROUP_HINT += "特种兵：选快节奏、不用排队的。" if "特种兵" in user_input else ""
        system = _FOOD_SYSTEM_PREFIX + f"""
5. 【群体适配】{_GROUP_HINT}

输出JSON: {{"picks":[{{"name":"店名","reason":"推荐理由（含与哪个景点就近）","confidence":0.8,"meal_time":"午餐/晚餐"}}]}}
最多选{max_food}个。只输出JSON。"""

    user = f"""用户需求: {user_input}
场景类型: {scene_type}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
群体: {group_type or '未知'}

用户可能游览的景点位置:
{json.dumps(poi_locations[:10], ensure_ascii=False)}

候选餐厅（{len(stratified)}家，分层采样）:
{json.dumps(summaries, ensure_ascii=False)}
{feedback_hint}
请根据餐厅与景点的坐标距离，推荐最方便的就餐选择。"""

    result = await _llm_decide(system, user)

    proposals = _match_food_picks(result.get("picks", []), foods) if result and "picks" in result else []

    # ── Post-hoc diversity check + retry (up to 2 rounds) ──
    for _ in range(2):
        issues = _check_food_diversity_issues(proposals, _FOOD_SUBCATS, scene_type)
        if not issues:
            break
        current_info = [
            f"{p['content']['name']}({_get_food_subcat(p['content']['name'])})"
            for p in proposals if p.get("content", {}).get("name")
        ]
        feedback_lines = "\n".join(f"- {i}" for i in issues)
        reselect_user = f"""你之前选了: {', '.join(current_info)}

存在的问题:
{feedback_lines}

请从候选餐厅重新选择，确保子类型多样:
{json.dumps(summaries, ensure_ascii=False)}

输出JSON: {{"picks":[{{"name":"店名","reason":"理由","confidence":0.8,"meal_time":"午餐/下午茶/晚餐"}}]}}
不要重复之前的错误。"""

        new_result = await _llm_decide(system, reselect_user)
        if new_result and "picks" in new_result:
            new_proposals = _match_food_picks(new_result["picks"], foods)
            if new_proposals:
                proposals = new_proposals

    # ── Fallback: smart rule engine ──
    if not proposals:
        proposals = _smart_food_selection(foods, intent, user_input)

    return {"proposals": proposals, "errors": errors}
