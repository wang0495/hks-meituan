"""CityFlow GraphQL 路由 -- 将 Strawberry GraphQL 挂载到 FastAPI。"""

from __future__ import annotations

from fastapi import APIRouter
from strawberry.fastapi import GraphQLRouter

from backend.graphql.schema import schema

router = APIRouter(tags=["GraphQL"])

# 创建 Strawberry GraphQL 路由
# graphql_app 默认挂载在 /graphql
graphql_app = GraphQLRouter(schema)

# 将 GraphQL 端点包含到路由中
router.include_router(graphql_app, prefix="/graphql")
