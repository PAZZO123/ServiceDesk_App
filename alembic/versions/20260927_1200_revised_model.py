"""revised model: roles table, ticket_owners, duplicate groups, merged profiles

Revision ID: a4d7e2c91b35
Revises: 76cd5b11aeb8
Create Date: 2026-09-27 12:00:00

Written by hand: autogenerate cannot move data between tables.
Does not import from `app` - a migration must give the same result forever.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a4d7e2c91b35"
down_revision: str | Sequence[str] | None = "76cd5b11aeb8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. roles table replaces the user_role enum
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "permissions",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_index(op.f("ix_roles_permissions"), "roles", ["permissions"], postgresql_using="gin")

    op.execute(
        """
        INSERT INTO roles (id, name, description, permissions, is_system) VALUES
          (gen_random_uuid(), 'requester',
           'Raises tickets and follows their own.',
           '{}'::text[], true),
          (gen_random_uuid(), 'agent',
           'Support staff: works the tickets queued to their teams.',
           ARRAY['ticket.work', 'comment.read_internal', 'ticket.starts_high']::text[], true),
          (gen_random_uuid(), 'observer',
           'Managers and executives: can see every ticket, cannot change any.',
           ARRAY['ticket.view_all', 'comment.read_internal']::text[], true),
          (gen_random_uuid(), 'admin',
           'Full access, including deleting tickets and assigning roles.',
           ARRAY['ticket.view_all', 'ticket.work', 'ticket.delete',
                 'comment.read_internal', 'content.moderate',
                 'team.manage', 'user.manage']::text[], true)
        """
    )

    # users.role -> users.role_id: add nullable, fill, then NOT NULL
    op.add_column("users", sa.Column("role_id", sa.UUID(), nullable=True))
    op.execute(
        """
        UPDATE users AS u
        SET role_id = r.id
        FROM roles AS r
        WHERE r.name = u.role::text
        """
    )
    op.alter_column("users", "role_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_users_role_id_roles"), "users", "roles", ["role_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"])
    op.drop_column("users", "role")
    op.execute("DROP TYPE IF EXISTS user_role")

    # 2. merge user_profiles into users
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(length=64), server_default="Africa/Kigali", nullable=False),
    )
    op.add_column("users", sa.Column("notify_email", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("users", sa.Column("notify_in_app", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("users", sa.Column("signature", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE users AS u
        SET timezone      = p.timezone,
            notify_email  = p.notify_email,
            notify_in_app = p.notify_in_app,
            signature     = p.signature
        FROM user_profiles AS p
        WHERE p.user_id = u.id
        """
    )
    op.drop_table("user_profiles")

    # 3. case-insensitive unique email
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.create_index(op.f("uq_users_email_lower"), "users", [sa.text("lower(email)")], unique=True)

    # 4. category names unique per team
    op.drop_constraint(op.f("uq_categories_name"), "categories", type_="unique")
    op.create_unique_constraint(op.f("uq_categories_team_id_name"), "categories", ["team_id", "name"])

    # 5. duplicate groups (replaces tickets.merged_into_id)
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
    op.create_index(
        op.f("uq_tickets_one_canonical_per_group"), "tickets", ["duplicate_group_id"],
        unique=True, postgresql_where=sa.text("is_duplicate_canonical"),
    )
    op.create_check_constraint(
        op.f("ck_tickets_canonical_needs_group"), "tickets",
        "NOT is_duplicate_canonical OR duplicate_group_id IS NOT NULL",
    )

    # 6. ticket_owners (replaces tickets.requester_id / assignee_id)
    op.create_table(
        "ticket_owners",
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("requester", "assignee", "watcher", name="ticket_owner_role"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"],
            name=op.f("fk_ticket_owners_ticket_id_tickets"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_ticket_owners_user_id_users"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ticket_id", "user_id", "role", name=op.f("pk_ticket_owners")),
    )
    op.create_index(op.f("ix_ticket_owners_user_id_role"), "ticket_owners", ["user_id", "role"])
    op.create_index(
        op.f("uq_ticket_owners_single_holder"), "ticket_owners", ["ticket_id", "role"],
        unique=True, postgresql_where=sa.text("role IN ('requester', 'assignee')"),
    )

    # copy the links across before the old columns go (keep the ticket's own dates)
    op.execute(
        """
        INSERT INTO ticket_owners (ticket_id, user_id, role, created_at)
        SELECT id, requester_id, 'requester', created_at
        FROM tickets
        """
    )
    op.execute(
        """
        INSERT INTO ticket_owners (ticket_id, user_id, role, created_at)
        SELECT id, assignee_id, 'assignee', updated_at
        FROM tickets
        WHERE assignee_id IS NOT NULL
        """
    )

    # 7. drop the old columns (their FKs and indexes go with them)
    op.drop_column("tickets", "requester_id")
    op.drop_column("tickets", "assignee_id")
    op.drop_column("tickets", "merged_into_id")
    op.drop_column("comments", "parent_id")


def downgrade() -> None:
    """Watchers and any role other than requester/agent/admin cannot come back.
    Fails on purpose (instead of losing data) if a ticket has no requester row
    or two teams share a category name."""
    # 7.
    op.add_column("comments", sa.Column("parent_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_comments_parent_id_comments"), "comments", "comments",
        ["parent_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index(op.f("ix_comments_parent_id"), "comments", ["parent_id"])

    op.add_column("tickets", sa.Column("merged_into_id", sa.UUID(), nullable=True))
    op.add_column("tickets", sa.Column("assignee_id", sa.UUID(), nullable=True))
    op.add_column("tickets", sa.Column("requester_id", sa.UUID(), nullable=True))

    # 6.
    op.execute(
        """
        UPDATE tickets AS t
        SET requester_id = o.user_id
        FROM ticket_owners AS o
        WHERE o.ticket_id = t.id AND o.role = 'requester'
        """
    )
    op.execute(
        """
        UPDATE tickets AS t
        SET assignee_id = o.user_id
        FROM ticket_owners AS o
        WHERE o.ticket_id = t.id AND o.role = 'assignee'
        """
    )
    op.alter_column("tickets", "requester_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_tickets_requester_id_users"), "tickets", "users",
        ["requester_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_tickets_assignee_id_users"), "tickets", "users",
        ["assignee_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_tickets_merged_into_id_tickets"), "tickets", "tickets",
        ["merged_into_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(op.f("ix_tickets_requester_id"), "tickets", ["requester_id"])
    op.create_index(op.f("ix_tickets_assignee_id"), "tickets", ["assignee_id"])
    op.create_index(op.f("ix_tickets_merged_into_id"), "tickets", ["merged_into_id"])
    op.drop_table("ticket_owners")
    op.execute("DROP TYPE IF EXISTS ticket_owner_role")

    # 5.
    op.drop_constraint(op.f("ck_tickets_canonical_needs_group"), "tickets", type_="check")
    op.drop_index(op.f("uq_tickets_one_canonical_per_group"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_duplicate_group_id"), table_name="tickets")
    op.drop_constraint(
        op.f("fk_tickets_duplicate_group_id_duplicate_groups"), "tickets", type_="foreignkey"
    )
    op.drop_column("tickets", "is_duplicate_canonical")
    op.drop_column("tickets", "duplicate_group_id")
    op.drop_table("duplicate_groups")

    # 4.
    op.drop_constraint(op.f("uq_categories_team_id_name"), "categories", type_="unique")
    op.create_unique_constraint(op.f("uq_categories_name"), "categories", ["name"])

    # 3.
    op.drop_index(op.f("uq_users_email_lower"), table_name="users")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 2.
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Africa/Kigali", nullable=False),
        sa.Column("notify_email", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notify_in_app", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_user_profiles_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_profiles")),
    )
    op.execute(
        """
        INSERT INTO user_profiles (user_id, timezone, notify_email, notify_in_app, signature)
        SELECT id, timezone, notify_email, notify_in_app, signature
        FROM users
        """
    )
    op.drop_column("users", "signature")
    op.drop_column("users", "notify_in_app")
    op.drop_column("users", "notify_email")
    op.drop_column("users", "timezone")

    # 1.
    op.execute("CREATE TYPE user_role AS ENUM ('requester', 'agent', 'admin')")
    op.add_column(
        "users",
        sa.Column(
            "role",
            postgresql.ENUM("requester", "agent", "admin", name="user_role", create_type=False),
            server_default="requester",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE users AS u
        SET role = r.name::user_role
        FROM roles AS r
        WHERE r.id = u.role_id
          AND r.name IN ('requester', 'agent', 'admin')
        """
    )
    op.drop_column("users", "role_id")
    op.drop_table("roles")
