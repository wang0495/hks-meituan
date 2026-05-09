"""CityFlow 数据校验框架。

使用方式::

    from backend.validators import POIValidator, validate_request

    # 直接校验数据
    poi = POIValidator(**raw_data)

    # 装饰器方式
    @validate_request(PlanRequestValidator)
    async def plan_route(user_input: str): ...
"""

from backend.validators.base import (BaseValidator, ChatRequestValidator,
                                     ConstraintsValidator,
                                     DialogueRequestValidator,
                                     DistanceMatrixValidator,
                                     EmotionTagsValidator,
                                     PlanRequestValidator, POISearchValidator,
                                     POIValidator, RequestValidator,
                                     RouteStepValidator, RouteValidator,
                                     check_injection, sanitize_string)
from backend.validators.decorators import validate_request, validate_response

__all__ = [
    "BaseValidator",
    "ChatRequestValidator",
    "ConstraintsValidator",
    "DialogueRequestValidator",
    "DistanceMatrixValidator",
    "EmotionTagsValidator",
    "POISearchValidator",
    "POIValidator",
    "PlanRequestValidator",
    "RequestValidator",
    "RouteStepValidator",
    "RouteValidator",
    "check_injection",
    "sanitize_string",
    "validate_request",
    "validate_response",
]
