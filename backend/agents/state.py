"""LangGraph 状态定义。

定义PlanningState用于在StateGraph各节点间共享数据，
以及AgentIssue/ValidatorResult等类型用于校验器输出。
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentIssue(TypedDict):
    """校验器发现的问题。

    Attributes:
        severity: 严重度，"high" | "medium" | "low"
        category: 类别，"time" | "fatigue" | "budget" | "local"
        description: 问题描述
        suggestion: 建议修复方式
        affected_indices: 受影响的路线步骤索引
    """

    severity: str
    category: str
    description: str
    suggestion: str
    affected_indices: list[int]


class ValidatorResult(TypedDict):
    """单个校验器的校验结果。

    Attributes:
        agent: 校验器名称
        issues: 发现的问题列表
        confidence: 置信度 0.0-1.0
    """

    agent: str
    issues: list[AgentIssue]
    confidence: float


class ArbitrationResult(TypedDict):
    """裁决节点汇总所有校验器结果后的决策。

    Attributes:
        action: 决策动作，"pass" | "adjust" | "re_solve"
        issues: 所有发现的问题(按severity排序)
        adjustments: 调整建议
        confidence: 整体置信度
    """

    action: str
    issues: list[AgentIssue]
    adjustments: dict[str, Any]
    confidence: float


class PlanningState(TypedDict):
    """LangGraph规划管线的共享状态。

    各节点通过读写此状态协作完成路线规划。

    Attributes:
        user_input: 原始用户输入
        user_intent: 解析后的用户意图
        candidates: POI候选池
        route: 求解器生成的路线
        validation_results: fan-in收集的校验结果
        arbitration: 裁决决策
        narrative: 生成的文案
        round: 当前校验轮数
        errors: 错误信息列表
    """

    user_input: str
    user_intent: dict[str, Any]
    candidates: list[dict[str, Any]]
    route: dict[str, Any] | None
    validation_results: list[ValidatorResult]
    arbitration: ArbitrationResult | None
    narrative: dict[str, Any] | None
    round: int
    errors: list[str]
