"""C版本状态：分布式智能体网络。

6层架构对应：
1. 用户输入 + 元规则
2. 元规则防火墙检查结果
3. 事件总线（events/proposals/counter_proposals）
4. 7个Agent提案（真LLM决策）
5. 涌现式校验结果
6. Live Itinerary（热力图+决策溯源）
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class TravelState(TypedDict, total=False):
    """分布式规划状态。"""

    # ── Layer 1: 用户输入 + 元规则 ──
    user_input: str
    user_intent: dict
    meta_rules: list[dict]
    candidates: list[dict]

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
    route: dict | None
    narrative: dict | None
    heatmap: dict
    decision_trace: dict

    # 控制
    user_decision_needed: bool

    # 错误（并发合并）
    errors: Annotated[list[str], operator.add]
