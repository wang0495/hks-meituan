"""add audit_logs table

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-05-09 01:33:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 audit_logs 表。"""
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 创建索引
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index(
        "idx_audit_logs_user_action", "audit_logs", ["user_id", "action"]
    )


def downgrade() -> None:
    """删除 audit_logs 表。"""
    op.drop_index("idx_audit_logs_user_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
