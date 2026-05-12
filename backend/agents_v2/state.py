"""A版本状态定义 - 支持3层联邦架构。"""

from __future__ import annotations

from typing import Any, TypedDict


class Contradiction(TypedDict):
    """矛盾标注。"""

    type: str
    description: str
    resolution: str


class SubNeed(TypedDict):
    """分解后的子需求。"""

    id: str
    description: str
    constraints: dict[str, Any]
    priority: int


class IntentPackage(TypedDict):
    """第一层输出：带矛盾标注的结构化意图包。"""

    core_intent: dict[str, Any]
    contradictions: list[Contradiction]
    decomposed_sub_needs: list[SubNeed]
    raw_input: str


class Bid(TypedDict):
    """竞标方案。"""

    agent_type: str
    agent_id: str
    sub_need_id: str
    proposal: dict[str, Any]
    confidence: float
    cost_estimate: dict[str, float]


class ValidationIssue(TypedDict):
    """校验发现的问题。"""

    validator: str
    severity: str
    description: str
    affected_bid_ids: list[str]


class Contract(TypedDict):
    """智能体间契约。"""

    bid_a: str
    bid_b: str
    handoff_time: str
    transport_mode: str
    status: str


class FederatedState(TypedDict):
    """A版本完整状态。"""

    # 输入
    user_input: str

    # Layer 1: 意图探测与矛盾调解
    intent_package: IntentPackage | None

    # 竞标市场输出
    bids: list[Bid]

    # Layer 2: 对抗性校验
    validation_issues: list[ValidationIssue]
    surviving_bids: list[Bid]

    # Layer 3: 微协商
    contracts: list[Contract]
    final_route: dict[str, Any] | None

    # 运行时监控
    runtime_alerts: list[dict[str, Any]]

    # 元信息
    round: int
    errors: list[str]
