"""POI expert: select tourist attractions from candidates using LLM decision.

Extracted from agents.py poi_agent.  Handles:
- Candidate filtering (exclude food/hotel/Macau/no-rating)
- Stratified sampling by category
- Scene-type-aware LLM prompting
- Smart rule-engine fallback when LLM fails
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.agents_v3.experts.base import (
    _FOOD_NAME_KWS,
    _LANDMARK_NAMES,
    _haversine_km,
    _is_likely_macau,
    _llm_decide,
    _proposal,
    _sanitize_for_prompt,
    _tag_similarity,
    sse_expert,
)

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


_POI_EXPERT_GROUP_SCENE: dict[str, str] = {
    "亲子": """
【亲子场景特化】
- 优先选有儿童游乐设施、海洋馆、动物园、科技馆类POI
- 排除夜生活、酒吧、高海拔/危险景点
- 每个景点停留时间要宽松（儿童体力有限）
- 选择有遮荫/室内备选的景点（防天气突变）
- 景点间距要小（带小孩不宜长途奔波）""",
    "情侣": """
【情侣场景特化】
- 优先选浪漫氛围的海滨、观景台、艺术区、特色咖啡厅
- 关注拍照打卡点（日落、夜景、特色建筑）
- 可以选有文化底蕴的景点（博物馆、历史街区）
- 避开过于拥挤的商业景点""",
    "朋友": """
【朋友聚会场景特化】
- 优先选互动性强的POI（密室、卡丁车、游乐园）
- 可以选热闹的街区、夜市
- 注意团队活动的适用性""",
    "退休": """
【银发场景特化】
- 优先选平缓、有休息设施的公园、文化场馆
- 排除需要大量步行/爬山的景点
- 选择有遮挡、有座椅的景点
- 景点间距离要短，移动方式优先公共交通""",
    "独居": """
【独游场景特化】
- 优先选适合独处的安静景点（书店、美术馆、公园）
- 可以选有文化深度的场所（博物馆、历史遗迹）
- 注意安全性（避开偏僻区域）""",
}
_POI_EXPERT_GROUP_SCENE["团建"] = _POI_EXPERT_GROUP_SCENE["团队"] = _POI_EXPERT_GROUP_SCENE[
    "公司"
] = """
【团建/大团队场景特化】
- 优先选适合团队互动的POI（拓展基地、沙滩、游乐园、卡丁车）
- 选择能容纳大群体的场所（公园、广场、大型景区）
- 排除不适合团队的活动（情侣向景点、小型场馆）
- 考虑团建常见需求：破冰、协作、合影
- 优先选有团建设施或集体活动空间的场所"""


def _build_poi_prompt(intent: dict) -> str:
    """根据用户意图动态生成POI Agent的system prompt。"""
    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")
    constraints = intent.get("hard_constraints", [])
    budget = intent.get("budget", {}).get("per_person", 0)

    scene_extra = _POI_EXPERT_GROUP_SCENE.get(group_type, "")
    pace_extra = (
        "\n- 特种兵模式：多选地标性景点（6-8个），追求覆盖面，但地理仍需紧凑"
        if "特种兵" in pace
        else ("\n- 闲逛模式：少选精（3-4个），每个景点停留时间充裕" if "闲逛" in pace else "")
    )

    constraint_extra = ""
    if "late_night" in constraints:
        constraint_extra += "\n- 深夜场景：优先选24小时营业或有夜景的景点，注意安全"
    if "indoor_only" in constraints:
        constraint_extra += "\n- 仅室内：排除所有户外景点（公园、海滨等）"
    if "pet_friendly" in constraints:
        constraint_extra += "\n- 宠物友好：优先选允许宠物入内的公园、广场"

    budget_extra = (
        "\n- 穷游模式：优先选免费景点（公园、海滩、历史街区），付费景点仅选1-2个高价值"
        if budget and budget <= 200
        else ""
    )

    return f"""你是珠海旅游景点规划专家。根据用户需求从候选列表中挑选最合适的景点组合。

核心要求（按优先级）：
1. 根据用户意图精准匹配（群体类型、预算、节奏）
2. **地理紧凑性**：每个景点都有lat/lng坐标，选出的景点在地理上应紧凑集中。
   - 通过坐标判断：如果选了lat=22.27的景点，其他景点也应集中在22.2-22.35范围内
   - 不要混合南北两端（如横琴lat~22.11和唐家湾lat~22.36跨距超25km）
   - 特种兵场景可以跨区域，但同区域的景点应连排
3. 场景多样性：自然/文化/娱乐/海滨 不重复同类型
{scene_extra}{pace_extra}{constraint_extra}{budget_extra}

输出JSON格式:
{{"picks":[{{"name":"景点名","reason":"选它的理由","confidence":0.8,"category_type":"自然/文化/娱乐/海滨之一"}}]}}

按推荐度排序，confidence范围0.5-1.0。只输出JSON。"""


# ---------------------------------------------------------------------------
# Geo cluster filter (post-processing)
# ---------------------------------------------------------------------------


def _build_dist_matrix_expert(coords: list[tuple]) -> list[list[float]]:
    """计算pairwise距离矩阵。"""
    n = len(coords)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _haversine_km(coords[i][1], coords[i][2], coords[j][1], coords[j][2])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def _find_largest_cluster_expert(
    dist_matrix: list[list[float]], threshold: float = 10.0
) -> set[int]:
    """找到最大地理簇。"""
    n = len(dist_matrix)
    best: set[int] = set()
    for i in range(n):
        cluster = {j for j in range(n) if dist_matrix[i][j] < threshold}
        cluster.add(i)
        if len(cluster) > len(best):
            best = cluster
    return best


_EXCLUDE_CATS = {"住宿", "酒店", "民宿", "餐饮", "美食"}


def _find_replacement_expert(
    outlier_name: str,
    selected_names: set[str],
    all_candidates: list[dict],
    center_lat: float,
    center_lng: float,
) -> dict | None:
    """为离群POI寻找替换。"""
    best_replacement = None
    best_score = -1.0

    for c in all_candidates:
        name = c.get("name", "")
        cat = c.get("category", "")
        if name in selected_names or name == outlier_name:
            continue
        if cat in _EXCLUDE_CATS or _is_likely_macau(name) or c.get("rating") is None:
            continue
        lat, lng = c.get("lat", 0), c.get("lng", 0)
        if not lat or not lng:
            continue

        dist = _haversine_km(lat, lng, center_lat, center_lng)
        if dist > 10:
            continue

        score = (c.get("rating") or 4.0) * 0.3
        if c.get("_llm_quality", {}).get("is_tourist"):
            score += 1.5
        if any(lm in name for lm in _LANDMARK_NAMES):
            score += 3.0
        if score > best_score:
            best_replacement = c
            best_score = score

    return best_replacement


def _geo_cluster_filter(proposals: list[dict], all_candidates: list[dict]) -> list[dict]:
    """地理聚类后处理：检测并替换离群POI。"""
    poi_coords = []
    for p in proposals:
        content = p.get("content", {})
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if lat and lng:
            poi_coords.append((p, lat, lng))

    if len(poi_coords) < 3:
        return proposals

    dist_matrix = _build_dist_matrix_expert(poi_coords)
    best_cluster = _find_largest_cluster_expert(dist_matrix)

    if len(best_cluster) >= len(poi_coords):
        return proposals

    cluster_lats = [poi_coords[i][1] for i in best_cluster]
    cluster_lngs = [poi_coords[i][2] for i in best_cluster]
    center_lat = sum(cluster_lats) / len(cluster_lats)
    center_lng = sum(cluster_lngs) / len(cluster_lngs)

    outlier_indices = set(range(len(poi_coords))) - best_cluster
    selected_names = {p.get("content", {}).get("name", "") for p in proposals}

    result = list(proposals)
    for idx in outlier_indices:
        outlier_prop = poi_coords[idx][0]
        outlier_name = outlier_prop.get("content", {}).get("name", "")

        best_replacement = _find_replacement_expert(
            outlier_name, selected_names, all_candidates, center_lat, center_lng
        )

        if best_replacement:
            for i, p in enumerate(result):
                if p.get("content", {}).get("name", "") == outlier_name:
                    result[i] = _proposal(
                        "poi",
                        best_replacement,
                        0.65,
                        f"地理聚类替换（原{outlier_name}距簇中心过远，替换为{best_replacement.get('name', '')}）",
                    )
                    selected_names.discard(outlier_name)
                    selected_names.add(best_replacement.get("name", ""))
                    break

    return result


# ---------------------------------------------------------------------------
# Smart rule-engine fallback
# ---------------------------------------------------------------------------


_EXPERT_EXCLUDE_CATS = ["住宿", "酒店", "民宿", "餐饮", "美食"]


def _expand_expert_keywords(user_input: str, base_keywords: list[str]) -> list[str]:
    """扩展关键词。"""
    keywords = list(base_keywords)
    text = user_input.lower()
    if "拍照" in text:
        keywords.extend(["拍照", "出片", "网红"])
    if "海鲜" in text or "美食" in text:
        keywords.extend(["美食", "海鲜", "餐饮"])
    if "孩子" in text or "亲子" in text:
        keywords.extend(["亲子", "儿童", "家庭"])
    if "海边" in text or "海" in text:
        keywords.extend(["海滨", "海", "沙滩", "海岛"])
    if "公园" in text:
        keywords.extend(["公园", "绿道"])
    return keywords


def _score_expert_poi(
    candidate: dict, keywords: list[str], budget: float, group_type: str
) -> float:
    """计算POI专家评分。"""
    score = 0.0
    rating = candidate.get("rating", 4.0)
    score += (rating - 3.5) * 0.15
    score += _tag_similarity(candidate, keywords) * 0.3

    price = candidate.get("avg_price", 0)
    if budget > 0 and price <= budget:
        score += 0.1
    elif budget > 0 and price > budget * 1.5:
        score -= 0.2

    llm_quality = candidate.get("_llm_quality", {})
    if llm_quality.get("is_tourist"):
        score += 0.15
    score += llm_quality.get("score", 0) * 0.05

    if candidate.get("_scene_tags"):
        score += 0.05

    suitability = candidate.get("_suitability", {})
    if group_type == "亲子" and suitability.get("亲子友好"):
        score += 0.15
    if group_type == "情侣" and suitability.get("情侣友好"):
        score += 0.15
    if ("退休" in group_type or "养老" in group_type) and suitability.get("老年友好"):
        score += 0.15

    return score


def _smart_poi_selection(candidates: list[dict], intent: dict, user_input: str) -> list[dict]:
    """智能POI选择规则引擎：多维评分。"""
    keywords = _expand_expert_keywords(user_input, intent.get("preferred_categories", []))
    budget = intent.get("budget", {}).get("per_person", 500)
    pace = intent.get("pace", "平衡型")
    max_picks = 8 if "特种兵" in pace else (4 if "闲逛" in pace else 5)
    group_type = intent.get("group", {}).get("type", "")

    scored = [
        (c, _score_expert_poi(c, keywords, budget, group_type))
        for c in candidates
        if c.get("category", "") not in _EXPERT_EXCLUDE_CATS
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    selected = []
    seen_categories: set[str] = set()
    for c, s in scored:
        cat = c.get("category", "未知")
        if len(selected) >= max_picks:
            break
        # 允许最多2个同类别
        if cat in seen_categories and sum(1 for x in selected if x[0].get("category") == cat) >= 2:
            continue
        selected.append((c, s))
        seen_categories.add(cat)

    return [
        _proposal("poi", c, round(min(0.5 + s, 0.95), 3), f"规则引擎评分{s:.2f}")
        for c, s in selected
    ]


# ---------------------------------------------------------------------------
# Main expert function
# ---------------------------------------------------------------------------


_POI_EXPERT_EXCLUDE_CATS = {
    "住宿",
    "酒店",
    "民宿",
    "餐饮",
    "美食",
    "小吃",
    "夜市小吃",
    "海鲜",
    "茶餐厅",
    "甜品",
    "饮品",
    "酒吧",
}


def _build_expert_poi_pool(candidates: list[dict]) -> list[dict]:
    """构建专家POI候选池。"""
    pool = []
    for c in candidates:
        name = c.get("name", "")
        cat = c.get("category", "")
        if cat in _POI_EXPERT_EXCLUDE_CATS:
            continue
        if any(kw in name for kw in _FOOD_NAME_KWS):
            continue
        if _is_likely_macau(name):
            continue
        if c.get("rating") is None:
            continue
        pool.append(c)
    return pool


def _build_expert_feedback_hints(state: dict) -> tuple[str, str]:
    """构建反馈提示。"""
    feedback = state.get("review_feedback", [])
    poi_feedback = [f for f in feedback if f.get("agent") == "poi"]
    feedback_hint = ""
    if poi_feedback:
        hints = "; ".join(f"{f['issue']} → {f['suggestion']}" for f in poi_feedback)
        feedback_hint = f"\n\n【上一轮审查反馈，必须据此调整】\n{hints}\n请严格按照反馈要求重新选择，不要重复之前的错误。"

    prev_ctx = state.get("prev_round_context", {})
    context_hint = ""
    if prev_ctx:
        last_score = prev_ctx.get("last_score", 0)
        score_dims = prev_ctx.get("score_5dim", {})
        last_stops = prev_ctx.get("last_stops", [])
        reject_reason = prev_ctx.get("reject_reason", "")
        dims_str = "; ".join(f"{k}={v}" for k, v in score_dims.items() if v)
        context_hint = f"\n\n【上一轮路线评分（反馈重入），请参考并改进】\n总分: {last_score} | 分项: {dims_str}\n上一轮路线: {' → '.join(last_stops[:8])}\n用户不满意原因: {reject_reason}\n要求: 保持上一轮高分维度不退化，重点改进低分维度。"

    return feedback_hint, context_hint


def _stratified_sample_expert(pool: list[dict], max_total: int = 250) -> list[dict]:
    """按category分层抽样。"""
    cat_groups: dict[str, list[dict]] = {}
    for c in pool:
        cat_groups.setdefault(c.get("category", "其他"), []).append(c)

    sampled = []
    per_cat = max(3, 200 // max(len(cat_groups), 1))
    for items in cat_groups.values():
        items.sort(key=lambda x: x.get("rating", 0), reverse=True)
        sampled.extend(items[:per_cat])

    if len(sampled) > max_total:
        sampled.sort(key=lambda x: x.get("rating", 0), reverse=True)
        sampled = sampled[:max_total]

    return sampled


def _build_expert_summaries(sampled: list[dict]) -> list[dict]:
    """构建LLM摘要。"""
    return [
        {
            "name": c.get("name", ""),
            "category": c.get("category", ""),
            "rating": c.get("rating", 0),
            "price": c.get("avg_price", 0),
            "tags": c.get("tags", [])[:5],
            "scene_tags": c.get("_scene_tags", [])[:3],
            "avg_stay_min": c.get("avg_stay_min", 60),
            "lat": c.get("lat", 0),
            "lng": c.get("lng", 0),
            "reviews": c.get("_ugc_summary", ""),
            "suitability": c.get("_suitability", {}),
        }
        for c in sampled
    ]


def _get_max_picks(scene_type: str, pace: str, weight: float) -> int:
    """获取最大选择数。"""
    if scene_type == "美食型" or scene_type == "目的地型":
        max_picks = 3
    else:
        max_picks = 8 if "特种兵" in pace else (4 if "闲逛" in pace else 5)

    max_picks = min(max_picks, 6 if weight >= 0.8 else 4 if weight >= 0.5 else 3)
    if scene_type in ("美食型", "目的地型"):
        max_picks = min(max_picks, 3)

    return max_picks


def _build_expert_system_prompt(system: str, scene_type: str) -> str:
    """构建场景特化系统提示。"""
    if scene_type == "美食型":
        return (
            system
            + "\n\n【美食场景覆盖】用户主要目的是吃，但路线也需要穿插1-2个散步消食的轻松地点（公园、海边、文化街区），让行程不只是吃。选2-3个即可，不要选需要长时间游览的景点。"
        )
    if scene_type == "目的地型":
        return (
            system
            + "\n\n【目的地型覆盖】用户指定了大景区，会在那里待大半天。选1-2个附近的补充景点即可，不要远距离选点。"
        )
    return system


def _match_expert_poi_picks(picks: list[dict], candidates: list[dict]) -> list[dict]:
    """匹配LLM picks到POI候选。"""
    proposals = []
    name_map = {c.get("name", ""): c for c in candidates}
    for pick in picks:
        name = pick.get("name", "")
        content = name_map.get(name)
        if not content:
            for c in candidates:
                if name in c.get("name", "") or c.get("name", "") in name:
                    content = c
                    break
        if content:
            proposals.append(
                _proposal(
                    "poi", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐")
                )
            )
    return proposals


def _build_expert_user_prompt(
    user_input: str,
    intent: dict,
    pace: str,
    sampled: list[dict],
    poi_summaries: list[dict],
    feedback_hint: str,
    context_hint: str,
    max_picks: int,
) -> str:
    """构建用户提示。"""
    return f"""用户需求: {_sanitize_for_prompt(user_input)}
意图分析:
- 偏好类别: {_sanitize_for_prompt(json.dumps(intent.get('preferred_categories', []), ensure_ascii=False))}
- 场景关键词: {_sanitize_for_prompt(json.dumps(intent.get('scene_requirements', []), ensure_ascii=False))}
- 预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
- 节奏: {pace}
- 群体: {intent.get('group', {}).get('type', '未知')}
- 人数: {intent.get('group', {}).get('size', 2)}
- 时间: {json.dumps(intent.get('time', {}), ensure_ascii=False)}

候选POI（{len(sampled)}个，按类别分层抽样）:
{json.dumps(poi_summaries, ensure_ascii=False)}
{feedback_hint}{context_hint}
请选出{max_picks}个最合适的景点。"""


@sse_expert("poi")
async def poi_expert(state: TravelState) -> dict:
    """POI expert: LLM selects attractions from candidate pool, with rule fallback."""
    weight = state.get("expert_weights", {}).get("poi", 0)
    if weight < 0.3:
        return {"proposals": []}

    candidates = state.get("expert_candidates", {}).get("poi", []) or state.get("candidates", [])
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
    scene_type = state.get("scene_type", "观光型")
    errors: list[str] = []

    feedback_hint, context_hint = _build_expert_feedback_hints(state)
    pool = _build_expert_poi_pool(candidates)
    sampled = _stratified_sample_expert(pool)
    poi_summaries = _build_expert_summaries(sampled)

    system = _build_expert_system_prompt(_build_poi_prompt(intent), scene_type)
    pace = intent.get("pace", "平衡型")
    max_picks = _get_max_picks(scene_type, pace, weight)

    user = _build_expert_user_prompt(
        user_input, intent, pace, sampled, poi_summaries, feedback_hint, context_hint, max_picks
    )
    result = await _llm_decide(system, user)
    proposals = (
        _match_expert_poi_picks(result.get("picks", []) if result else [], candidates)
        if result and "picks" in result
        else []
    )

    if not proposals:
        proposals = _smart_poi_selection(candidates, intent, user_input)

    if proposals and len(proposals) >= 2:
        proposals = _geo_cluster_filter(proposals, pool)

    return {"proposals": proposals, "errors": errors}
