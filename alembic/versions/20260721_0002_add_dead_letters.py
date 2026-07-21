"""Add dead-letter tracking for exhausted event replays.

Revision ID: 20260721_0002
Revises: 20260721_0001
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0002"
down_revision: str | None = "20260721_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create durable tracking for events that should no longer auto-replay."""
    op.create_table(
        "dead_letters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("external_event_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("replay_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_dead_letters_event_id", "dead_letters", ["event_id"])
    op.create_index("ix_dead_letters_external_event_id", "dead_letters", ["external_event_id"])


def downgrade() -> None:
    """Drop dead-letter tracking."""
    op.drop_index("ix_dead_letters_external_event_id", table_name="dead_letters")
    op.drop_index("ix_dead_letters_event_id", table_name="dead_letters")
    op.drop_table("dead_letters")
