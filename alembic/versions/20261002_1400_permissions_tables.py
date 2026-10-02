"""permissions + role_permissions tables; remove duplicate groups

Revision ID: c3f9a1d27e64
Revises: 5b8e1f03c7d2
Create Date: 2026-10-02 14:00:00

Written by hand: autogenerate cannot move data between tables.
Does not import from `app` - a migration must give the same result forever.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c3f9a1d27e64"
down_revision: str | Sequence[str] | None = "5b8e1f03c7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the Permission enum on this date (+ descriptions).
# tests/test_roles.py fails if app/models/enums.py and the table drift apart.
PERMISSIONS = [
    ("ticket.view_all", "See every ticket in every team."),
    ("ticket.work", "Work tickets: change status, assign, claim, write internal notes."),
    ("ticket.delete", "Delete tickets."),
    ("ticket.starts_high", "Tickets you raise start at High priority."),
    ("comment.read_internal", "Read internal notes."),
    ("content.moderate", "Delete other people's comments."),
    ("team.manage", "Add, remove and promote team members."),
    ("user.manage", "List users and change their role."),
    ("role.manage", "Create roles and change which permissions they grant."),
]


def upgrade() -> None:
    # ---- 1. permissions + role_permissions --------------------------------
    op.create_table(
        "permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("permission_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
    )
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    # Bound parameters, not string formatting: "people's" contains a quote.
    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description) "
                "VALUES (gen_random_uuid(), :code, :description)"
            ).bindparams(code=code, description=description)
        )

    # ---- 2. move roles.permissions (text[]) into role_permissions ----------
    # Refuse rather than silently drop a code that has no permissions row
    # (a typo stored in the old free-text array).
    op.execute(
        """
        DO $$
        DECLARE unknown text;
        BEGIN
            SELECT string_agg(DISTINCT p, ', ') INTO unknown
            FROM roles, unnest(roles.permissions) AS p
            WHERE p NOT IN (SELECT code FROM permissions);
            IF unknown IS NOT NULL THEN
                RAISE EXCEPTION 'roles.permissions contains unknown codes: %', unknown;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles AS r
        CROSS JOIN LATERAL unnest(r.permissions) AS granted(code_text)
        JOIN permissions AS p ON p.code = granted.code_text
        """
    )
    # The admin keeps every power it had, plus the new one.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.name = 'admin' AND p.code = 'role.manage'
        ON CONFLICT DO NOTHING
        """
    )
    op.drop_index(op.f("ix_roles_permissions"), table_name="roles", postgresql_using="gin")
    op.drop_column("roles", "permissions")

    # ---- 3. remove duplicate groups -----------------------------------------
    op.drop_index("uq_tickets_one_canonical_per_group", table_name="tickets")
    op.drop_constraint(op.f("ck_tickets_canonical_needs_group"), "tickets", type_="check")
    op.drop_index(op.f("ix_tickets_duplicate_group_id"), table_name="tickets")
    op.drop_constraint(
        op.f("fk_tickets_duplicate_group_id_duplicate_groups"), "tickets", type_="foreignkey"
    )
    op.drop_column("tickets", "is_duplicate_canonical")
    op.drop_column("tickets", "duplicate_group_id")
    op.drop_index(op.f("ix_duplicate_groups_created_by"), table_name="duplicate_groups")
    op.drop_table("duplicate_groups")


def downgrade() -> None:
    # Duplicate groups come back EMPTY (there were none when this ran).
    op.create_table(
        "duplicate_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name=op.f("fk_duplicate_groups_created_by_users"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_duplicate_groups")),
    )
    op.create_index(op.f("ix_duplicate_groups_created_by"), "duplicate_groups", ["created_by"])
    op.add_column("tickets", sa.Column("duplicate_group_id", sa.UUID(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column("is_duplicate_canonical", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_tickets_duplicate_group_id_duplicate_groups"),
        "tickets", "duplicate_groups", ["duplicate_group_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_tickets_duplicate_group_id"), "tickets", ["duplicate_group_id"])
    op.create_check_constraint(
        op.f("ck_tickets_canonical_needs_group"),
        "tickets",
        "NOT is_duplicate_canonical OR duplicate_group_id IS NOT NULL",
    )
    op.create_index(
        "uq_tickets_one_canonical_per_group", "tickets", ["duplicate_group_id"],
        unique=True, postgresql_where=sa.text("is_duplicate_canonical"),
    )

    # role_permissions -> roles.permissions text[]. role.manage disappears
    # (the old schema has no such permission).
    op.add_column(
        "roles",
        sa.Column(
            "permissions", postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"), nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE roles AS r SET permissions = COALESCE((
            SELECT array_agg(p.code ORDER BY p.code)
            FROM role_permissions rp JOIN permissions p ON p.id = rp.permission_id
            WHERE rp.role_id = r.id AND p.code <> 'role.manage'
        ), '{}'::text[])
        """
    )
    op.create_index(op.f("ix_roles_permissions"), "roles", ["permissions"], postgresql_using="gin")
    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
