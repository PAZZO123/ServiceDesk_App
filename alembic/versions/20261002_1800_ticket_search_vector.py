"""tickets.search_vector becomes a generated column (full-text search)

Revision ID: d81b5e0c4a2f
Revises: c3f9a1d27e64
Create Date: 2026-10-02 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d81b5e0c4a2f"
down_revision: str | Sequence[str] | None = "c3f9a1d27e64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_EXPRESSION = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(description, '')), 'B')"
)


def upgrade() -> None:
    # A plain column cannot be turned into a generated one in place:
    # drop it (and its index) and add it back.
    op.drop_index("ix_tickets_search", table_name="tickets")
    op.drop_column("tickets", "search_vector")
    op.add_column(
        "tickets",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            # GENERATED ALWAYS AS (...) STORED: PostgreSQL computes it on
            # every INSERT/UPDATE - and right now for every existing row.
            sa.Computed(SEARCH_EXPRESSION, persisted=True),
            nullable=True,
        ),
    )
    # GIN = an index of "which rows contain this word" - what @@ uses.
    op.create_index(
        "ix_tickets_search", "tickets", ["search_vector"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_search", table_name="tickets")
    op.drop_column("tickets", "search_vector")
    op.add_column("tickets", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True))
    op.create_index(
        "ix_tickets_search", "tickets", ["search_vector"], postgresql_using="gin"
    )