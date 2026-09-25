import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def add_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    changes: dict[str, Any],
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            ip_address=ip_address,
        )
    )