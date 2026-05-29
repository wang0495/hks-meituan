"""POI expert: select tourist attractions from candidates using LLM decision.

Extracted from agents.py poi_agent.  Handles:
- Candidate filtering (exclude food/hotel/Macau/no-rating)
- Stratified sampling by category
- Scene-type-aware LLM prompting
- Smart rule-engine fallback when LLM fails
"""

from __future__ import annotations

import json

from backend.agents_v3.experts.base import (
    sse_expert,
    _FOOD_NAME_KWS,
    _LANDMARK_NAMES,
    _haversine_km,
    _is_likely_macau,
    _llm_decide,
    _proposal,
    _sanitize_for_prompt,
    _tag_similarity,
)
from backend.agents_v3.state import TravelState


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_poi_prompt(intent: dict) -> str:
    """根据用户意图动态生成POI Agent的system prompt。"""
    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")
    constraints = intent.get("hard_constraints", [])
    budget = intent.get("budget", {}).get("per_person", 0)

    # ── 场景特化指令 ──
    scene_extra = ""
    if group_type == "亲子":
        scene_extra = """
【亲子场景特化】
- 优先选有儿童游乐设施、海洋馆、动物园、科技馆类POI
- 排除夜生活、酒吧、高海拔/危险景点
- 每个景点停留时间要宽松（儿童体力有限）
- 选择有遮荫/室内备选的景点（防天气突变）
- 景点间距要小（带小孩不宜长途奔波）"""
    elif group_type == "情侣":
        scene_extra = """
【情侣场景特化】
- 优先选浪漫氛围的海滨、观景台、艺术区、特色咖啡厅
- 关注拍照打卡点（日落、夜景、特色建筑）
- 可以选有文化底蕴的景点（博物馆、历史街区）
- 避开过于拥挤的商业景点"""
    elif group_type == "朋友":
        scene_extra = """
【朋友聚会场景特化】
- 优先选互动性强的POI（密室、卡丁车、游乐园）
- 可以选热闹的街区、夜市
- 注意团队活动的适用性"""
    elif group_type == "退休":
        scene_extra = """
【银发场景特化】
- 优先选平缓、有休息设施的公园、文化场馆
- 排除需要大量步行/爬山的景点
- 选择有遮挡、有座椅的景点
- 景点间距离要短，移动方式优先公共交通"""
    elif group_type == "独居":
        scene_extra = """
【独游场景特化】
- 优先选适合独处的安静景点（书店、美术馆、公园）
- 可以选有文化深度的场所（博物馆、历史遗迹）
- 注意安全性（避开偏僻区域）"""
    elif group_type in ("团建", "团队", "公司"):
        scene_extra = """
【团建/大团队场景特化】
- 优先选适合团队互动的POI（拓展基地、沙滩、游乐园、卡丁车）
- 选择能容纳大群体的场所（公园、广场、大型景区）
- 排除不适合团队的活动（情侣向景点、小型场馆）
- 考虑团建常见需求：破冰、协作、合影
- 优先选有团建设施或集体活动空间的场所"""

    # 特种兵/闲逛
    pace_extra = ""
    if "特种兵" in pace:
        pace_extra = "\n- 特种兵模式：多选地标性景点（6-8个），追求覆盖面，但地理仍需紧凑"
    elif "闲逛" in pace:
        pace_extra = "\n- 闲逛模式：少选精（3-4个），每个景点停留时间充裕"

    # 硬约束
    constraint_extra = ""
    if "late_night" in constraints:
        constraint_extra += "\n- 深夜场景：优先选24小时营业或有夜景的景点，注意安全"
    if "indoor_only" in constraints:
        constraint_extra += "\n- 仅室内：排除所有户外景点（公园、海滨等）"
    if "pet_friendly" in constraints:
        constraint_extra += "\n- 宠物友好：优先选允许宠物入内的公园、广场"

    # 预算
    budget_extra = ""
    if budget and budget <= 200:
        budget_extra = "\n- 穷游模式：优先选免费景点（公园、海滩、历史街区），付费景点仅选1-2个高价值"

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


def _geo_cluster_filter(proposals: list[dict], all_candidates: list[dict]) -> list[dict]:
    """地理聚类后处理：检测并替换离群POI。

    策略：找到最大地理簇（pairwise距离<10km），替换不在簇内的POI。
    """
    # 提取有坐标的POI
    poi_coords = []
    for p in proposals:
        content = p.get("content", {})
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if lat and lng:
            poi_coords.append((p, lat, lng))

    if len(poi_coords) < 3:
        return proposals

    # 计算pairwise距离矩阵
    n = len(poi_coords)
    dist_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _haversine_km(
                poi_coords[i][1], poi_coords[i][2],
                poi_coords[j][1], poi_coords[j][2],
            )
            dist_matrix[i][j] = d
            dist_matrix[j][i] = d

    # 找到最大簇：从每个点出发，找所有距它<10km的点，选最大的那个簇
    best_cluster = set()
    for i in range(n):
        cluster = {j for j in range(n) if dist_matrix[i][j] < 10}
        cluster.add(i)
        if len(cluster) > len(best_cluster):
            best_cluster = cluster

    # 簇内点数必须过半
    if len(best_cluster) >= n:
        return proposals  # 全部在簇内

    # 计算簇中心
    cluster_lats = [poi_coords[i][1] for i in best_cluster]
    cluster_lngs = [poi_coords[i][2] for i in best_cluster]
    center_lat = sum(cluster_lats) / len(cluster_lats)
    center_lng = sum(cluster_lngs) / len(cluster_lngs)

    # 标记离群点
    outlier_indices = set(range(n)) - best_cluster

    # 构建已选POI名称集合
    selected_names = {p.get("content", {}).get("name", "") for p in proposals}

    # 尝试用簇中心附近的候选替换离群点
    result = list(proposals)
    for idx in outlier_indices:
        outlier_prop = poi_coords[idx][0]
        outlier_name = outlier_prop.get("content", {}).get("name", "")

        best_replacement = None
        best_score = -1

        for c in all_candidates:
            name = c.get("name", "")
            cat = c.get("category", "")
            if name in selected_names or name == outlier_name:
                continue
            if cat in ["住宿", "酒店", "民宿", "餐饮", "美食"]:
                continue
            if _is_likely_macau(name):
                continue
            if c.get("rating") is None:
                continue

            lat, lng = c.get("lat", 0), c.get("lng", 0)
            if not lat or not lng:
                continue

            dist = _haversine_km(lat, lng, center_lat, center_lng)
            if dist > 10:
                continue  # 只选簇中心10km范围内的

            score = (c.get("rating") or 4.0) * 0.3
            llm_q = c.get("_llm_quality", {})
            if llm_q.get("is_tourist"):
                score += 1.5
            for lm in _LANDMARK_NAMES:
                if lm in name:
                    score += 3.0
                    break
            if score > best_score:
                best_replacement = c
                best_score = score

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


def _smart_poi_selection(candidates: list[dict], intent: dict, user_input: str) -> list[dict]:
    """智能POI选择规则引擎：多维评分。"""
    text = user_input.lower()
    keywords = intent.get("preferred_categories", [])
    # 扩展关键词
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

    budget = intent.get("budget", {}).get("per_person", 500)
    pace = intent.get("pace", "平衡型")
    max_picks = 8 if "特种兵" in pace else (4 if "闲逛" in pace else 5)

    scored = []
    for c in candidates:
        # 跳过住宿和餐饮类
        cat = c.get("category", "")
        if cat in ["住宿", "酒店", "民宿", "餐饮", "美食"]:
            continue

        score = 0.0
        # 评分维度1: 基础质量
        rating = c.get("rating", 4.0)
        score += (rating - 3.5) * 0.15  # 4.0→0.075, 4.5→0.15

        # 评分维度2: 标签相似度
        tag_sim = _tag_similarity(c, keywords)
        score += tag_sim * 0.3

        # 评分维度3: 预算匹配
        price = c.get("avg_price", 0)
        if budget > 0 and price <= budget:
            score += 0.1
        elif budget > 0 and price > budget * 1.5:
            score -= 0.2

        # 评分维度4: 旅游质量
        llm_quality = c.get("_llm_quality", {})
        if llm_quality.get("is_tourist"):
            score += 0.15
        q_score = llm_quality.get("score", 0)
        score += q_score * 0.05

        # 评分维度5: 场景标签
        scene_tags = c.get("_scene_tags", [])
        if scene_tags:
            score += 0.05

        # 评分维度6: 适合度
        suitability = c.get("_suitability", {})
        group_type = intent.get("group", {}).get("type", "")
        if group_type == "亲子" and suitability.get("亲子友好"):
            score += 0.15
        if group_type == "情侣" and suitability.get("情侣友好"):
            score += 0.15
        if "退休" in group_type or "养老" in group_type:
            if suitability.get("老年友好"):
                score += 0.15

        scored.append((c, score))

    # 排序+多样性筛选
    scored.sort(key=lambda x: x[1], reverse=True)

    # 确保类别多样性
    selected = []
    seen_categories = set()
    for c, s in scored:
        cat = c.get("category", "未知")
        if len(selected) >= max_picks:
            break
        # 允许最多2个同类别
        if cat in seen_categories and sum(1 for x in selected if x[0].get("category") == cat) >= 2:
            continue
        selected.append((c, s))
        seen_categories.add(cat)

    return [_proposal("poi", c, round(min(0.5 + s, 0.95), 3), f"规则引擎评分{s:.2f}") for c, s in selected]


# ---------------------------------------------------------------------------
# Main expert function
# ---------------------------------------------------------------------------


@sse_expert("poi")
async def poi_expert(state: TravelState) -> dict:
    """POI expert: LLM selects attractions from candidate pool, with rule fallback.

    Reads expert_weights and expert_candidates from MoE state.  When
    expert_candidates["poi"] is empty, falls back to state["candidates"]
    with the same filtering logic as the original poi_agent.
    """
    weight = state.get("expert_weights", {}).get("poi", 0)
    if weight < 0.3:
        return {"proposals": []}

    # ── Resolve candidate pool ──
    candidates = state.get("expert_candidates", {}).get("poi", [])
    if not candidates:
        candidates = state.get("candidates", [])

    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
    scene_type = state.get("scene_type", "观光型")
    errors: list[str] = []

    # ── Read review feedback (for rework rounds) ──
    feedback = state.get("review_feedback", [])
    poi_feedback = [f for f in feedback if f.get("agent") == "poi"]
    feedback_hint = ""
    if poi_feedback:
        hints = "; ".join(f"{f['issue']} → {f['suggestion']}" for f in poi_feedback)
        feedback_hint = (
            "\n\n【上一轮审查反馈，必须据此调整】\n"
            f"{hints}\n"
            "请严格按照反馈要求重新选择，不要重复之前的错误。"
        )

    # ── Read prev_round_context (for feedback re-entry) ──
    prev_ctx = state.get("prev_round_context", {})
    context_hint = ""
    if prev_ctx:
        last_score = prev_ctx.get("last_score", 0)
        score_dims = prev_ctx.get("score_5dim", {})
        last_stops = prev_ctx.get("last_stops", [])
        reject_reason = prev_ctx.get("reject_reason", "")
        dims_str = "; ".join(f"{k}={v}" for k, v in score_dims.items() if v)
        context_hint = (
            f"\n\n【上一轮路线评分（反馈重入），请参考并改进】\n"
            f"总分: {last_score} | 分项: {dims_str}\n"
            f"上一轮路线: {' → '.join(last_stops[:8])}\n"
            f"用户不满意原因: {reject_reason}\n"
            f"要求: 保持上一轮高分维度不退化，重点改进低分维度。"
        )

    # 只做最基本过滤：去掉非景点、澳门、无评分垃圾POI
    _EXCLUDE_CATS = {"住宿", "酒店", "民宿", "餐饮", "美食", "小吃", "夜市小吃", "海鲜", "茶餐厅", "甜品", "饮品", "酒吧"}
    pool = []
    for c in candidates:
        name = c.get("name", "")
        cat = c.get("category", "")
        if cat in _EXCLUDE_CATS:
            continue
        # 名称包含餐饮关键词的也排除（防止美食街/海鲜街等被误选为景点）
        if any(kw in name for kw in _FOOD_NAME_KWS):
            continue
        if _is_likely_macau(name):
            continue
        if c.get("rating") is None:
            continue
        pool.append(c)

    # 按category分层抽样，确保LLM看到各类POI
    cat_groups: dict[str, list[dict]] = {}
    for c in pool:
        cat = c.get("category", "其他")
        cat_groups.setdefault(cat, []).append(c)

    # 每个category按rating排序后取前N个，总共控制在~200个
    sampled: list[dict] = []
    per_cat = max(3, 200 // max(len(cat_groups), 1))
    for cat, items in cat_groups.items():
        items.sort(key=lambda x: x.get("rating", 0), reverse=True)
        sampled.extend(items[:per_cat])

    # 如果总量还是太大，按rating截断
    if len(sampled) > 250:
        sampled.sort(key=lambda x: x.get("rating", 0), reverse=True)
        sampled = sampled[:250]

    # 构建LLM摘要
    poi_summaries = []
    for c in sampled:
        poi_summaries.append({
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
        })

    # ── Decision: LLM (scene-type-aware prompting) ──
    system = _build_poi_prompt(intent)

    # 场景覆盖：不同scene_type调整POI数量和策略
    pace = intent.get("pace", "平衡型")
    if scene_type == "美食型":
        # 美食场景：POI是散步消食用，选2-3个轻松地点（公园/海边/文化街区）
        max_picks = 3
        system += (
            "\n\n【美食场景覆盖】用户主要目的是吃，但路线也需要穿插1-2个散步消食的轻松地点"
            "（公园、海边、文化街区），让行程不只是吃。选2-3个即可，"
            "不要选需要长时间游览的景点。"
        )
    elif scene_type == "目的地型":
        max_picks = 3
        system += (
            "\n\n【目的地型覆盖】用户指定了大景区，会在那里待大半天。"
            "选1-2个附近的补充景点即可，不要远距离选点。"
        )
    else:
        max_picks = 8 if "特种兵" in pace else (4 if "闲逛" in pace else 5)

    # Adjust max_picks by weight
    if weight >= 0.8:
        max_picks = min(max_picks, 6)
    elif weight >= 0.5:
        max_picks = min(max_picks, 4)
    else:
        max_picks = min(max_picks, 3)

    # Further adjust for scene_type
    if scene_type == "美食型":
        max_picks = min(max_picks, 3)
    elif scene_type == "目的地型":
        max_picks = min(max_picks, 3)

    user = f"""用户需求: {_sanitize_for_prompt(user_input)}
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

    result = await _llm_decide(system, user)

    proposals = []
    name_map = {c.get("name", ""): c for c in candidates}
    if result and "picks" in result:
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for c in candidates:
                    if name in c.get("name", "") or c.get("name", "") in name:
                        content = c
                        break
            if content:
                proposals.append(_proposal(
                    "poi",
                    content,
                    pick.get("confidence", 0.7),
                    pick.get("reason", "LLM推荐"),
                ))

    # ── 降级：智能规则引擎（非简单fallback） ──
    if not proposals:
        proposals = _smart_poi_selection(candidates, intent, user_input)

    # ── 地理聚类：替换离群POI，确保路线紧凑 ──
    if proposals and len(proposals) >= 2:
        proposals = _geo_cluster_filter(proposals, pool)

    return {"proposals": proposals, "errors": errors}
