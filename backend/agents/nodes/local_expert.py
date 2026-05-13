"""local_expert 节点。

本地达人校验器（LLM节点）。
使用LLM检查：
1. 是否为旅游陷阱
2. 季节性是否合适
3. 当地人的隐藏建议
"""

from __future__ import annotations

import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.agents.state import PlanningState, AgentIssue
from backend.config.settings import settings


SYSTEM_PROMPT = """你是CityFlow的本地达人，熟悉珠海本地情况。

你的任务是审核路线，从本地人视角发现问题：
1. **旅游陷阱**: 哪些POI是外地游客才去、本地人不去的地方？
2. **季节性**: 当前季节是否适合这些POI？
3. **隐藏建议**: 有什么本地人才知道的信息？
4. **排队预警**: 哪些POI在特定时间会大排长龙？

## 输出格式

返回JSON：
{
    "issues": [
        {
            "severity": "high|medium|low",
            "category": "local",
            "description": "问题描述",
            "suggestion": "建议",
            "affected_indices": [0, 1]
        }
    ],
    "local_tips": ["本地人建议1", "本地人建议2"],
    "confidence": 0.85
}"""


def node(state: PlanningState) -> dict:
    """本地达人校验。

    使用LLM从本地视角审核路线。

    Args:
        state: 当前规划状态，需包含route

    Returns:
        dict: 包含validation_results的更新片段
    """
    route = state.get("route")
    user_intent = state.get("user_intent", {})

    if not route:
        return {
            "validation_results": state.get("validation_results", []) + [{
                "agent": "local_expert",
                "issues": [],
                "confidence": 0.0,
            }]
        }

    # 构建路线描述
    route_desc = []
    for i, step in enumerate(route.get("route", [])):
        poi = step.get("poi", {})
        route_desc.append(f"{i+1}. {poi.get('name')} ({poi.get('category')}) - {poi.get('tags', [])}")

    context = f"""用户群体: {user_intent.get('group', {}).get('type', '未知')}
路线POI:
{"\n".join(route_desc)}
"""

    try:
        llm = ChatOpenAI(
            model=settings.llm.model,
            temperature=settings.agent.local_expert_temperature,
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key,
            max_retries=settings.llm.max_retries,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=context),
        ]

        response = llm.invoke(messages)
        content = response.content

        # 解析JSON
        try:
            analysis = json.loads(content)
        except json.JSONDecodeError:
            # 从markdown提取
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                analysis = json.loads(json_str)
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
                analysis = json.loads(json_str)
            else:
                raise

        issues = analysis.get("issues", [])
        confidence = analysis.get("confidence", 0.8)

        result = {
            "agent": "local_expert",
            "issues": issues,
            "confidence": confidence,
        }

    except Exception as e:
        # LLM失败，返回空结果
        result = {
            "agent": "local_expert",
            "issues": [],
            "confidence": 0.5,
        }

    return {
        "validation_results": state.get("validation_results", []) + [result]
    }
