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
_GQL_MAX_ALIASES = 10       # 最大别名数

graphql_app = GraphQLRouter(schema)


# 在GraphQL路由前加查询大小限制
@router.post("/graphql")
async def graphql_endpoint(request: Request):
    """GraphQL入口，限制查询大小和别名数。"""
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
    except (json.JSONDecodeError, AttributeError):
        pass

    # 转发给Strawberry处理
    return await graphql_app(request)


router.include_router(graphql_app, prefix="/graphql-internal")
