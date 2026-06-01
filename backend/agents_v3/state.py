"""MoE版本状态：混合专家架构。

6层架构对应：
1. 用户输入 + 元规则
2. 元规则防火墙检查结果
3. 事件总线（events/proposals/counter_proposals）
4. MoE专家提案（按需激活，LLM决策）
5. 涌现式校验结果
6. Live Itinerary（热力图+决策溯源）
"""

from __future__ import annotations

import asyncio
import operator
from typing import Annotated, TypedDict


class TravelState(TypedDict, total=False):
    """分布式规划状态。"""

    # ── Layer 1: 用户输入 + 元规则 ──
    user_input: str
    user_intent: dict
    scene_type: str                  # 美食型/观光型/目的地型/特种兵型/休闲型
    meta_rules: list[dict]
    candidates: list[dict]

    # ── MoE: 专家路由 ──
    expert_weights: dict             # {"poi": 0.9, "food": 0.8, ...}
    active_experts: list[str]        # ["poi", "food", "local_expert"]
    expert_candidates: dict          # {"poi": [...], "food": [...], ...}
    destination_name: str            # LLM检测到的目的地名称
    destination_center: tuple        # (lat, lng) 目的地中心坐标

    # ── Layer 2: 元规则防火墙结果 ──
    rule_violations: list[dict]

    # ── Layer 3: 事件总线（并发合并） ──
    events: Annotated[list[dict], operator.add]
    proposals: Annotated[list[dict], operator.add]
    counter_proposals: Annotated[list[dict], operator.add]
    negotiation_msgs: Annotated[list[dict], operator.add]

    # ── 讨论池：review反馈 ──
    review_feedback: list[dict]       # [{agent: "poi", issue: "...", action: "rework"}]
    review_round: int                 # 当前轮次（0=首轮, 1=第2轮...）
    reworked_proposals: list[dict]    # rework后的完整proposals（覆盖原始的）

    # ── Layer 5: 涌现式校验结果 ──
    conflicts: list[dict]

    # ── Layer 6: Live Itinerary ──
    num_days: int                     # 出行天数 (default=1, max=5)
    route: dict | None               # 单日路线 (向后兼容，多日时为第1天)
    routes: list                     # 多日路线 [{day:1, route:{...}}, ...]
    narrative: dict | None
    heatmap: dict
    decision_trace: dict

    # 控制
    user_decision_needed: bool

    # ── SSE 实时推送队列 ──
    sse_queue: asyncio.Queue          # agent_start/agent_thinking/agent_result events

    # 错误（并发合并）
    errors: Annotated[list[str], operator.add]

    # ── 反馈重入 (Path B) ──
    feedback_mode: bool                  # True=反馈重入模式
    rerun_experts: list[str]            # 需要重跑的expert列表
    cached_proposals: list[dict]       # 未重跑expert的上轮缓存提案
    prev_round_context: dict             # 上一轮决策+效果 {last_weights, score_5dim, route, reject_reason}


# ── Agent 元数据（工牌） ──
AGENT_META: dict[str, dict] = {
    "rule_guard":     {"name": "意图解析",   "icon": "🧠", "role": "需求理解", "color": "#ff5368"},
    "poi":            {"name": "POI 专家",   "icon": "🏛", "role": "景点筛选", "color": "#51aef9"},
    "food":           {"name": "美食专家",   "icon": "🍜", "role": "餐饮推荐", "color": "#ff9b54"},
    "hotel":          {"name": "住宿专家",   "icon": "🏨", "role": "住宿推荐", "color": "#4da6ff"},
    "traffic":        {"name": "交通专家",   "icon": "🚗", "role": "交通规划", "color": "#4dd8e8"},
    "weather":        {"name": "天气专家",   "icon": "🌤", "role": "天气分析", "color": "#ffa54d"},
    "local_expert":   {"name": "本地向导",   "icon": "🗺", "role": "隐藏宝藏", "color": "#7edc95"},
    "insurance":      {"name": "保险专家",   "icon": "🛡", "role": "风险评估", "color": "#9b6dff"},
    "negotiation":    {"name": "协商引擎",   "icon": "⚖️", "role": "冲突调解", "color": "#ff6b9d"},
    "review":         {"name": "审查员",     "icon": "🔍", "role": "质量校验", "color": "#c49a6a"},
    "synthesizer":    {"name": "综合师",     "icon": "✨", "role": "路线组装", "color": "#ff5a88"},
    "expert_router":  {"name": "路由器",     "icon": "📡", "role": "专家调度", "color": "#7b6cf6"},
}


async def sse_emit(state: TravelState, event: str, data: dict) -> None:
    """向 SSE 队列推送事件（安全：无 queue 时静默跳过）。"""
    q: asyncio.Queue | None = state.get("sse_queue")
    if q is not None:
        await q.put((event, data))
        await asyncio.sleep(0)  # yield control so drain loop can pick up
