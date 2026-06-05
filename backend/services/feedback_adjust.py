"""反馈调整核心逻辑：调用 feedback graph 重新规划路线。

替代原 DialogueEngine，通过选择性重跑 MoE expert 实现智能路线调整。
"""

from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_feedback_adjust(
    route_id: str,
    instruction: str,
    cached_route: dict,
    cached_state: dict,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """调用 feedback graph 执行路线调整。

    Args:
        route_id: 路线 ID
        instruction: 用户调整指令
        cached_route: route_cache 中的路线数据
        cached_state: feedback_state_cache 中的中间状态
        history: 可选的对话历史

    Returns:
        {"reply": str, "route": dict, "changes_made": list}
    """
    from backend.agents_v3 import get_feedback_graph_c
    from backend.agents_v3.state import TravelState
    from backend.services.feedback_classifier import classify_feedback

    # 1. 分类指令 → rerun_experts + weight_adjust
    classification = await classify_feedback(instruction, history)
    rerun_experts = classification["rerun_experts"]
    weight_adjust = classification["weight_adjust"]
    reply = classification["reply"]
    logger.info(
        "[FeedbackAdjust] route=%s intent=%s rerun=%s",
        route_id, classification["intent"], rerun_experts,
    )

    # 2. 构建 expert_weights（原权重 + 调整量）
    old_weights = dict(cached_state.get("expert_weights", {}))
    new_weights: dict[str, float] = {}
    for k, v in old_weights.items():
        new_weights[k] = max(0.1, min(1.0, v + weight_adjust.get(k, 0)))
    # 确保重跑的 expert 至少有权重
    for name in rerun_experts:
        new_weights[name] = max(new_weights.get(name, 0.3), 0.3)

    # 3. 分离 cached_proposals（非重跑 expert 的提案保留）
    rerun_set = set(rerun_experts)
    all_proposals = cached_state.get("proposals", [])
    cached_proposals = [p for p in all_proposals if p.get("agent") not in rerun_set]

    # 4. 构建 TravelState（参考 test_feedback.py 的 run_feedback）
    user_intent = cached_route.get("user_intent", {})
    original_input = cached_state.get("user_input", "")
    combined_input = f"{original_input}（用户反馈：{instruction}）" if original_input else instruction

    prev_stops = [
        step.get("poi", {}).get("name", "")
        for step in cached_route.get("route", [])
    ]

    fb_state: TravelState = {
        "user_input": combined_input,
        "proposals": [],
        "negotiation_msgs": [],
        "errors": [],
        "feedback_mode": True,
        "rerun_experts": sorted(rerun_experts),
        "cached_proposals": cached_proposals,
        "prev_round_context": {
            "last_weights": old_weights,
            "last_stops": prev_stops,
            "reject_reason": instruction,
        },
        "user_intent": user_intent,
        "scene_type": cached_state.get("scene_type", "观光型"),
        "candidates": cached_state.get("candidates", []),
        "expert_weights": new_weights,
        "active_experts": sorted(rerun_experts),
        "sse_queue": asyncio.Queue(),
        "destination_name": cached_state.get("destination_name", ""),
        "destination_center": cached_state.get("destination_center", ()),
    }

    # 5. 调用 feedback graph
    graph = get_feedback_graph_c()
    result = await asyncio.wait_for(graph.ainvoke(fb_state), timeout=120)

    # 6. 提取新路线
    new_route = result.get("route")
    if not new_route or not new_route.get("route"):
        logger.error("[FeedbackAdjust] graph 返回空路线: %s", route_id)
        return {
            "reply": "抱歉，路线调整失败，请重试或重新规划。",
            "route": cached_route,
            "changes_made": [],
        }

    # 7. 更新缓存
    new_route["user_intent"] = user_intent
    from backend.services.cache import route_cache, feedback_state_cache

    route_cache.set(route_id, new_route)
    feedback_state_cache.set(route_id, {
        "proposals": result.get("proposals", []),
        "expert_weights": result.get("expert_weights", new_weights),
        "active_experts": result.get("active_experts", rerun_experts),
        "candidates": cached_state.get("candidates", []),
        "scene_type": cached_state.get("scene_type", "观光型"),
        "destination_name": cached_state.get("destination_name", ""),
        "destination_center": cached_state.get("destination_center", ()),
        "user_intent": user_intent,
        "user_input": original_input,
    })

    # 8. 返回结果
    changes_made = [{
        "type": "feedback_graph",
        "intent": classification["intent"],
        "rerun_experts": rerun_experts,
        "weight_adjust": weight_adjust,
    }]

    return {
        "reply": reply,
        "route": new_route,
        "changes_made": changes_made,
    }


async def rebuild_minimal_state(cached_route: dict) -> dict[str, Any]:
    """从路线 + 数据服务重建最小中间状态（降级用）。"""
    from backend.services.data_service import load_pois

    user_intent = cached_route.get("user_intent", {})
    city = user_intent.get("city", "珠海")
    all_pois = await load_pois(city=city)

    return {
        "proposals": [],
        "expert_weights": {"poi": 0.8, "food": 0.7, "traffic": 0.6, "local_expert": 0.5},
        "active_experts": ["poi", "food", "traffic", "local_expert"],
        "candidates": all_pois[:150],
        "scene_type": user_intent.get("scene_type", "观光型"),
        "destination_name": city,
        "destination_center": (),
        "user_intent": user_intent,
        "user_input": "",
    }
