"""元规则防火墙节点：解析意图 + 加载数据 + 硬约束预筛。

对应架构Layer 1+2：用户输入 → 元规则防火墙。
"""

from __future__ import annotations

from backend.agents_v3.firewall.meta_rule_firewall import check_hard_rules
from backend.agents_v3.state import TravelState


async def rule_guard(state: TravelState) -> dict:
    """入口节点：解析意图 → 加载POI → 硬约束预筛。"""
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

    # ── 场景分类（规则，不额外调LLM） ──
    scene_type = _classify_scene(user_input, user_intent)

    return {
        "user_intent": user_intent,
        "scene_type": scene_type,
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


def _classify_scene(user_input: str, intent: dict) -> str:
    """基于规则的场景分类（不额外调LLM）。

    返回: 美食型 | 目的地型 | 特种兵型 | 休闲型 | 观光型（默认）
    """
    text = user_input.lower()
    pace = intent.get("pace", "平衡型")
    prefs = intent.get("preferred_categories", [])
    scene_reqs = intent.get("scene_requirements", [])

    # 优先级1：美食主题
    food_kws = ["美食", "海鲜", "吃", "小吃", "特色菜", "夜市", "吃货"]
    if any(kw in text for kw in food_kws) or "餐饮" in prefs:
        return "美食型"

    # 优先级2：目的地型（指定了大景区）
    dest_kws = ["长隆", "海洋王国", "海洋科学馆", "圆明新园", "御温泉", "梦幻水城"]
    if any(kw in text for kw in dest_kws):
        return "目的地型"

    # 优先级3：特种兵
    if "特种兵" in text or "特种兵" in pace:
        return "特种兵型"

    # 优先级4：休闲/慢游
    relax_kws = ["休闲", "慢", "闲逛", "养老", "散步", "轻松"]
    if any(kw in text for kw in relax_kws) or "闲逛" in pace:
        return "休闲型"

    # 默认：观光型
    return "观光型"
