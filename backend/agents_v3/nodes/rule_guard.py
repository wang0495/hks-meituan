"""元规则防火墙节点：解析意图 + 加载数据 + 硬约束预筛。

对应架构Layer 1+2：用户输入 → 元规则防火墙。

ADR-R1: _fix_food_categories() 在 load_pois() 内自动执行
ADR-R2: _ensure_key_pois() 用规则补核心景点（不再调LLM，节省~3s）
ADR-R3: 场景分类用规则不用LLM（已移入 expert_router.py）
ADR-R4: intent_parser 超时重试3次再降级
ADR-R5: 意图解析和POI加载并行执行（节省~3s）
"""

from __future__ import annotations

import asyncio

from backend.agents_v3.state import TravelState, AGENT_META, sse_emit


async def rule_guard(state: TravelState) -> dict:
    """入口节点：解析意图 → 加载POI → 硬约束预筛。

    优化：parse_intent 和 load_pois 并行执行（ADR-R5）。
    """
    meta = AGENT_META.get("rule_guard", {})
    await sse_emit(state, "agent_start", {"agent": "rule_guard", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "rule_guard", "text": "解析意图 + 加载数据（并行）..."})

    user_input = state.get("user_input", "")
    errors: list[str] = []

    # ── 1+2. 并行：意图解析 + POI加载（ADR-R5） ──
    from backend.services.intent_parser import parse_intent
    from backend.services.data_service import load_pois

    intent_result, all_pois = await asyncio.gather(
        _safe_parse_intent(user_input),
        load_pois(city="珠海", errors=errors),
    )
    user_intent = intent_result
    target_city = user_intent.get("city", "珠海")

    # 如果城市不是珠海，重新加载（罕见路径）
    if target_city != "珠海" and all_pois:
        from backend.services.data_service import load_pois as _load
        all_pois = await _load(city=target_city, errors=errors)

    # ── 3. 硬约束预筛 ──
    candidates = all_pois
    if all_pois:
        try:
            from backend.services.filters import filter_candidates
            candidates = filter_candidates(all_pois, user_intent)
        except Exception:
            candidates = all_pois[:120]

        # ── 4. 规则补充关键景点（ADR-R2，不再调LLM） ──
        candidates = _ensure_key_pois(candidates, all_pois, user_input)

    # ── 5. 硬约束违规检查 ──
    from backend.services.filters import check_hard_rules
    rule_violations = check_hard_rules(user_intent, candidates)

    # ── 6. 预计算场景分类（ADR-PERF：无歧义场景跳过expert_router LLM调用） ──
    pre_scene_type = None
    try:
        from backend.agents_v3.nodes.expert_router import _rule_precheck
        pre_scene_type = _rule_precheck(user_input, user_intent)
    except Exception:
        pass

    await sse_emit(state, "agent_result", {"agent": "rule_guard", "summary": f"意图已解析，{len(candidates)}个候选POI"})

    # ── 提前推送候选POI预览（ADR-PERF：用户3-5秒内看到真实POI名称） ──
    if candidates:
        top_preview = sorted(candidates, key=lambda p: float(p.get("rating", 0)), reverse=True)[:6]
        await sse_emit(state, "searching", {
            "message": f"已找到 {len(candidates)} 个候选地点",
            "preview": [
                {"name": p.get("name", ""), "category": p.get("category", ""), "rating": p.get("rating", 0)}
                for p in top_preview
            ],
            "intent_summary": {
                "city": user_intent.get("city", "珠海"),
                "period": user_intent.get("time", {}).get("period", "全天"),
                "pace": user_intent.get("pace", "平衡型"),
                "group": user_intent.get("group", {}).get("type", "独居"),
            },
        })

    return {
        "user_intent": user_intent,
        "candidates": candidates,
        "rule_violations": rule_violations,
        "meta_rules": [],
        "errors": errors,
        **({"pre_scene_type": pre_scene_type} if pre_scene_type else {}),
    }


async def _safe_parse_intent(user_input: str) -> dict:
    """带异常捕获的意图解析。"""
    from backend.services.intent_parser import parse_intent
    try:
        return await parse_intent(user_input)
    except Exception:
        return _bare_intent(user_input)


def _bare_intent(user_input: str) -> dict:
    """intent_parser 也失败时的最小兜底。"""
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


# 珠海核心景点（关键词匹配兜底）
_KEY_POIS = [
    "长隆海洋王国", "海洋王国", "横琴长隆海洋科学馆", "长隆马戏城",
    "珠海渔女", "情侣路", "外伶仃岛", "淇澳岛", "圆明新园",
    "海滨泳场", "海滨公园", "野狸岛", "日月贝", "珠海大剧院",
    "港珠澳大桥", "东澳岛", "金海滩", "飞沙滩", "御温泉",
    "梅华海鲜城", "新海利", "湾仔海鲜街",
]


def _ensure_key_pois(
    candidates: list[dict],
    all_pois: list[dict],
    user_input: str,
) -> list[dict]:
    """规则匹配补充核心景点（ADR-R2：不再调LLM，纯关键词匹配）。

    从用户输入中匹配知名景点名，确保候选池包含这些核心POI。
    """
    cand_names = {c.get("name", "") for c in candidates}
    must_have = set()

    # 从用户输入中匹配核心景点
    for kp in _KEY_POIS:
        if kp in user_input:
            must_have.add(kp)

    # 如果没有匹配到任何核心景点，保留默认集合
    if not must_have:
        return candidates

    # 将缺失的核心POI加入候选池
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
