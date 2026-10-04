"""notification_type gets 'ticket_created' (oversight notifications)

Revision ID: e4b7c2a9d815
Revises: d81b5e0c4a2f
Create Date: 2026-10-04 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e4b7c2a9d815"
down_revision: str | Sequence[str] | None = "d81b5e0c4a2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'ticket_created'")


def downgrade() -> None:
    pass