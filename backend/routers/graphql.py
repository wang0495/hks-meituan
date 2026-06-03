"""CityFlow GraphQL 路由 -- 将 Strawberry GraphQL 挂载到 FastAPI。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from strawberry.fastapi import GraphQLRouter

from backend.graphql.schema import schema

logger = logging.getLogger(__name__)

router = APIRouter(tags=["GraphQL"])

# GraphQL安全限制
_GQL_MAX_QUERY_SIZE = 5000  # 最大查询字符数
_GQL_MAX_ALIASES = 10  # 最大别名数
_GQL_MAX_DEPTH = 5  # 最大嵌套深度

graphql_app = GraphQLRouter(schema)


def _check_query_depth(query: str, max_depth: int) -> bool:
    """检查GraphQL查询嵌套深度。"""
    depth = 0
    max_seen = 0
    for ch in query:
        if ch == "{":
            depth += 1
            max_seen = max(max_seen, depth)
        elif ch == "}":
            depth -= 1
    return max_seen <= max_depth


# 在GraphQL路由前加查询大小限制
@router.post("/graphql")
async def graphql_endpoint(request: Request) -> dict:
    """GraphQL入口，限制查询大小、别名数和嵌套深度。"""
    body = await request.body()
    if len(body) > _GQL_MAX_QUERY_SIZE:
        return {"errors": [{"message": "查询过大"}]}

    import json

    try:
        data = json.loads(body)
        query = data.get("query", "")
        # 简单别名计数: 数冒号在花括号前的数量
        alias_count = query.count(":")
        if alias_count > _GQL_MAX_ALIASES:
            return {"errors": [{"message": f"别名数量超过限制({_GQL_MAX_ALIASES})"}]}
        # 深度限制
        if not _check_query_depth(query, _GQL_MAX_DEPTH):
            return {"errors": [{"message": f"查询嵌套深度超过限制({_GQL_MAX_DEPTH})"}]}
    except (json.JSONDecodeError, AttributeError):
        pass

    # 转发给Strawberry处理
    return await graphql_app(request)


router.include_router(graphql_app, prefix="/graphql-internal")
