from typing import Optional

from pydantic import BaseModel, Field


class DataQuery(BaseModel):
    """数据查询请求。"""

    dataset: Optional[str] = Field(None, description="数据集名称")
    filters: Optional[dict] = Field(None, description="过滤条件")


class DataResponse(BaseModel):
    """数据查询响应。"""

    data: list[dict] = Field(..., description="数据列表")
    total: int = Field(..., ge=0, description="数据总数")


class ChatRequest(BaseModel):
    """LLM对话请求。"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="用户消息内容",
        examples=["你好，请介绍一下CityFlow"],
    )
    model: Optional[str] = Field(
        "openai",
        description="使用的模型名称，默认 openai",
        examples=["openai"],
    )


class ChatResponse(BaseModel):
    """LLM对话响应。"""

    response: str = Field(..., description="模型回复内容")
    model: str = Field(..., description="使用的模型名称")
