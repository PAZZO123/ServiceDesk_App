
import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import Notification
from app.models.enums import NotificationType, TicketOwnerRole, TicketStatus
from app.models.team import TeamMembership
from app.models.ticket import Ticket
from app.realtime.events import emit_ticket_event
from app.services.audit import add_audit
from app.workers.celery_app import celery_app
from app.workers.db import worker_session

logger = logging.getLogger(__name__)
BATCH_SIZE = 100
FINISHED = (TicketStatus.RESOLVED, TicketStatus.CLOSED)


async def _recipients(db: AsyncSession, ticket: Ticket) -> list[uuid.UUID]:
    assignees = [o.user_id for o in ticket.owners if o.role == TicketOwnerRole.ASSIGNEE]
    if assignees:
        return assignees
    rows = await db.scalars(
        select(TeamMembership.user_id).where(TeamMembership.team_id == ticket.team_id)
    )
    return list(rows)


async def sweep_sla_breaches(db: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)

    tickets = (
        await db.scalars(
            select(Ticket)
            .where(
        
                Ticket.sla_breached.is_(False),
                Ticket.sla_due_at < now,
                Ticket.status.not_in(FINISHED),
                Ticket.deleted_at.is_(None),
            )
            .order_by(Ticket.sla_due_at)  # oldest breach first
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
            .options(selectinload(Ticket.owners))
        )
    ).all()

    for ticket in tickets:
        ticket.sla_breached = True
        add_audit(
            db,
            actor_id=None,
            entity_type="ticket",
            entity_id=ticket.id,
            action="sla_breached",
            changes={"sla_due_at": ticket.sla_due_at.isoformat()},
        )

        for user_id in await _recipients(db, ticket):
            db.add(
                Notification(
                    user_id=user_id,
                    type=NotificationType.SLA_BREACHED,
                    payload={
                        "ticket_id": str(ticket.id),
                        "reference": ticket.reference,
                        "title": ticket.title,
                        "priority": ticket.priority.value,
                        "sla_due_at": ticket.sla_due_at.isoformat(),
                    },
                )
            )

        await emit_ticket_event(db, ticket.id, "sla_breached")
    await db.commit()
    return len(tickets)


async def _run_sweep() -> int:
    async with worker_session() as db:
        return await sweep_sla_breaches(db)

@celery_app.task(name="sla.sweep_breaches")
def sweep_sla_breaches_task() -> int:
    count = asyncio.run(_run_sweep())
    if count:
        logger.info("sla_sweep flagged=%d", count)
    return count