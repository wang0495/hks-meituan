from __future__ import annotations

import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from backend.config import settings
from backend.errors import LLMServiceError

logger = logging.getLogger(__name__)

_openai_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key,
        )
    return _openai_client


async def chat_stream(
    message: str,
    model: str = "",
    system_prompt: str = "你是一个数据分析助手，简洁地回答用户问题。",
) -> AsyncIterator[str]:
    if not model:
        model = settings.llm.model
    client = get_client()
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except TimeoutError:
        logger.warning("LLM stream timeout")
        raise LLMServiceError(message="LLM服务超时", details={"timeout": True})
    except Exception as e:
        logger.exception("LLM stream error: %s", e)
        raise LLMServiceError(message="LLM服务异常", details={"original_error": str(e)})


async def chat(message: str, model: str = "") -> str:
    if not model:
        model = settings.llm.model
    client = get_client()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
        )
        return resp.choices[0].message.content or ""
    except TimeoutError:
        logger.warning("LLM chat timeout")
        raise LLMServiceError(message="LLM服务超时", details={"timeout": True})
    except Exception as e:
        logger.exception("LLM chat error: %s", e)
        raise LLMServiceError(message="LLM服务异常", details={"original_error": str(e)})
