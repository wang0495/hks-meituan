"""CityFlow API -- 请求 / 响应 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    """流式规划路线的请求体。"""

    user_input: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="用户出行需求的自然语言描述，系统会自动解析意图、匹配画像。",
        examples=["周末想一个人安静走走", "和朋友一起吃喝玩乐，预算500以内"],
    )

    user_id: str | None = Field(
        None,
        description="用户标识。如果提供，系统会读取该用户的长期记忆来个性化推荐。",
    )

    current_context: dict | None = Field(
        None,
        description=(
            "当前上下文信息（天气/季节/节假日等）。"
            "如果提供，系统会根据上下文模式匹配历史偏好。"
        ),
    )

    start_location: str | None = Field(
        None,
        description="出发位置，如'香洲'、'拱北'、'唐家湾'。留空则默认市区中心。",
    )

    agent: bool | None = Field(
        None,
        description="是否使用新的多智能体架构。None表示使用系统默认配置，true强制启用，false强制禁用。",
    )

    version: str | None = Field(
        None,
        description="架构版本选择: 'a'=3层联邦架构, 'b'=LangGraph+Validator架构, None=使用默认配置",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"user_input": "周末想一个人安静走走"},
                {"user_input": "和女朋友约会，要有氛围感"},
                {"user_input": "带孩子出去玩，不要太累"},
            ]
        }
    }


class AdjustRequest(BaseModel):
    """对话式路线调整的请求体。"""

    instruction: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description=(
            "用户调整指令，支持以下类型：\n"
            '- **替换**: "换掉第二个景点"、"不喜欢故宫"\n'
            '- **节奏**: "太赶了"、"想轻松点"、"紧凑一些"\n'
            '- **预算**: "太贵了"、"便宜一点"\n'
            '- **时间**: "早一点出发"、"5点前结束"\n'
            '- **重试**: "重新来"、"再来一次"'
        ),
        examples=["换掉第二个景点", "太赶了", "便宜一点"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"instruction": "换掉第二个景点"},
                {"instruction": "太赶了，想轻松点"},
                {"instruction": "便宜一点"},
                {"instruction": "早上8点出发"},
                {"instruction": "重新规划"},
            ]
        }
    }


# ---------------------------------------------------------------------------
# 响应模型（用于 OpenAPI 文档生成）
# ---------------------------------------------------------------------------


class EmotionTags(BaseModel):
    """POI情绪标签（6维，取值0~1）。"""

    excitement: float = Field(..., ge=0, le=1, description="兴奋度")
    tranquility: float = Field(..., ge=0, le=1, description="宁静度")
    sociability: float = Field(..., ge=0, le=1, description="社交性")
    culture_depth: float = Field(..., ge=0, le=1, description="文化深度")
    surprise: float = Field(..., ge=0, le=1, description="惊喜度")
    physical_demand: float = Field(..., ge=0, le=1, description="体力消耗")


class POIConstraints(BaseModel):
    """POI约束条件。"""

    accessible: bool = Field(True, description="是否无障碍通行")
    pet_friendly: bool = Field(False, description="是否允许携带宠物")
    queue_time_min: int = Field(0, ge=0, description="预计排队时间（分钟）")
    opening_hours: str = Field("09:00-17:00", description="营业时间")
    has_restroom: bool = Field(True, description="是否有洗手间")


class TravelInfo(BaseModel):
    """交通信息。"""

    distance_m: int = Field(..., ge=0, description="距离（米）")
    time_min: int = Field(..., ge=0, description="耗时（分钟）")


class POIResponse(BaseModel):
    """兴趣点（POI）完整信息。"""

    id: str = Field(..., description="POI唯一标识")
    name: str = Field(..., description="名称")
    category: str = Field(..., description="类别（景点/餐厅/公园/商场等）")
    city: str = Field(..., description="所在城市")
    rating: float = Field(..., ge=0, le=5, description="评分（0~5）")
    avg_price: float = Field(..., ge=0, description="人均消费（元）")
    avg_stay_min: int = Field(60, ge=0, description="建议停留时长（分钟）")
    lat: float = Field(..., description="纬度")
    lng: float = Field(..., description="经度")
    business_hours: str = Field("09:00-17:00", description="营业时间")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    emotion_tags: EmotionTags | None = Field(None, description="情绪标签")
    constraints: POIConstraints | None = Field(None, description="约束条件")
    price_range: str | None = Field(
        None,
        description="价格区间（免费/便宜/中等/较贵/高端）",
    )


class RouteStep(BaseModel):
    """路线中的单个步骤。"""

    poi: POIResponse = Field(..., description="该站点的POI信息")
    arrival_time: str = Field(..., description="到达时间，格式 HH:MM")
    departure_time: str = Field(..., description="离开时间，格式 HH:MM")
    travel_from_prev: TravelInfo | None = Field(
        None,
        description="从前一站到本站的交通信息（首站为null）",
    )


class NarrativeStep(BaseModel):
    """路线文案。"""

    opening: str = Field("", description="开场白")
    steps: list[str] = Field(default_factory=list, description="每站的文案描述")
    closing: str = Field("", description="结束语")
    emotion_highlights: list[dict] = Field(
        default_factory=list,
        description="情绪亮点",
    )


class RouteResult(BaseModel):
    """完整的路线规划结果。"""

    route: list[RouteStep] = Field(..., description="路线步骤列表")
    emotion_curve: list[dict] = Field(
        default_factory=list,
        description="情绪曲线数据",
    )
    total_cost: dict = Field(
        ...,
        description="总消耗估算：time_min(总时长), budget_used(预算), step_estimate(步数)",
    )
    unused_candidates: list[POIResponse] = Field(
        default_factory=list,
        description="未使用的候选POI，可用于后续对话替换",
    )
    breathing_spots: list[POIResponse] = Field(
        default_factory=list,
        description="推荐的休息点",
    )
    narrative: NarrativeStep | None = Field(None, description="路线文案")
    user_intent: dict | None = Field(None, description="解析后的用户意图")


class DoneEvent(BaseModel):
    """SSE done 事件的载荷。"""

    route_id: str = Field(..., description="路线ID，可用于后续查询和对话调整")
    full_route: RouteResult = Field(..., description="完整路线数据")


class DialogueResult(BaseModel):
    """对话调整的响应。"""

    reply: str = Field(..., description="系统回复文本")
    route: dict = Field(..., description="调整后的完整路线数据")
    changes_made: list[dict] = Field(
        default_factory=list,
        description=(
            "本次所做的变更列表，每项包含 type 字段：\n"
            "- replace: 替换景点（含 original/replacement）\n"
            "- pace: 调整节奏（含 new_pace）\n"
            "- budget: 调整预算（含 new_budget）\n"
            "- time: 调整时间（含 new_time）\n"
            "- retry: 重新规划"
        ),
    )


class DistanceMatrixItem(BaseModel):
    """距离矩阵中的单个元素。"""

    distance_m: int = Field(..., ge=0, description="距离（米）")
    time_min: int = Field(..., ge=0, description="预估耗时（分钟），按30km/h计算")


class DistanceMatrixResponse(BaseModel):
    """距离矩阵响应。"""

    matrix: list[list[DistanceMatrixItem]] = Field(
        ...,
        description="N×N距离矩阵，matrix[i][j] 表示 poi_ids[i] 到 poi_ids[j] 的距离信息",
    )
    poi_ids: list[str] = Field(..., description="对应的POI ID列表，顺序与矩阵行列一致")


class ErrorResponse(BaseModel):
    """错误响应。"""

    detail: str | dict = Field(..., description="错误详情")


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = Field("ok", description="服务状态")
