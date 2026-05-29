"""元规则防火墙节点：解析意图 + 加载数据 + 硬约束预筛。

对应架构Layer 1+2：用户输入 → 元规则防火墙。

═════════════════════════════════════════════════════════════
  架构决策记录（ADR）— 别瞎改，每条都是踩过坑的
═════════════════════════════════════════════════════════════

ADR-R1: _fix_food_categories() 必须在 filter_candidates 之前执行
  - 已移入 data_service.load_pois()，加载时自动清洗，无需 agent 关心

ADR-R2: _ensure_key_pois_llm() 用LLM补核心景点
  - 纯规则过滤会漏掉用户隐含需要的核心景点
  - 如"带孩子去长隆"可能被预算过滤砍掉长隆
  - LLM判断更准确, 但多一次API调用

ADR-R3: 场景分类用规则不用LLM
  - _classify_scene() 基于关键词, 不额外调LLM
  - 已移入 expert_router.py

ADR-R4: intent_parser 超时重试3次再降级
  - intent_parser.py 内部已含降级逻辑（_rule_based_parse）
  - agent 不再感知降级细节
"""

from __future__ import annotations

from backend.agents_v3.state import TravelState, AGENT_META, sse_emit


async def rule_guard(state: TravelState) -> dict:
    """入口节点：解析意图 → 加载POI → 硬约束预筛。"""
    meta = AGENT_META.get("rule_guard", {})
    await sse_emit(state, "agent_start", {"agent": "rule_guard", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "rule_guard", "text": "解析自然语言意图..."})

    user_input = state.get("user_input", "")
    errors: list[str] = []

    # ── 1. 意图解析（service 内含 LLM+降级） ──
    from backend.services.intent_parser import parse_intent

    try:
        user_intent = await parse_intent(user_input)
    except Exception as e:
        errors.append(f"意图解析失败: {e}")
        user_intent = _bare_intent(user_input)

    # ── 2. 加载POI（统一入口：美团API → 本地JSON → 清洗 → 城市过滤） ──
    await sse_emit(state, "agent_thinking", {"agent": "rule_guard", "text": "加载POI数据，硬约束预筛..."})
    from backend.services.data_service import load_pois

    target_city = user_intent.get("city", "珠海")
    all_pois = await load_pois(city=target_city, errors=errors)

    # ── 3. 硬约束预筛 ──
    candidates = all_pois
    if all_pois:
        try:
            from backend.services.filters import filter_candidates
            candidates = filter_candidates(all_pois, user_intent)
        except Exception:
            candidates = all_pois[:120]

        # ── 4. LLM 补充关键景点（agent 核心智能） ──
        candidates = await _ensure_key_pois_llm(candidates, all_pois, user_input, user_intent)

    # ── 5. 硬约束违规检查 ──
    from backend.services.filters import check_hard_rules
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


def _bare_intent(user_input: str) -> dict:
    """intent_parser 也失败时的最小兜底（不应走到这里）。"""
    return {
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

    from backend.agents_v3.experts.base import _llm_decide

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
        result = await _llm_decide("", prompt, prefix="LLM")
        must_have = result.get("must_have", []) if result else []
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
