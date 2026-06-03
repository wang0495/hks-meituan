from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.schemas import ChatRequest, ChatResponse
from backend.services import llm_service

router = APIRouter(prefix="/api/llm", tags=["LLM"])

# 允许的模型白名单
_ALLOWED_MODELS = frozenset(
    {
        "openai",
        "deepseek-chat",
        "deepseek-reasoner",
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
    }
)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="LLM对话",
    description=(
        "与大语言模型进行单轮对话。\n\n"
        "发送一条消息，返回模型的完整回复。\n\n"
        "## 支持的模型\n\n"
        "- `openai` - OpenAI GPT（默认）\n"
        "- 其他模型视配置而定"
    ),
    response_description="模型回复",
    responses={
        200: {
            "description": "对话成功",
            "content": {
                "application/json": {
                    "example": {
                        "response": "你好！有什么可以帮助你的吗？",
                        "model": "openai",
                    }
                }
            },
        }
    },
    tags=["LLM"],
)
async def chat(req: ChatRequest) -> ChatResponse:
    """与LLM进行单轮对话。"""
    model_name = req.model or "openai"
    if model_name not in _ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"不支持的模型: {model_name}")
    resp = await llm_service.chat(message=req.message, model=model_name)
    return ChatResponse(response=resp, model=model_name)


@router.post(
    "/chat/stream",
    summary="LLM流式对话",
    description=(
        "与大语言模型进行流式对话（SSE）。\n\n"
        "发送一条消息，以SSE事件流的形式逐步返回模型回复。\n\n"
        "## SSE 格式\n\n"
        "- 每条消息格式：`data: <chunk>\\n\\n`\n"
        "- 流结束标记：`data: [DONE]\\n\\n`"
    ),
    response_description="SSE事件流",
    responses={
        200: {
            "description": "SSE事件流",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "examples": {
                        "chunk": {
                            "summary": "回复片段",
                            "value": "data: 你好\n\n",
                        },
                        "done": {
                            "summary": "结束标记",
                            "value": "data: [DONE]\n\n",
                        },
                    },
                }
            },
        }
    },
    tags=["LLM"],
)
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """与LLM进行流式对话。"""
    model_name = req.model or "openai"
    if model_name not in _ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"不支持的模型: {model_name}")

    async def stream():
        async for chunk in llm_service.chat_stream(message=req.message, model=req.model):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
