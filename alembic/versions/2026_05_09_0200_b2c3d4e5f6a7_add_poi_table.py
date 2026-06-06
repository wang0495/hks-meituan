"""add POI table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-09 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 pois 表。"""
    op.create_table(
        "pois",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("city", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("rating", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("avg_price", sa.Float, nullable=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("business_hours", sa.String(100), nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("queue_prone", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("avg_stay_min", sa.Integer, nullable=False, server_default="60"),
        sa.Column("emotion_tags", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("experience_value", sa.Float, nullable=True),
        sa.Column("price_elasticity", sa.Float, nullable=True),
        sa.Column("experience_leverage", sa.String(20), nullable=True),
        sa.Column("spend_emotion", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 创建索引
    op.create_index("idx_pois_city", "pois", ["city"])
    op.create_index("idx_pois_category", "pois", ["category"])
    op.create_index("idx_pois_rating", "pois", ["rating"])


def downgrade() -> None:
    """删除 pois 表。"""
    op.drop_index("idx_pois_rating", table_name="pois")
    op.drop_index("idx_pois_category", table_name="pois")
    op.drop_index("idx_pois_city", table_name="pois")
    op.drop_table("pois")
