"""new permission ticket.reassign, granted to admin

Revision ID: f6a3d8e1b247
Revises: e4b7c2a9d815
Create Date: 2026-10-04 15:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6a3d8e1b247"
down_revision: str | Sequence[str] | None = "e4b7c2a9d815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A new row in permissions: the code knows WHAT can be checked...
    op.execute(
        """
        INSERT INTO permissions (id, code, description)
        VALUES (
            gen_random_uuid(),
            'ticket.reassign',
            'Take over or reassign a ticket that another agent is already working on'
        )
        ON CONFLICT (code) DO NOTHING
        """
    )
    # ...and role_permissions decides WHO has it. Admin today; an admin can
    # give it to any other role later from the Roles page, without code.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.name = 'admin' AND p.code = 'ticket.reassign'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Grants first: the foreign key (ON DELETE RESTRICT) protects a
    # permission that is still granted.
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id = (SELECT id FROM permissions WHERE code = 'ticket.reassign')
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'ticket.reassign'")