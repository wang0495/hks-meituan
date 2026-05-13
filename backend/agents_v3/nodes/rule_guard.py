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

    # ── 加载POI ──
    try:
        from backend.services.data_service import get_data
        all_pois = get_data()
        if isinstance(all_pois, dict):
            all_pois = list(all_pois.values())
        elif not isinstance(all_pois, list):
            all_pois = []
    except Exception as e:
        errors.append(f"POI加载失败: {e}")
        all_pois = []

    # ── 只保留目标城市POI ──
    target_city = user_intent.get("city", "珠海")
    if all_pois:
        zhuhai_pois = [p for p in all_pois if p.get("city", "") == target_city or not p.get("city")]
        if len(zhuhai_pois) >= 10:
            all_pois = zhuhai_pois
        # else 保留全部（数据可能没标城市）

    # ── 预筛（宽松：只做最基本过滤，让Agent自己选） ──
    candidates = all_pois
    if all_pois:
        try:
            from backend.services.filters import filter_candidates
            candidates = filter_candidates(all_pois, user_intent)
        except Exception:
            candidates = all_pois[:120]

        # 确保关键景点在候选池中（即使被过滤掉了也加回来）
        candidates = _ensure_key_pois(candidates, all_pois, user_intent)

    # ── 元规则防火墙检查 ──
    rule_violations = check_hard_rules(user_intent, candidates)

    return {
        "user_intent": user_intent,
        "candidates": candidates,
        "rule_violations": rule_violations,
        "meta_rules": [],
        "errors": errors,
    }


# 珠海核心景点（必须出现在候选池中）
_KEY_POIS = [
    "长隆海洋王国", "海洋王国", "横琴长隆海洋科学馆", "长隆马戏城",
    "珠海渔女", "情侣路", "外伶仃岛", "淇澳岛", "圆明新园",
    "海滨泳场", "海滨公园", "野狸岛", "日月贝", "珠海大剧院",
    "港珠澳大桥", "东澳岛", "金海滩", "飞沙滩", "御温泉",
    "梅华海鲜城", "新海利", "湾仔海鲜街",
]


def _ensure_key_pois(candidates: list[dict], all_pois: list[dict], intent: dict) -> list[dict]:
    """确保关键景点在候选池中。"""
    cand_names = {c.get("name", "") for c in candidates}

    # 构建需要确保的景点列表
    user_input = str(intent.get("_raw_input", ""))
    needed = set()
    for kp in _KEY_POIS:
        if kp in user_input:
            needed.add(kp)

    # 如果用户没提到特定景点，至少加入最知名的
    if not needed:
        needed = {"长隆海洋王国", "珠海渔女", "情侣路", "圆明新园", "海滨泳场"}

    missing = []
    for poi in all_pois:
        name = poi.get("name", "")
        for n in needed:
            if n in name or name in n:
                if name not in cand_names:
                    missing.append(poi)
                    cand_names.add(name)
                    break

    if missing:
        candidates = list(candidates) + missing

    return candidates


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
