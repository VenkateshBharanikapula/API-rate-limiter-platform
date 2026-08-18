"""create core tables: api_clients, rate_limit_configs, api_usage, audit_logs

Revision ID: 0001
Revises:
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("api_key", sa.String(length=64), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("free", "basic", "premium", name="plan_type", native_enum=False),
            nullable=False,
            server_default="free",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_clients_email", "api_clients", ["email"], unique=True)
    op.create_index("ix_api_clients_api_key", "api_clients", ["api_key"], unique=True)

    op.create_table(
        "rate_limit_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("api_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requests_allowed", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_rate_limit_configs_client_id", "rate_limit_configs", ["client_id"], unique=True
    )

    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("api_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("was_allowed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_usage_client_id", "api_usage", ["client_id"])
    op.create_index("ix_api_usage_timestamp", "api_usage", ["timestamp"])
    op.create_index(
        "ix_api_usage_client_timestamp", "api_usage", ["client_id", "timestamp"]
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("api_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Enum(
                "client_registered",
                "api_key_generated",
                "rate_limit_updated",
                "client_activated",
                "client_deactivated",
                name="audit_action",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_client_id", "audit_logs", ["client_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index(
        "ix_audit_logs_client_created", "audit_logs", ["client_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("api_usage")
    op.drop_table("rate_limit_configs")
    op.drop_table("api_clients") 
