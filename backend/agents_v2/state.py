"""A版本状态定义 - 支持3层联邦架构完整实现。"""

from __future__ import annotations

from typing import Any, TypedDict


# ============================================================================
# Layer 1: 意图探测与矛盾调解
# ============================================================================


class Contradiction(TypedDict):
    """矛盾标注。"""

    type: str  # budget_vs_quality, group_vs_activity, emotion_shift等
    description: str
    severity: str  # high/medium/low
    conflicting_aspects: list[str]
    resolution: str


class SubNeed(TypedDict):
    """分解后的子需求。"""

    id: str
    description: str
    constraints: dict[str, Any]
    priority: int  # 1-10
    time_window: tuple[str, str] | None  # (start, end)


class ProbeQuestion(TypedDict):
    """追问问题。"""

    question_id: str
    question: str
    related_contradiction: str | None
    options: list[str] | None


class IntentPackage(TypedDict):
    """第一层输出：带矛盾标注的结构化意图包。"""

    core_intent: dict[str, Any]
    contradictions: list[Contradiction]
    decomposed_sub_needs: list[SubNeed]
    probe_questions: list[ProbeQuestion]
    latent_needs: list[str]  # 隐含需求
    raw_input: str


# ============================================================================
# 竞标市场
# ============================================================================


class Bid(TypedDict):
    """竞标方案。"""

    bid_id: str
    agent_type: str  # poi/food/activity/transport/insurance
    agent_id: str
    sub_need_id: str
    proposal: dict[str, Any]
    confidence: float  # 0-1
    base_cost: float
    dynamic_price: float  # 市场动态定价
    cost_estimate: dict[str, float]
    created_at_round: int


class CompositeBid(TypedDict):
    """组合投标：POI+餐饮+交通打包。"""

    composite_id: str
    agent_type: str  # "composite"
    sub_need_ids: list[str]
    component_bids: list[Bid]
    total_cost: float
    total_confidence: float
    synergy_bonus: float  # 协同奖励分


class BiddingRound(TypedDict):
    """单轮竞标记录。"""

    round_number: int
    bids: list[Bid]
    composite_bids: list[CompositeBid]
    market_prices: dict[str, float]  # sub_need_id -> market_price
    supply_demand_ratio: dict[str, float]


class MarketClearing(TypedDict):
    """市场出清结果。"""

    winning_bids: list[Bid]
    winning_composites: list[CompositeBid]
    budget_used: float
    coverage: float  # sub_need覆盖率
    clearing_prices: dict[str, float]


class BidTask(TypedDict):
    """单个Agent竞标任务（Send()参数）。"""

    sub_need: SubNeed
    agent_type: str
    round_number: int


# ============================================================================
# Layer 2: 对抗性校验市场
# ============================================================================


class ValidationIssue(TypedDict):
    """校验发现的问题。"""

    issue_id: str
    validator: str
    severity: str  # high/medium/low
    category: str  # time/fatigue/budget/local/critique/realtime
    description: str
    suggestion: str
    affected_bid_ids: list[str]


class ValidatorResult(TypedDict):
    """单个Validator的输出。"""

    validator: str
    issues: list[ValidationIssue]
    confidence: float
    metadata: dict[str, Any]


class ValidationTask(TypedDict):
    """单个Validator任务（Send()参数）。"""

    validator_name: str
    bids: list[Bid]
    composite_bids: list[CompositeBid]
    intent_package: IntentPackage


# ============================================================================
# Layer 3: 微协商总线
# ============================================================================


class TimeContract(TypedDict):
    """时间契约（有约束力）。"""

    contract_id: str
    bid_a: str  # 前序bid ID
    bid_b: str  # 后续bid ID
    handoff_time: str  # 交接时间 HH:MM
    buffer_minutes: int  # 缓冲时间
    transport_mode: str
    transport_time_min: float
    constraints: list[str]  # 契约约束 ["no_delay", "weather_backup"]
    status: str  # active / violated / renegotiating
    violation_action: str


class RenegotiationScope(TypedDict):
    """重协商范围。"""

    trigger: str
    affected_contracts: list[str]
    time_range: tuple[str, str]
    alternative_bids: list[Bid]


class NegotiationResult(TypedDict):
    """协商结果。"""

    success: bool
    contracts: list[TimeContract]
    adjustments: dict[str, Any]
    conflicts_resolved: int
    conflicts_remaining: int


# ============================================================================
# 运行时监控
# ============================================================================


class RuntimeAlert(TypedDict):
    """运行时告警。"""

    alert_id: str
    type: str  # weather_change / poi_closed / traffic_delay / time_pressure
    severity: str
    description: str
    affected_contract_ids: list[str]
    suggested_action: str


# ============================================================================
# 完整状态
# ============================================================================


class FederatedState(TypedDict):
    """A版本完整状态。"""

    # 输入
    user_input: str
    perception_ctx: dict[str, Any] | None

    # Layer 1: 意图探测与矛盾调解
    intent_package: IntentPackage | None
    probe_questions: list[ProbeQuestion]

    # 竞标市场
    bidding_rounds: list[BiddingRound]
    current_round: int
    bids: list[Bid]
    composite_bids: list[CompositeBid]
    market_clearing: MarketClearing | None

    # Layer 2: 对抗性校验
    validation_results: list[ValidatorResult]
    validation_issues: list[ValidationIssue]
    surviving_bids: list[Bid]
    surviving_composites: list[CompositeBid]

    # Layer 3: 微协商
    negotiation_result: NegotiationResult | None
    contracts: list[TimeContract]
    final_route: dict[str, Any] | None
    renegotiation_scope: RenegotiationScope | None

    # 运行时
    runtime_alerts: list[RuntimeAlert]
    round: int
    errors: list[str]

    # 内部任务标识（Send()使用）
    _bid_task: BidTask | None
    _validation_task: ValidationTask | None
