"""元规则防火墙节点：解析意图 + 加载数据 + 硬约束预筛。

对应架构Layer 1+2：用户输入 → 元规则防火墙。

═════════════════════════════════════════════════════════════
  架构决策记录（ADR）— 别瞎改，每条都是踩过坑的
═════════════════════════════════════════════════════════════

ADR-R1: _fix_food_categories()必须在agent之前执行
  - POI数据里"美食街"category=文化, "湾仔海鲜街"category=文化
  - 不修正的话poi_agent会当文化景点选中, 同时food_agent也能选 → 重复
  - 通过名称关键词识别, 把category覆盖为"餐饮"
  - 必须在filter_candidates之前, 否则过滤逻辑用的是错误的category

ADR-R2: _ensure_key_pois_llm()用LLM补核心景点
  - 纯规则过滤会漏掉用户隐含需要的核心景点
  - 如"带孩子去长隆"可能被预算过滤砍掉长隆
  - LLM判断更准确, 但多一次API调用

ADR-R3: 场景分类用规则不用LLM
  - _classify_scene()基于关键词, 不额外调LLM
  - 5种场景: 美食型 > 目的地型 > 特种兵型 > 休闲型 > 观光型(默认)
  - 优先级顺序重要: "美食一日游"应是美食型不是观光型

ADR-R4: intent_parser超时重试3次再降级
  - 之前1次超时就fallback到规则匹配, 质量很差
  - 规则匹配的意图解析会误判: 如"情侣一日游"可能被归为"朋友"
  - LLM解析质量远高于规则, 值得多等几秒
"""

from __future__ import annotations

from backend.agents_v3.firewall.meta_rule_firewall import check_hard_rules
from backend.agents_v3.state import TravelState, AGENT_META, sse_emit


async def rule_guard(state: TravelState) -> dict:
    """入口节点：解析意图 → 加载POI → 硬约束预筛。"""
    meta = AGENT_META.get("rule_guard", {})
    await sse_emit(state, "agent_start", {"agent": "rule_guard", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "rule_guard", "text": "解析自然语言意图..."})

    user_input = state.get("user_input", "")
    errors = []

    # ── 意图解析 ──
    try:
        from backend.services.intent_parser import parse_intent
        user_intent = await parse_intent(user_input)
    except Exception as e:
        errors.append(f"意图解析失败: {e}")
        user_intent = _fallback_intent(user_input)

    # ── 从美团API加载POI ──
    await sse_emit(state, "agent_thinking", {"agent": "rule_guard", "text": f"加载POI数据，硬约束预筛..."})
    try:
        from backend.agents_v3.meituan_client import fetch_pois
        all_pois = await fetch_pois()
    except Exception as e:
        errors.append(f"美团API不可用: {e}")
        # 降级到本地JSON
        try:
            from backend.services.data_service import get_data
            all_pois = get_data()
            if isinstance(all_pois, dict):
                all_pois = list(all_pois.values())
            elif not isinstance(all_pois, list):
                all_pois = []
        except Exception as e2:
            errors.append(f"本地数据也不可用: {e2}")
            all_pois = []

    # ── 修正被误分类的美食POI ──
    _fix_food_categories(all_pois)

    # ── 只保留目标城市POI ──
    target_city = user_intent.get("city", "珠海")
    if all_pois:
        zhuhai_pois = [p for p in all_pois if p.get("city", "") == target_city or not p.get("city")]
        if len(zhuhai_pois) >= 10:
            all_pois = zhuhai_pois

    # ── 预筛（宽松：只做最基本过滤，让Agent自己选） ──
    candidates = all_pois
    if all_pois:
        try:
            from backend.services.filters import filter_candidates
            candidates = filter_candidates(all_pois, user_intent)
        except Exception:
            candidates = all_pois[:120]

        # 用LLM判断需要哪些核心景点，确保在候选池中
        candidates = await _ensure_key_pois_llm(candidates, all_pois, user_input, user_intent)

    # ── 元规则防火墙检查 ──
    rule_violations = check_hard_rules(user_intent, candidates)

    # scene_type 由 expert_router 设置，这里不设置

    await sse_emit(state, "agent_result", {"agent": "rule_guard", "summary": f"意图已解析，{len(candidates)}个候选POI"})

    return {
        "user_intent": user_intent,
        "candidates": candidates,
        "rule_violations": rule_violations,
        "meta_rules": [],
        "errors": errors,
    }


# 珠海核心景点（LLM降级时使用）
_KEY_POIS = [
    "长隆海洋王国", "海洋王国", "横琴长隆海洋科学馆", "长隆马戏城",
    "珠海渔女", "情侣路", "外伶仃岛", "淇澳岛", "圆明新园",
    "海滨泳场", "海滨公园", "野狸岛", "日月贝", "珠海大剧院",
    "港珠澳大桥", "东澳岛", "金海滩", "飞沙滩", "御温泉",
    "梅华海鲜城", "新海利", "湾仔海鲜街",
]


async def _ensure_key_pois_llm(
    candidates: list[dict],
    all_pois: list[dict],
    user_input: str,
    intent: dict,
) -> list[dict]:
    """用LLM判断用户意图隐含需要哪些核心景点，确保它们在候选池中。"""
    import json
    import os

    from openai import AsyncOpenAI

    cand_names = {c.get("name", "") for c in candidates}

    # 从全部POI中取高评分的知名景点（供LLM选择）
    well_known = [
        {"name": p.get("name", ""), "category": p.get("category", ""), "rating": p.get("rating", 0)}
        for p in all_pois
        if p.get("rating") and p.get("rating", 0) >= 4.0
        and p.get("category", "") not in ["住宿", "酒店", "民宿"]
    ][:80]

    group_type = intent.get("group", {}).get("type", "未知")

    prompt = f"""根据用户的出行需求，判断以下哪些知名景点/地点应该在候选池中（即使用户没有直接点名，只要是该需求下理应包含的）。

用户需求: {user_input}
场景类型: {intent.get('scene_requirements', [])}
偏好类别: {intent.get('preferred_categories', [])}
群体: {group_type}

已知知名景点:
{json.dumps(well_known, ensure_ascii=False)}

当前候选池中已有的:
{json.dumps(list(cand_names)[:30], ensure_ascii=False)}

请选出必须在候选池中但目前缺失的景点名。输出JSON: {{"must_have": ["景点名1", "景点名2"]}}
如果候选池已经足够，输出: {{"must_have": []}}
只输出JSON。"""

    try:
        client = AsyncOpenAI(
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        )
        resp = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
        text = resp.choices[0].message.content or ""
        result = json.loads(text)
        must_have = result.get("must_have", [])
    except Exception:
        # LLM失败降级到正则
        must_have = _fallback_must_have(user_input)

    # 把缺失的加入候选池
    missing = []
    for poi in all_pois:
        name = poi.get("name", "")
        if name in cand_names:
            continue
        for needed_name in must_have:
            if needed_name in name or name in needed_name:
                missing.append(poi)
                cand_names.add(name)
                break

    if missing:
        candidates = list(candidates) + missing

    return candidates


def _fallback_must_have(user_input: str) -> list[str]:
    """LLM不可用时降级：关键词匹配。"""
    needed = set()
    for kp in _KEY_POIS:
        if kp in user_input:
            needed.add(kp)
    if not needed:
        needed = {"长隆海洋王国", "珠海渔女", "情侣路", "圆明新园", "海滨泳场"}
    return list(needed)


def _fallback_intent(user_input: str) -> dict:
    """意图解析降级。"""
    text = user_input.lower()
    intent = {
        "city": "珠海",
        "time": {"period": "全天", "start": "09:00", "end": "20:00"},
        "budget": {"per_person": 500, "type": "弹性"},
        "group": {"size": 2, "type": "情侣"},
        "preferences": {"culture": 0.5, "food": 0.5, "nature": 0.5, "social": 0.3},
        "pace": "平衡型",
        "hard_constraints": [],
        "preferred_categories": ["景点"],
        "_raw_input": user_input,
    }

    if any(kw in text for kw in ["亲子", "孩子", "儿童"]):
        intent["group"] = {"size": 3, "type": "亲子"}
        intent["hard_constraints"].append("accessible")
        intent["preferred_categories"] = ["娱乐", "景点"]
    elif any(kw in text for kw in ["父母", "养老", "老人"]):
        intent["group"] = {"size": 3, "type": "退休"}
        intent["pace"] = "闲逛型"
        intent["preferred_categories"] = ["公园", "景点"]
    elif "朋友" in text:
        intent["group"] = {"size": 4, "type": "朋友"}

    if any(kw in text for kw in ["穷", "便宜", "省钱"]):
        intent["budget"] = {"per_person": 200, "type": "硬约束"}
    elif any(kw in text for kw in ["豪华", "高档"]):
        intent["budget"] = {"per_person": 1500, "type": "弹性"}

    if any(kw in text for kw in ["美食", "海鲜", "吃"]):
        intent["preferred_categories"] = ["餐饮"]
        intent["preferences"]["food"] = 0.9
    elif "特种兵" in text:
        intent["pace"] = "特种兵型"
        intent["preferred_categories"] = ["景点", "娱乐"]
    elif "拍照" in text:
        intent["preferred_categories"] = ["景点", "文化"]

    return intent


# 名称中包含这些关键词的POI，即使category不是餐饮也应归为餐饮
_FOOD_NAME_KWS = [
    "美食街", "海鲜街", "小吃街", "美食城", "美食广场", "食街",
    "夜市", "大排档", "海鲜城", "海鲜市场", "水产市场",
]
# 名称中包含这些关键词的，不是景点而是餐饮
_EXCLUDE_FROM_POI = [
    "餐厅", "茶餐厅", "火锅", "烧烤", "甜品", "奶茶", "咖啡",
    "粉麵", "粥", "点心", "早茶", "烧腊", "煲仔",
]


def _fix_food_categories(pois: list[dict]) -> None:
    """修正被误分类的美食POI：通过名称识别，把category覆盖为餐饮。"""
    food_cats = {"餐饮", "美食", "小吃", "夜市小吃"}
    for p in pois:
        cat = p.get("category", "")
        if cat in food_cats:
            continue
        name = p.get("name", "")
        for kw in _FOOD_NAME_KWS:
            if kw in name:
                p["_original_category"] = cat
                p["category"] = "餐饮"
                break


# _classify_scene 已移入 expert_router.py（作为LLM降级fallback）
