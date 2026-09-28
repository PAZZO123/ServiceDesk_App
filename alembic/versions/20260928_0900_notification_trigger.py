"""notify listeners when notifications are added or read

Revision ID: 5b8e1f03c7d2
Revises: a4d7e2c91b35
Create Date: 2026-09-28 09:00:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5b8e1f03c7d2'
down_revision: Union[str, Sequence[str], None] = 'a4d7e2c91b35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The payload is only the user id: a doorbell, not the message.
    # NOTIFY is transactional - it is delivered on COMMIT, dropped on ROLLBACK,
    # and repeats with the same payload in one transaction arrive only once.
    op.execute(
        """
        CREATE FUNCTION notify_notification_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify('notifications', NEW.user_id::text);
            RETURN NULL;
        END;
        $$;
        """
    )
    # A trigger, not Python code: Day 8's Celery workers will add
    # notifications too, and none of them can forget to ring.
    op.execute(
        """
        CREATE TRIGGER notifications_notify
        AFTER INSERT OR UPDATE OF read_at ON notifications
        FOR EACH ROW EXECUTE FUNCTION notify_notification_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS notifications_notify ON notifications;")
    op.execute("DROP FUNCTION IF EXISTS notify_notification_change();")