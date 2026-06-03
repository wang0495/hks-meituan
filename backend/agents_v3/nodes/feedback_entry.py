"""feedback_entry: 反馈重入入口节点。

Path B 反馈流程的 graph 入口：
1. 读取 rerun_experts（由 feedback_router 标记）
2. 注入非重跑 expert 的缓存提案到 proposals
3. 设定 active_experts = rerun_experts（让 _wave1_dispatcher 只分派这些）
4. 重置 review 状态
5. 传递 prev_round_context 供下游 agent 参考
"""

from __future__ import annotations

import logging

from backend.agents_v3.state import TravelState, sse_emit

logger = logging.getLogger(__name__)


async def feedback_entry(state: TravelState) -> dict:
    """反馈重入：选择性 expert 重跑 + 缓存提案注入。"""
    await sse_emit(state, "agent_start", {"agent": "feedback_entry"})
    await sse_emit(
        state, "agent_thinking", {"agent": "feedback_entry", "text": "选择性重跑专家..."}
    )

    rerun = set(state.get("rerun_experts", []))
    cached = list(state.get("cached_proposals", []))
    prev_ctx = state.get("prev_round_context", {})

    # 只保留非重跑 expert 的缓存提案（重跑 expert 会产生新提案）
    non_rerun_cached = [p for p in cached if p.get("agent") not in rerun]

    logger.info(
        "feedback_entry: rerun=%s, cached=%d, non_rerun_cached=%d",
        sorted(rerun),
        len(cached),
        len(non_rerun_cached),
    )

    await sse_emit(
        state,
        "agent_thinking",
        {
            "agent": "feedback_entry",
            "text": f"重跑 {len(rerun)} 个expert, 注入 {len(non_rerun_cached)} 条缓存提案",
        },
    )

    return {
        "proposals": non_rerun_cached,
        "active_experts": sorted(rerun),
        "rerun_experts": sorted(rerun),
        "cached_proposals": cached,
        "prev_round_context": prev_ctx,
        "review_feedback": [],
        "review_round": 0,
    }
