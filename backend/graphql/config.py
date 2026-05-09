"""CityFlow GraphQL 配置 -- Schema 工厂。"""

from __future__ import annotations

import strawberry

from backend.graphql.schema import Mutation, Query


def create_graphql_schema() -> strawberry.Schema:
    """创建并返回 GraphQL Schema 实例。

    启用 auto_camel_case 使得 Python 的 snake_case 字段名
    在 GraphQL 端自动转为 camelCase（如 avg_price -> avgPrice）。
    """
    return strawberry.Schema(
        query=Query,
        mutation=Mutation,
    )
