"""7个真Agent：每个Agent有感知→决策→行动三层架构。

核心设计：
- 感知(Listener)：读取state中相关事件和上下文
- 决策(Decision Core)：DeepSeek LLM做领域决策（全部用DeepSeek，无小模型）
- 行动(Actor)：输出结构化提案 + 协商消息

降级策略：LLM失败时用更复杂的规则引擎（不是简单hardcode），
规则引擎使用评分函数+向量相似度模拟。

═════════════════════════════════════════════════════════════
  架构决策记录（ADR）— 别瞎改，每条都是踩过坑的
═════════════════════════════════════════════════════════════

ADR-A1: food_agent候选池限制15个（5子类×top3）
  - 832个餐饮POI全给LLM → 选太多同类型 → 方差大
  - 分5个子类: 海鲜/正餐/小吃/茶餐厅甜品/综合美食街, 每类取top3
  - 综合美食街(夜市/美食街/海鲜街)最多选1个，内部已有多种

ADR-A2: food_agent排除购物/酒店/住宿category
  - 朝阳市场category=购物, 不是食品市场而是服装市场
  - 没这个过滤会导致food_agent选进非餐饮POI

ADR-A3: poi_agent必须排除名称含餐饮关键词的POI
  - 美食街/海鲜街在数据里category=文化, 不是餐饮
  - 如果不按名称排除, poi_agent会把美食街当文化景点选中
  - rule_guard._fix_food_categories()会在上游把category修正为餐饮
  - 这里是双保险

ADR-A4: 美食型场景poi_agent最多选3个散步点
  - 美食路线景点是配角, 2-3个散步消食点够了
  - 选多了反而挤占餐饮时间

ADR-A5: 不能用规则引擎替代LLM选POI
  - _smart_poi_selection是fallback规则, 效果远不如LLM
  - 规则引擎只能按rating+距离打分, 不理解用户意图
  - LLM能理解"带3岁宝宝转转"和"特种兵打卡"的区别
"""

from __future__ import annotations

import json
import logging
import math
import uuid

from backend.agents_v3.state import AGENT_META, TravelState, sse_emit

logger = logging.getLogger(__name__)


# 名称中包含这些关键词的POI应归为餐饮，不应被poi_agent选中
_FOOD_NAME_KWS = [
    "美食街",
    "海鲜街",
    "小吃街",
    "美食城",
    "美食广场",
    "食街",
    "夜市",
    "大排档",
    "海鲜城",
    "海鲜市场",
    "水产市场",
    "餐厅",
    "茶餐厅",
    "火锅",
    "烧烤",
    "甜品店",
    "奶茶",
]


def _food_intent_hint(scene_reqs_text: str, user_input: str) -> str:
    """根据用户子意图生成food_agent的额外prompt提示。

    检测scene_requirements和user_input中的食物关键词，
    指导LLM优先选对应类型的餐饮。
    """
    text = scene_reqs_text + " " + user_input
    hints = []

    if any(kw in text for kw in ["甜品", "奶茶", "冰室", "甜点", "蛋糕"]):
        hints.append(
            "   - ⚠️ 用户核心需求是吃甜品！优先选甜品店/奶茶/冰室/茶餐厅甜品档，正餐最多选1家"
        )
    if any(kw in text for kw in ["海鲜", "生蚝", "虾", "蟹"]):
        hints.append("   - ⚠️ 用户核心需求是吃海鲜！优先选海鲜排档/海鲜市场/海鲜餐厅，少选粉面粥")
    if any(kw in text for kw in ["小吃", "粉", "面", "粥", "排档", "扫街"]):
        hints.append("   - ⚠️ 用户核心需求是吃小吃！优先选粉面粥/排档/夜市小吃，正餐酒楼最多1家")
    if any(kw in text for kw in ["夜宵", "深夜", "凌晨", "宵夜", "夜市"]):
        hints.append("   - ⚠️ 用户是深夜觅食！优先选大排档/深夜营业场所，正餐餐厅可能已关门")
    if any(kw in text for kw in ["茶餐厅", "早茶", "点心"]):
        hints.append("   - ⚠️ 用户想吃茶餐厅/早茶！优先选粤式茶餐厅，其他类型最多1家")

    if hints:
        return "\n6. 【用户子意图·最重要】\n" + "\n".join(hints)
    return ""


# ═══════════════════════════════════════════════════════════
# 公共工具
# ═══════════════════════════════════════════════════════════


def _proposal(agent: str, content: dict, confidence: float, reasoning: str) -> dict:
    return {
        "proposal_id": f"prop_{agent}_{uuid.uuid4().hex[:6]}",
        "agent": agent,
        "content": content,
        "confidence": round(confidence, 3),
        "reasoning": reasoning,
    }


async def _load_all_pois() -> list[dict]:
    """从美团API获取全部POI数据。"""
    try:
        from backend.agents_v3.meituan_client import fetch_pois

        return await fetch_pois()
    except Exception:
        # API不可用时降级到本地JSON
        try:
            from backend.services.data_service import get_data

            data = get_data()
            if isinstance(data, dict):
                return list(data.values())
            if isinstance(data, list):
                return data
        except Exception:
            logger.debug("local JSON data_service fallback failed", exc_info=True)
        return []


# LLM调用统一委托给experts/base.py
from backend.agents_v3.experts.base import _get_llm_client, _llm_decide  # noqa: F401, E402


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两点间距离(km)。"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _is_likely_macau(name: str) -> bool:
    """检测是否是澳门POI（数据中有些错误标记为珠海）。"""
    macau_keywords = [
        "Museu",
        "Casa",
        "Troço",
        "Posto",
        "Esplanada",
        "Muralhas",
        "Taipa",
        "Prémio",
        "Macau",
        "Wynn",
        "Grand",
        "Lisboa",
        "Venetian",
        "Parisian",
        "Morrisson",
        "Guia",
        "Penha",
        "Barra",
        "Patane",
        "博物館露天",
        "大賽車",
        "沙梨頭",
        "噴泉表演 Fountain",
        "海事博物館",
        "倫記軟滑",
        "永利名店",
        "吉祥樹表演",
        "龍環葡韻",
        "東方基金",
        "舊城牆遺址",
        # 新增常见澳门餐饮
        "檸檬車露",
        "義順鮮奶",
        "禮記",
        "榮暉",
        "氹仔",
        "馬交",
        "葡國菜",
        "葡式",
        "葡撻",
        "車厘哥夫",
        "潘榮",
        "六記",
        "誠昌",
        "木糠",
        "杏仁餅",
    ]
    for kw in macau_keywords:
        if kw in name:
            return True
    # 检测是否含大量葡萄牙语/英语（澳门POI通常中英双语）
    chinese_chars = sum(1 for c in name if "\u4e00" <= c <= "\u9fff")
    latin_chars = sum(1 for c in name if ("a" <= c <= "z") or ("A" <= c <= "Z"))
    return bool(latin_chars > chinese_chars and latin_chars > 5)


# 珠海知名地标（用于评分boost）
_LANDMARK_NAMES = {
    "长隆海洋王国",
    "海洋王国",
    "珠海渔女",
    "情侣路",
    "圆明新园",
    "海滨泳场",
    "野狸岛",
    "日月贝",
    "珠海大剧院",
    "港珠澳大桥",
    "外伶仃岛",
    "淇澳岛",
    "飞沙滩",
    "金海滩",
    "御温泉",
    "唐家湾古镇",
    "梅溪牌坊",
    "农科奇观",
    "梦幻水城",
    "湾仔海鲜街",
    "拱北口岸",
}


def _tag_similarity(poi: dict, keywords: list[str]) -> float:
    """计算POI与关键词的向量相似度（用标签匹配模拟）。"""
    score = 0.0
    name = poi.get("name", "")
    cat = poi.get("category", "")
    tags = poi.get("tags", [])
    scene_tags = poi.get("_scene_tags", [])
    suitability = poi.get("_suitability", {})
    all_text = f"{name} {cat} {' '.join(tags)} {' '.join(scene_tags)} {' '.join(str(v) for v in suitability.values())}"

    matched = 0
    for kw in keywords:
        if kw in all_text:
            matched += 1
    if keywords:
        score = matched / len(keywords)
    return score


# ═══════════════════════════════════════════════════════════
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
        budget_extra = (
            "\n- 穷游模式：优先选免费景点（公园、海滩、历史街区），付费景点仅选1-2个高价值"
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


# 景点Agent — LLM感知+决策+行动
# ═══════════════════════════════════════════════════════════


_EXCLUDED_POI_CATS = ["住宿", "酒店", "民宿", "餐饮", "美食"]


def _build_poi_pool(candidates: list[dict]) -> list[dict]:
    """构建景点候选池。"""
    pool = []
    for c in candidates:
        name = c.get("name", "")
        cat = c.get("category", "")
        if cat in _EXCLUDED_POI_CATS:
            continue
        if any(kw in name for kw in _FOOD_NAME_KWS):
            continue
        if _is_likely_macau(name):
            continue
        if c.get("rating") is None:
            continue
        pool.append(c)
    return pool


def _stratified_sample_pois(pool: list[dict], max_total: int = 250) -> list[dict]:
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


def _build_poi_summaries(sampled: list[dict]) -> list[dict]:
    """构建LLM摘要。"""
    return [{"name": c.get("name", ""), "category": c.get("category", ""), "rating": c.get("rating", 0), "price": c.get("avg_price", 0), "tags": c.get("tags", [])[:5], "scene_tags": c.get("_scene_tags", [])[:3], "avg_stay_min": c.get("avg_stay_min", 60), "lat": c.get("lat", 0), "lng": c.get("lng", 0), "reviews": c.get("_ugc_summary", ""), "suitability": c.get("_suitability", {})} for c in sampled]


def _match_poi_picks(picks: list[dict], candidates: list[dict]) -> list[dict]:
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
            proposals.append(_proposal("poi", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐")))
    return proposals


async def poi_agent(state: TravelState) -> dict:
    """景点Agent：LLM直接从候选池选景点，不做算法预排序。"""
    meta = AGENT_META.get("poi", {})
    await sse_emit(state, "agent_start", {"agent": "poi", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "poi", "text": "加载候选景点，按分类分层抽样..."})

    candidates = state.get("candidates", [])
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
    scene_type = state.get("scene_type", "观光型")
    errors = []

    feedback = state.get("review_feedback", [])
    poi_feedback = [f for f in feedback if f.get("agent") == "poi"]
    feedback_hint = ""
    if poi_feedback:
        hints = "; ".join(f"{f['issue']} → {f['suggestion']}" for f in poi_feedback)
        feedback_hint = f"\n\n【上一轮审查反馈，必须据此调整】\n{hints}\n请严格按照反馈要求重新选择，不要重复之前的错误。"

    pool = _build_poi_pool(candidates)
    sampled = _stratified_sample_pois(pool)
    poi_summaries = _build_poi_summaries(sampled)

    system = _build_poi_prompt(intent)
    pace = intent.get("pace", "平衡型")
    if scene_type == "美食型":
        max_picks = 3
        system += "\n\n【美食场景覆盖】用户主要目的是吃，但路线也需要穿插1-2个散步消食的轻松地点（公园、海边、文化街区），让行程不只是吃。选2-3个即可，不要选需要长时间游览的景点。"
    elif scene_type == "目的地型":
        max_picks = 3
        system += "\n\n【目的地型覆盖】用户指定了大景区，会在那里待大半天。选1-2个附近的补充景点即可，不要远距离选点。"
    else:
        max_picks = 8 if "特种兵" in pace else (4 if "闲逛" in pace else 5)

    user = f"""用户需求: {user_input}
意图分析:
- 偏好类别: {json.dumps(intent.get('preferred_categories', []), ensure_ascii=False)}
- 场景关键词: {json.dumps(intent.get('scene_requirements', []), ensure_ascii=False)}
- 预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
- 节奏: {pace}
- 群体: {intent.get('group', {}).get('type', '未知')}
- 人数: {intent.get('group', {}).get('size', 2)}
- 时间: {json.dumps(intent.get('time', {}), ensure_ascii=False)}

候选POI（{len(sampled)}个，按类别分层抽样）:
{json.dumps(poi_summaries, ensure_ascii=False)}
{feedback_hint}
请选出{max_picks}个最合适的景点。"""

    result = await _llm_decide(system, user)
    proposals = _match_poi_picks(result.get("picks", []) if result else [], candidates) if result and "picks" in result else []

    # ── 降级：智能规则引擎（非简单fallback） ──
    if not proposals:
        proposals = _smart_poi_selection(candidates, intent, user_input)

    return {"proposals": proposals, "errors": errors}


def _build_distance_matrix(coords: list[tuple]) -> list[list[float]]:
    """计算pairwise距离矩阵。"""
    n = len(coords)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _haversine_km(coords[i][1], coords[i][2], coords[j][1], coords[j][2])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def _find_largest_cluster(dist_matrix: list[list[float]], threshold: float = 10.0) -> set[int]:
    """找到最大地理簇。"""
    n = len(dist_matrix)
    best_cluster: set[int] = set()
    for i in range(n):
        cluster = {j for j in range(n) if dist_matrix[i][j] < threshold}
        cluster.add(i)
        if len(cluster) > len(best_cluster):
            best_cluster = cluster
    return best_cluster


def _find_replacement(outlier_name: str, selected_names: set[str], all_candidates: list[dict], center_lat: float, center_lng: float, max_dist: float = 10.0) -> dict | None:
    """为离群POI寻找替换。"""
    best_replacement = None
    best_score = -1.0

    for c in all_candidates:
        name = c.get("name", "")
        cat = c.get("category", "")
        if name in selected_names or name == outlier_name:
            continue
        if cat in _EXCLUDED_POI_CATEGORIES or _is_likely_macau(name) or c.get("rating") is None:
            continue
        lat, lng = c.get("lat", 0), c.get("lng", 0)
        if not lat or not lng:
            continue

        dist = _haversine_km(lat, lng, center_lat, center_lng)
        if dist > max_dist:
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


def _apply_replacements(result: list[dict], outlier_indices: set[int], poi_coords: list[tuple], selected_names: set[str], all_candidates: list[dict], center_lat: float, center_lng: float) -> list[dict]:
    """应用离群POI替换。"""
    for idx in outlier_indices:
        outlier_prop = poi_coords[idx][0]
        outlier_name = outlier_prop.get("content", {}).get("name", "")

        replacement = _find_replacement(outlier_name, selected_names, all_candidates, center_lat, center_lng)
        if replacement:
            for i, p in enumerate(result):
                if p.get("content", {}).get("name", "") == outlier_name:
                    result[i] = _proposal("poi", replacement, 0.65, f"地理聚类替换（原{outlier_name}距簇中心过远，替换为{replacement.get('name', '')}）")
                    selected_names.discard(outlier_name)
                    selected_names.add(replacement.get("name", ""))
                    break

    return result


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

    dist_matrix = _build_distance_matrix(poi_coords)
    best_cluster = _find_largest_cluster(dist_matrix)

    if len(best_cluster) >= len(poi_coords):
        return proposals

    cluster_lats = [poi_coords[i][1] for i in best_cluster]
    cluster_lngs = [poi_coords[i][2] for i in best_cluster]
    center_lat = sum(cluster_lats) / len(cluster_lats)
    center_lng = sum(cluster_lngs) / len(cluster_lngs)

    outlier_indices = set(range(len(poi_coords))) - best_cluster
    selected_names = {p.get("content", {}).get("name", "") for p in proposals}

    return _apply_replacements(list(proposals), outlier_indices, poi_coords, selected_names, all_candidates, center_lat, center_lng)


_EXCLUDED_POI_CATEGORIES = ["住宿", "酒店", "民宿", "餐饮", "美食"]


def _expand_keywords(user_input: str, base_keywords: list[str]) -> list[str]:
    """根据用户输入扩展关键词。"""
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


def _score_poi_candidate(candidate: dict, keywords: list[str], budget: float, group_type: str) -> float:
    """计算POI候选的综合评分。"""
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
    keywords = _expand_keywords(user_input, intent.get("preferred_categories", []))
    budget = intent.get("budget", {}).get("per_person", 500)
    pace = intent.get("pace", "平衡型")
    max_picks = 8 if "特种兵" in pace else (4 if "闲逛" in pace else 5)
    group_type = intent.get("group", {}).get("type", "")

    scored = [(c, _score_poi_candidate(c, keywords, budget, group_type)) for c in candidates if c.get("category", "") not in _EXCLUDED_POI_CATEGORIES]
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


# ═══════════════════════════════════════════════════════════
# 餐饮Agent — LLM感知+决策+行动
# ═══════════════════════════════════════════════════════════


_FOOD_CATEGORIES = ["餐饮", "美食", "小吃", "海鲜", "餐厅", "夜市", "茶餐厅", "甜品", "饮品"]
_FOOD_NAME_KEYWORDS = ["餐厅", "海鲜", "烧", "煲", "粉", "面", "火锅", "烧烤", "夜市", "粥", "蚝", "排档", "甜品", "奶茶", "冰", "茶餐厅", "柠檬", "美食街", "海鲜街", "老街"]
_EXCLUDED_CATEGORIES = ["购物", "酒店", "住宿"]


def _is_food_poi(poi: dict) -> bool:
    """判断POI是否为餐饮类。"""
    cat = poi.get("category", "")
    name = poi.get("name", "")
    if cat in _EXCLUDED_CATEGORIES:
        return False
    if _is_likely_macau(name):
        return False
    if poi.get("rating") is None:
        return False
    return any(kw in cat for kw in _FOOD_CATEGORIES) or any(kw in name for kw in _FOOD_NAME_KEYWORDS)


_FOOD_SUBCATS: dict[str, list[str]] = {
    "海鲜": ["海鲜", "蚝", "鱼排", "渔港"],
    "正餐": ["餐厅", "烧", "煲", "火锅", "烧烤"],
    "小吃": ["粉", "面", "粥", "小吃", "排档"],
    "茶餐厅/甜品": ["茶餐厅", "甜品", "奶茶", "冰", "柠檬", "饮品"],
    "综合美食街": ["夜市", "美食街", "海鲜街", "老街"],
}

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


def _stratified_sample(foods: list[dict], score_fn) -> tuple[list[dict], dict[str, str]]:
    """分层采样：按子类别分组，规则预排top3。"""
    stratified = []
    subcat_map: dict[str, str] = {}
    seen_names: set[str] = set()

    for sub_name, kws in _FOOD_SUBCATS.items():
        bucket = [f for f in foods if any(kw in f.get("name", "") or kw in f.get("category", "") for kw in kws) and f.get("name", "") not in seen_names]
        bucket.sort(key=score_fn, reverse=True)
        for f in bucket[:3]:
            stratified.append(f)
            subcat_map[f.get("name", "")] = sub_name
            seen_names.add(f.get("name", ""))

    return stratified, subcat_map


def _build_food_summaries(stratified: list[dict], subcat_map: dict[str, str]) -> list[dict]:
    """构建给LLM的餐饮摘要。"""
    return [{"name": f.get("name", ""), "type": subcat_map.get(f.get("name", ""), "其他"), "cat": f.get("category", ""), "price": f.get("avg_price", 0), "rating": f.get("rating", 0), "tags": f.get("tags", [])[:3], "lat": round(f.get("lat", 0), 3) if f.get("lat") else None, "lng": round(f.get("lng", 0), 3) if f.get("lng") else None, "reviews": f.get("_ugc_summary", "")} for f in stratified[:15]]


def _build_food_system_prompt(scene_type: str, intent: dict, user_input: str, group_type: str) -> str:
    """构建餐饮LLM系统提示。"""
    if scene_type == "美食型":
        scene_reqs_text = " ".join(intent.get("scene_requirements", []))
        intent_hint = _food_intent_hint(scene_reqs_text, user_input)
        return _FOOD_SYSTEM_PREFIX + f"""
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
选4-5个。只输出JSON。"""

    group_hint = ""
    if group_type == "亲子":
        group_hint = "亲子：选环境好、有儿童餐的；"
    elif group_type == "情侣":
        group_hint = "情侣：选氛围好的特色餐厅；"
    if "特种兵" in user_input:
        group_hint += "特种兵：选快节奏、不用排队的。"

    return _FOOD_SYSTEM_PREFIX + f"""
5. 【群体适配】{group_hint}

输出JSON: {{"picks":[{{"name":"店名","reason":"推荐理由（含与哪个景点就近）","confidence":0.8,"meal_time":"午餐/晚餐"}}]}}
最多选3个。只输出JSON。"""


def _build_food_user_prompt(user_input: str, scene_type: str, intent: dict, group_type: str, poi_locations: list[dict], stratified: list[dict], summaries: list[dict], feedback_hint: str) -> str:
    """构建餐饮LLM用户提示。"""
    return f"""用户需求: {user_input}
场景类型: {scene_type}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
群体: {group_type or '未知'}

用户可能游览的景点位置:
{json.dumps(poi_locations[:10], ensure_ascii=False)}

候选餐厅（{len(stratified)}家，分层采样）:
{json.dumps(summaries, ensure_ascii=False)}
{feedback_hint}
请根据餐厅与景点的坐标距离，推荐最方便的就餐选择。"""


def _match_food_picks(picks_data: list[dict], foods: list[dict]) -> list[dict]:
    """匹配LLM picks到food POI。"""
    matched = []
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
            matched.append(_proposal("food", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐")))
    return matched


async def _reselect_food(system: str, proposals: list[dict], issues: list[str], summaries: list[dict], foods: list[dict]) -> list[dict]:
    """带反馈重选餐饮。"""
    current_info = [f"{p['content']['name']}({_get_food_subcat(p['content']['name'], _FOOD_SUBCATS)})" for p in proposals if p.get("content", {}).get("name")]
    feedback = "\n".join(f"❌ {i}" for i in issues)
    reselect_user = f"""你之前选了: {', '.join(current_info)}

存在的问题:
{feedback}

请从候选餐厅重新选择，确保子类型多样:
{json.dumps(summaries, ensure_ascii=False)}

输出JSON: {{"picks":[{{"name":"店名","reason":"理由","confidence":0.8,"meal_time":"午餐/下午茶/晚餐"}}]}}
不要重复之前的错误。"""

    new_result = await _llm_decide(system, reselect_user)
    if new_result and "picks" in new_result:
        new_proposals = _match_food_picks(new_result["picks"], foods)
        if new_proposals:
            return new_proposals
    return proposals


def _extract_poi_locations(candidates: list[dict], max_count: int = 20) -> list[dict]:
    """提取景点位置信息。"""
    locations = []
    for c in candidates[:max_count]:
        if c.get("category", "") not in ["住宿", "酒店", "民宿", "餐饮", "美食"]:
            lat, lng = c.get("lat", 0), c.get("lng", 0)
            if lat and lng:
                locations.append({"name": c.get("name", ""), "lat": round(lat, 3), "lng": round(lng, 3), "category": c.get("category", "")})
    return locations


def _make_food_rule_score(poi_center: tuple[float, float] | None):
    """创建餐饮规则评分函数。"""
    def _score(f: dict) -> float:
        s = f.get("rating", 0)
        if poi_center:
            lat, lng = f.get("lat", 0), f.get("lng", 0)
            if lat and lng:
                s -= _haversine_km(lat, lng, poi_center[0], poi_center[1]) * 0.05
        return s
    return _score


async def food_agent(state: TravelState) -> dict:
    """餐饮Agent：独立加载全部餐饮数据 → LLM选餐厅 → 提案。"""
    meta = AGENT_META.get("food", {})
    await sse_emit(state, "agent_start", {"agent": "food", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "food", "text": "加载餐饮POI，5子类各取TOP3..."})

    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
    scene_type = state.get("scene_type", "观光型")
    candidates = state.get("candidates", [])

    feedback = state.get("review_feedback", [])
    food_feedback = [f for f in feedback if f.get("agent") == "food"]
    feedback_hint = ""
    if food_feedback:
        hints = "; ".join(f"{f['issue']} → {f['suggestion']}" for f in food_feedback)
        feedback_hint = f"\n\n【上一轮审查反馈，必须据此调整】\n{hints}"

    all_pois = await _load_all_pois()
    target_city = intent.get("city", "珠海")
    foods = [c for c in all_pois if (c.get("city", "") == target_city or not c.get("city")) and _is_food_poi(c)]

    if len(foods) < 3:
        for c in candidates:
            if any(kw in c.get("name", "") for kw in _FOOD_NAME_KEYWORDS) and c not in foods:
                foods.append(c)

    poi_locations = _extract_poi_locations(candidates)
    poi_center = (sum(p["lat"] for p in poi_locations) / len(poi_locations), sum(p["lng"] for p in poi_locations) / len(poi_locations)) if poi_locations else None

    stratified, subcat_map = _stratified_sample(foods, _make_food_rule_score(poi_center))
    summaries = _build_food_summaries(stratified, subcat_map)
    group_type = intent.get("group", {}).get("type", "")

    system = _build_food_system_prompt(scene_type, intent, user_input, group_type)
    user = _build_food_user_prompt(user_input, scene_type, intent, group_type, poi_locations, stratified, summaries, feedback_hint)

    result = await _llm_decide(system, user)
    proposals = _match_food_picks(result.get("picks", []), foods) if result and "picks" in result else []

    for _ in range(2):
        issues = _check_food_diversity_issues(proposals, _FOOD_SUBCATS, scene_type)
        if not issues:
            break
        proposals = await _reselect_food(system, proposals, issues, summaries, foods)

    if not proposals:
        proposals = _smart_food_selection(foods, intent, user_input)

    return {"proposals": proposals}


def _get_food_subcat(name: str, subcat_defs: dict[str, list[str]]) -> str:
    """判断餐饮POI属于哪个子类别。"""
    for sub_name, kws in subcat_defs.items():
        if any(kw in name for kw in kws):
            return sub_name
    return "其他"


def _check_food_diversity_issues(
    proposals: list[dict],
    subcat_defs: dict[str, list[str]],
    scene_type: str,
) -> list[str]:
    """检查餐饮提案的子类别多样性问题。返回问题列表，空=通过。"""
    if len(proposals) < 2:
        return []

    from collections import Counter

    subcats = [
        _get_food_subcat(p.get("content", {}).get("name", ""), subcat_defs) for p in proposals
    ]
    counts = Counter(subcats)
    issues = []

    # 综合美食街最多1个
    street_count = counts.get("综合美食街", 0)
    if street_count > 1:
        street_names = [
            p.get("content", {}).get("name", "")
            for p in proposals
            if _get_food_subcat(p.get("content", {}).get("name", ""), subcat_defs) == "综合美食街"
        ]
        issues.append(
            f"选了{street_count}个综合美食场所（{', '.join(street_names)}），内部已有多种美食，最多选1个"
        )

    # 任何子类不超过2个
    for sub, cnt in counts.items():
        if cnt > 2:
            issues.append(f"{sub}类选了{cnt}个，同类型最多2个")

    # 美食型需要≥3种子类
    if scene_type == "美食型" and len(set(subcats)) < 3:
        issues.append(
            f"只覆盖{len(set(subcats))}种子类（{', '.join(set(subcats))}），美食路线需要≥3种不同子类"
        )

    return issues


def _smart_food_selection(foods: list[dict], intent: dict, user_input: str) -> list[dict]:
    """智能餐饮选择。"""
    if not foods:
        return [_proposal("food", {"name": "（无餐饮数据）", "category": "餐饮"}, 0.2, "无餐饮POI")]

    text = user_input.lower()
    budget = intent.get("budget", {}).get("per_person", 500)
    keywords = []
    if "海鲜" in text:
        keywords.extend(["海鲜", "蚝", "鱼"])
    if "本地" in text or "特色" in text:
        keywords.extend(["本地", "特色", "传统", "老字号"])
    if "小吃" in text:
        keywords.extend(["小吃", "街边", "排档"])

    scored = []
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


# ═══════════════════════════════════════════════════════════
# 住宿Agent — LLM感知+决策+行动
# ═══════════════════════════════════════════════════════════


_HOTEL_KEYWORDS = ["住宿", "酒店", "民宿"]
_HOTEL_NAME_KEYWORDS = ["酒店", "民宿", "宾馆", "公寓"]


async def _check_need_hotel(user_input: str) -> bool:
    """判断是否需要住宿。"""
    if any(kw in user_input for kw in ["晚", "两", "二", "三天", "住宿", "酒店", "民宿", "二日", "两日", "过夜"]):
        return True
    judge = await _llm_decide('判断用户是否需要住宿。输出JSON: {"need":true/false,"reason":"理由"}', f"用户输入: {user_input}")
    return bool(judge and judge.get("need"))


def _filter_hotels(all_pois: list[dict], candidates: list[dict]) -> list[dict]:
    """筛选住宿POI并去重。"""
    hotel_sources = all_pois + candidates
    hotels = [c for c in hotel_sources if any(kw in c.get("category", "") for kw in _HOTEL_KEYWORDS) or any(kw in c.get("name", "") for kw in _HOTEL_NAME_KEYWORDS)]
    seen: set[str] = set()
    unique = []
    for h in hotels:
        name = h.get("name", "")
        if name not in seen:
            seen.add(name)
            unique.append(h)
    return unique


def _build_hotel_summaries(hotels: list[dict], max_count: int = 20) -> list[dict]:
    """构建住宿摘要。"""
    return [{"name": h.get("name", ""), "price": h.get("avg_price", 0), "rating": h.get("rating", 0), "tags": h.get("tags", [])[:3], "area": h.get("tags", [""])[0] if h.get("tags") else "", "lat": round(h.get("lat", 0), 3) if h.get("lat") else None, "lng": round(h.get("lng", 0), 3) if h.get("lng") else None} for h in hotels[:max_count]]


async def hotel_agent(state: TravelState) -> dict:
    """住宿Agent：感知是否需要住宿 → LLM选酒店 → 提案。"""
    meta = AGENT_META.get("hotel", {})
    await sse_emit(state, "agent_start", {"agent": "hotel", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "hotel", "text": "分析住宿需求..."})

    candidates = state.get("candidates", [])
    intent = state.get("user_intent", {})
    user_input = str(state.get("user_input", ""))

    if not await _check_need_hotel(user_input):
        return {"proposals": []}

    all_pois = await _load_all_pois()
    target_city = intent.get("city", "珠海")
    all_pois = [p for p in all_pois if p.get("city", "") == target_city or not p.get("city")]
    hotels = _filter_hotels(all_pois, candidates)

    poi_locations = _extract_poi_locations(candidates, max_count=15)
    summaries = _build_hotel_summaries(hotels)

    group_type = intent.get("group", {}).get("type", "")
    group_hint = ""
    if group_type == "亲子":
        group_hint = "优先选有亲子房/儿童设施的酒店，位置靠近主要景点（减少带小孩的交通时间）。"
    elif group_type == "情侣":
        group_hint = "优先选有海景/景观房的酒店，位置选安静浪漫的区域。"
    elif group_type == "商务":
        group_hint = "优先选交通便利、靠近商业区的酒店。"

    # ── 决策：LLM ──
    system = f"""你是住宿推荐专家。根据用户需求从候选酒店中挑选最合适的。

考虑因素：
1. 预算合理性（不超预算）
2. 评分和口碑（优先高评分）
3. 位置便利性：通过坐标判断，选离主要景点最近的区域
4. {group_hint if group_hint else '群体适配'}

输出JSON: {{"picks":[{{"name":"酒店名","reason":"推荐理由（含位置优势）","confidence":0.8}}]}}
最多选2个。只输出JSON。"""

    user = f"""用户需求: {user_input}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
群体: {group_type or '未知'}

用户可能游览的景点:
{json.dumps(poi_locations[:8], ensure_ascii=False)}

候选酒店（含坐标）:
{json.dumps(summaries, ensure_ascii=False)}

请根据酒店与景点的坐标距离推荐。"""

    result = await _llm_decide(system, user)

    proposals = []
    if result and "picks" in result:
        name_map = {h.get("name", ""): h for h in hotels}
        for pick in result["picks"]:
            name = pick.get("name", "")
            content = name_map.get(name)
            if not content:
                for h in hotels:
                    if name in h.get("name", "") or h.get("name", "") in name:
                        content = h
                        break
            if content:
                proposals.append(
                    _proposal(
                        "hotel", content, pick.get("confidence", 0.7), pick.get("reason", "LLM推荐")
                    )
                )

    # 降级
    if not proposals and hotels:
        scored = sorted(hotels, key=lambda h: h.get("rating", 4.0), reverse=True)
        for h in scored[:2]:
            proposals.append(_proposal("hotel", h, 0.5, "规则引擎：评分排序"))

    return {"proposals": proposals}


# ═══════════════════════════════════════════════════════════
# 交通Agent — LLM评估交通+路线串联
# ═══════════════════════════════════════════════════════════


async def traffic_agent(state: TravelState) -> dict:
    """交通Agent：分析候选POI分布 → LLM规划交通方案 → 提案。"""
    meta = AGENT_META.get("traffic", {})
    await sse_emit(state, "agent_start", {"agent": "traffic", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "traffic", "text": "分析POI地理分布..."})
    # ── 感知 ──
    candidates = state.get("candidates", [])
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")

    # 提取非住宿POI的位置信息（扩大到30个，确保高质量POI覆盖）
    poi_locs = []
    for c in candidates[:30]:
        if c.get("category", "") not in ["住宿", "酒店", "民宿"]:
            poi_locs.append(
                {
                    "name": c.get("name", ""),
                    "lat": c.get("lat", 0),
                    "lng": c.get("lng", 0),
                    "category": c.get("category", ""),
                    "tags": c.get("tags", [])[:3],
                }
            )

    # 计算POI之间的距离矩阵（关键景点之间）
    distances = []
    for i, p1 in enumerate(poi_locs[:12]):
        for j, p2 in enumerate(poi_locs[:12]):
            if i < j and p1.get("lat") and p2.get("lat"):
                d = _haversine_km(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
                if d > 0.5:  # 只记录有意义的距离
                    distances.append({"from": p1["name"], "to": p2["name"], "km": round(d, 1)})

    # ── 构建场景感知prompt ──
    group_type = intent.get("group", {}).get("type", "")
    pace = intent.get("pace", "平衡型")
    scene_reqs = intent.get("scene_requirements", [])

    scene_hint = ""
    if group_type == "亲子":
        scene_hint = """
【亲子路线设计】
- 上午精力好，安排主要景点（如海洋公园、动物园）
- 午后孩子易疲倦，安排室内/轻松项目
- 景点间距要短（带小孩不宜>5km/次）
- 避开交通高峰时段"""
    elif group_type == "情侣":
        scene_hint = """
【情侣路线设计】
- 安排水畔/海滨漫步路线（情侣路沿线最佳）
- 下午安排咖啡厅或艺术区（轻松浪漫氛围）
- 傍晚安排观景台/海边看日落
- 晚上安排夜景好的地点"""
    elif group_type == "朋友":
        scene_hint = """
【朋友路线设计】
- 可安排较紧凑的打卡路线
- 午餐和晚餐穿插不同特色街区
- 可以走主题路线（美食街、文创区）"""
    else:
        scene_hint = "\n- 平衡地理效率和游览体验"

    system = f"""你是城市旅行路线规划专家。你需要设计一条高质量的一日游路线。

你的核心任务：
1. 【地理连贯】按区域聚类排序，避免来回折返（跨区移动>10km会严重降低体验）
2. 【时间节奏】遵循情绪曲线设计：
   - 上午(9-12点)：精力充沛，安排主力景点（户外/特色/地标）
   - 午餐(11:30-13:00)：选景点附近的特色餐饮
   - 下午(13-17点)：安排次级景点或室内（午后适合轻松活动）
   - 傍晚(17-19点)：安排观景/休闲（海边/公园/观景台）
   - 晚上(19点后)：如需要，安排夜景/美食/娱乐
3. 【场景适配】{scene_hint}
4. 【高效交通】同区域景点连走，跨区域利用公共交通干线

输出JSON:
{{"mode":"推荐交通方式","route_suggestion":"路线设计思路（2-3句话）","estimated_total_time":"总交通耗时(分钟)","tips":"交通建议","suggested_order":["景点1","景点2",...],"confidence":0.8}}

关键：suggested_order必须是最优游览顺序，综合考虑地理距离、时间节奏和用户体验。
只输出JSON。"""

    user = f"""用户需求: {user_input}
群体: {group_type or '未知'}
节奏: {pace}
场景要求: {json.dumps(scene_reqs, ensure_ascii=False) if scene_reqs else '无特殊要求'}
城市: {intent.get('city', '珠海')}

景点位置:
{json.dumps(poi_locs, ensure_ascii=False)}

景点间距离(>0.5km):
{json.dumps(distances[:25], ensure_ascii=False)}

请设计最优路线顺序。注意：优先地理连贯（同区域连走），其次考虑时间节奏。"""

    result = await _llm_decide(system, user)

    if result:
        result["distances"] = distances
        return {
            "proposals": [
                _proposal("traffic", result, result.get("confidence", 0.7), "LLM交通规划")
            ]
        }

    # 降级：基于距离矩阵计算最近邻顺序
    if poi_locs and distances:
        order = _nearest_neighbor_order(poi_locs)
        return {
            "proposals": [
                _proposal(
                    "traffic",
                    {
                        "mode": "公共交通+步行",
                        "suggested_order": order,
                        "estimated_total_time": 60,
                        "distances": distances,
                    },
                    0.5,
                    "规则引擎：最近邻排序",
                )
            ]
        }

    return {
        "proposals": [
            _proposal(
                "traffic", {"mode": "公共交通", "estimated_total_time": 60}, 0.4, "默认交通方案"
            )
        ]
    }


def _nearest_neighbor_order(poi_locs: list[dict]) -> list[str]:
    """最近邻算法排序景点。"""
    if not poi_locs:
        return []
    order = [poi_locs[0]["name"]]
    remaining = list(range(1, len(poi_locs)))
    current = 0
    while remaining:
        best_idx = None
        best_dist = float("inf")
        for idx in remaining:
            p = poi_locs[idx]
            c = poi_locs[current]
            if p.get("lat") and c.get("lat"):
                d = _haversine_km(p["lat"], p["lng"], c["lat"], c["lng"])
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
        if best_idx is not None:
            order.append(poi_locs[best_idx]["name"])
            remaining.remove(best_idx)
            current = best_idx
        else:
            break
    return order


# ═══════════════════════════════════════════════════════════
# 天气Agent — LLM评估天气影响
# ═══════════════════════════════════════════════════════════


async def weather_agent(state: TravelState) -> dict:
    """天气Agent：LLM评估天气对行程的影响。"""
    meta = AGENT_META.get("weather", {})
    await sse_emit(state, "agent_start", {"agent": "weather", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "weather", "text": "评估天气对行程影响..."})
    # ── 感知 ──
    state.get("user_intent", {})
    user_input = state.get("user_input", "")
    candidates = state.get("candidates", [])

    # 识别户外/室内POI
    outdoor_pois = []
    indoor_pois = []
    for c in candidates[:15]:
        name = c.get("name", "")
        tags = c.get("tags", []) + c.get("_scene_tags", [])
        cat = c.get("category", "")
        is_outdoor = any(kw in str(tags) for kw in ["户外", "公园", "海滨", "沙滩", "徒步", "自然"])
        is_indoor = any(kw in str(tags) for kw in ["室内", "博物馆", "展览", "科学馆"])
        if is_outdoor or cat in ["公园", "自然"]:
            outdoor_pois.append(name)
        if is_indoor or "科学馆" in name or "博物馆" in name:
            indoor_pois.append(name)

    # 动态获取当前月份
    from datetime import datetime

    now = datetime.now()
    month = now.month
    season_map = {
        1: "冬季",
        2: "冬季",
        3: "春季",
        4: "春季",
        5: "夏季",
        6: "夏季",
        7: "夏季",
        8: "夏季",
        9: "秋季",
        10: "秋季",
        11: "秋季",
        12: "冬季",
    }
    season = season_map.get(month, "未知")

    # ── 决策：LLM ──
    system = """你是天气评估专家。分析天气对旅游行程的影响。

要求：
1. 根据当前月份评估珠海的天气状况（温度、降雨概率、日照）
2. 逐个分析户外POI的适宜性和最佳游览时段
3. 给出具体的行程调整建议（哪个POI放上午、哪个需要备选）

输出JSON: {"condition":"天气状况","temperature":"温度范围","outdoor_ok":true/false,"advice":"具体行程调整建议","rain_probability":0.3,"indoor_alternatives":["室内备选"],"confidence":0.8}
只输出JSON。"""

    user = f"""用户场景: {user_input}
当前月份: {month}月（{season}）
城市: 珠海（华南沿海城市）
户外POI: {', '.join(outdoor_pois[:5]) if outdoor_pois else '无'}
室内POI: {', '.join(indoor_pois[:5]) if indoor_pois else '无'}"""

    result = await _llm_decide(system, user)

    if result:
        return {
            "proposals": [
                _proposal("weather", result, result.get("confidence", 0.8), "LLM天气评估")
            ]
        }

    # 降级：基于季节的规则评估
    return {
        "proposals": [
            _proposal(
                "weather",
                {
                    "condition": "多云",
                    "temperature": "26-32°C",
                    "outdoor_ok": True,
                    "advice": f"{month}月珠海{season}气候，建议上午户外下午室内，注意防晒防暑",
                    "rain_probability": 0.35,
                    "indoor_alternatives": indoor_pois[:3] if indoor_pois else ["长隆海洋科学馆"],
                },
                0.6,
                "规则引擎：季节性天气评估",
            )
        ]
    }


# ═══════════════════════════════════════════════════════════
# 本地达人Agent — LLM生成本地建议
# ═══════════════════════════════════════════════════════════


async def local_expert_agent(state: TravelState) -> dict:
    """本地达人Agent：LLM结合POI数据给本地特色建议。"""
    meta = AGENT_META.get("local_expert", {})
    await sse_emit(state, "agent_start", {"agent": "local_expert", **meta})
    await sse_emit(
        state, "agent_thinking", {"agent": "local_expert", "text": "搜索非热门高评地点..."}
    )
    # ── 感知 ──
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")
    candidates = state.get("candidates", [])

    # 获取小众/高评分POI
    hidden_gems = []
    for c in candidates:
        llm_q = c.get("_llm_quality", {})
        tags = c.get("tags", [])
        rating = c.get("rating", 0)
        # 小众但高质量
        if rating >= 4.0 and (llm_q.get("score", 0) >= 7 or any("小众" in str(t) for t in tags)):
            hidden_gems.append(
                {
                    "name": c.get("name", ""),
                    "category": c.get("category", ""),
                    "rating": rating,
                    "tags": tags[:3],
                }
            )

    # 获取用户可能已选的热门POI（用于去重）
    popular_names = []
    for c in candidates[:15]:
        if c.get("rating") and c.get("rating", 0) >= 4.0:
            popular_names.append(c.get("name", ""))

    group_type = intent.get("group", {}).get("type", "")
    scene_reqs = intent.get("scene_requirements", [])

    # ── 决策：LLM ──
    system = f"""你是珠海本地达人，熟悉珠海的每一个角落。根据用户需求给出本地特色建议。

要求：
1. 推荐只有本地人才知道的宝藏地点（不要重复推荐热门景点）
2. 结合小众POI数据给出具体推荐
3. 给出实用的本地贴士（避坑、最佳时间等）
4. {f'场景适配：用户想{", ".join(scene_reqs)}，推荐符合场景的小众地点' if scene_reqs else ''}
5. {f'群体适配：{group_type}群体的特殊需求' if group_type else ''}

输出JSON: {{"tips":[{{"name":"推荐名","type":"类型","why":"为什么推荐","best_time":"最佳时间"}}]],"secrets":["隐藏的好去处"],"local_advice":"本地人建议","confidence":0.75}}
只输出JSON。"""

    user = f"""用户需求: {user_input}
群体: {group_type or '未知'}
偏好: {json.dumps(intent.get('preferred_categories', []), ensure_ascii=False)}
场景要求: {json.dumps(scene_reqs, ensure_ascii=False) if scene_reqs else '无'}
预算: {intent.get('budget', {}).get('per_person', '不限')}元

已选热门景点（不要再推荐这些）:
{', '.join(popular_names[:10]) if popular_names else '待定'}

小众POI数据:
{json.dumps(hidden_gems[:10], ensure_ascii=False) if hidden_gems else '无小众数据'}"""

    result = await _llm_decide(system, user)

    if result:
        return {
            "proposals": [
                _proposal("local_expert", result, result.get("confidence", 0.75), "LLM本地建议")
            ]
        }

    # 降级：基于数据的小众推荐
    gems = (
        hidden_gems[:3]
        if hidden_gems
        else [{"name": "唐家湾古镇", "type": "小众景点", "why": "人少景美，岭南古村落"}]
    )
    return {
        "proposals": [
            _proposal(
                "local_expert",
                {
                    "tips": [
                        {
                            "name": g.get("name", ""),
                            "type": g.get("type", g.get("category", "")),
                            "why": g.get("why", "小众推荐"),
                        }
                        for g in gems
                    ],
                    "secrets": [g.get("name", "") for g in gems],
                    "local_advice": "珠海天气湿热，建议早出晚归避开正午高温",
                },
                0.4,
                "规则引擎：小众POI推荐",
            )
        ]
    }


# ═══════════════════════════════════════════════════════════
# 保险Agent — LLM评估风险
# ═══════════════════════════════════════════════════════════


async def insurance_agent(state: TravelState) -> dict:
    """保险Agent：LLM直接分析行程风险。"""
    meta = AGENT_META.get("insurance", {})
    await sse_emit(state, "agent_start", {"agent": "insurance", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "insurance", "text": "评估行程风险..."})
    # ── 感知 ──
    user_input = str(state.get("user_input", ""))
    intent = state.get("user_intent", {})
    proposals = state.get("proposals", [])

    # 收集行程信息给LLM（不做if/else预处理）
    poi_names = [p.get("content", {}).get("name", "") for p in proposals if p.get("agent") == "poi"]
    food_names = [
        p.get("content", {}).get("name", "") for p in proposals if p.get("agent") == "food"
    ]
    total_cost = sum(
        p.get("content", {}).get("avg_price", 0)
        for p in proposals
        if p.get("agent") in ["poi", "food", "hotel"]
    )

    # 收集住宿信息
    hotel_names = [
        p.get("content", {}).get("name", "") for p in proposals if p.get("agent") == "hotel"
    ]

    # ── 决策：LLM直接分析 ──
    system = """你是旅行保险顾问。请直接分析用户行程的风险因素并给出保险建议。

你需要自己判断：
1. 根据景点名称推断是否有高风险活动（海滩游泳、登山徒步、海上项目、高空项目等）
2. 参与者构成（儿童/老人需要额外医疗保障）
3. 花费水平和预算是否匹配（超预算本身也是风险）
4. 多日行程的额外风险（住宿安全、行李丢失等）
5. 季节性风险（夏季防暑防台风、冬季防寒等）

输出JSON: {"risk_level":"low/medium/high","risk_factors":["你识别的风险因素"],"recommended_insurance":"推荐险种","coverage":"保额建议","notes":["注意事项"],"confidence":0.7}
只输出JSON。"""

    user = f"""用户行程: {user_input}
群体: {intent.get('group', {}).get('type', '未知')}
预算: {intent.get('budget', {}).get('per_person', '不限')}元
计划景点: {', '.join(poi_names[:8]) if poi_names else '待定'}
计划餐饮: {', '.join(food_names[:4]) if food_names else '待定'}
{'住宿: ' + ', '.join(hotel_names[:3]) if hotel_names else '无需住宿（一日游）'}
预估花费: {total_cost}元"""

    result = await _llm_decide(system, user)

    if result:
        return {
            "proposals": [
                _proposal("insurance", result, result.get("confidence", 0.7), "LLM风险评估")
            ]
        }

    # 降级：基于花费的简单规则
    level = "low"
    if total_cost > 1000:
        level = "medium"
    if total_cost > 2000:
        level = "high"
    return {
        "proposals": [
            _proposal(
                "insurance",
                {
                    "risk_level": level,
                    "risk_factors": [f"预估花费{total_cost}元"],
                    "recommended_insurance": "综合旅行险" if level != "low" else "基础旅行险",
                    "coverage": "50万" if level == "high" else "20万",
                    "notes": ["注意防晒防暑", "保管好个人物品"],
                },
                0.5,
                f"规则降级：{level}风险",
            )
        ]
    }


# ═══════════════════════════════════════════════════════════
# 协商Agent — 基于其他Agent提案生成反提案
# ═══════════════════════════════════════════════════════════


async def negotiation_agent(state: TravelState) -> dict:
    """协商Agent：读取所有提案 → LLM分析冲突 → 生成优化建议。"""
    meta = AGENT_META.get("negotiation", {})
    await sse_emit(state, "agent_start", {"agent": "negotiation", **meta})
    await sse_emit(
        state, "agent_thinking", {"agent": "negotiation", "text": "读取提案，分析冲突..."}
    )
    proposals = state.get("proposals", [])
    intent = state.get("user_intent", {})
    user_input = state.get("user_input", "")

    if not proposals:
        return {"counter_proposals": []}

    # 按agent分类提案，包含完整信息
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
                "lat": content.get("lat", 0),
                "lng": content.get("lng", 0),
                "confidence": p.get("confidence", 0),
            }
        )

    system = """你是行程优化顾问。基于各Agent的提案，分析是否存在冲突或优化空间。

你需要检查：
1. 餐厅是否在景点附近（比较lat/lng坐标）
2. 景点类型是否过于单一（多样性）
3. 预算是否合理（总花费vs用户预算）
4. 是否有遗漏的重要景点
5. 路线地理连续性是否合理（坐标是否跳跃）

输出JSON: {"suggestions":[{"type":"优化类型","description":"具体建议","affected_agents":["相关Agent"],"priority":"high/medium/low"}],"confidence":0.7}
只输出JSON。没有需要优化的则输出 {"suggestions":[],"confidence":0.8}"""

    user = f"""用户需求: {user_input}
预算: {intent.get('budget', {}).get('per_person', '不限')}元/人
群体: {intent.get('group', {}).get('type', '未知')}

各Agent提案详情:
{json.dumps(proposal_details, ensure_ascii=False)}"""

    result = await _llm_decide(system, user)

    if result and result.get("suggestions"):
        msgs = []
        for s in result["suggestions"]:
            msgs.append(
                {
                    "type": s.get("type", ""),
                    "from": "negotiation",
                    "message": s.get("description", ""),
                    "priority": s.get("priority", "low"),
                }
            )
        return {"negotiation_msgs": msgs}

    return {"counter_proposals": []}
