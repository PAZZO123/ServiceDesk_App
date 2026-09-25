import csv
import io
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.api.deps import DbSession, Perms
from app.models.team import Category, Team
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import TicketFilters
from app.services.ticket_service import TicketService

logger=logging.getLogger(__name__)
router=APIRouter(tags=["Export"])

BATCH_SIZE=500
COLUMNS=[
    "reference",
    "title",
    "status",
    "priority",
    "team",
    "category",
    "requester",
    "assignee",
    "created_at",
    "sla_due_at",
    "resolved_at",
]

def _csv_safe(value:Any)->str:
    text=""if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text

@router.get(
    "/exports/tickets.csv",
    summary="Download ticket as csv",
    response_model=StreamingResponse,
     responses={200: {"content": {"text/csv": {}}}},
)
async def export_tickets(
    db:DbSession,
    perms:Perms,
    filters:Annotated[TicketFilters, Depends()],
)->StreamingResponse:
    service=TicketService(db)
    conditions=service.conditions(filters)
    conditions.extend(perms.visibility_conditions())
    requester=aliased(User, name="req")
    assignee=aliased(User, name="asg")
    
    stmt=(
        select(
            Ticket.reference,
            Ticket.title,
            Ticket.status,
            Ticket.priority,
            Team.name,
            Category.name,
            requester.full_name,
            assignee.full_name,
            Ticket.created_at,
            Ticket.sla_due_at,
            Ticket.resolved_at,
        )
        .join(Team, Team.id == Ticket.team_id)
        .join(Category, Category.id == Ticket.category_id)
        .join(requester, requester.id == Ticket.requester_id)
        .outerjoin(assignee,assignee.id==Ticket.assignee_id)
        .where(Ticket.deleted_at.is_(None), *conditions)
        .order_by(Ticket.created_at)
        .execution_options(yield_per=BATCH_SIZE)
    )
    
    async def generate() -> AsyncIterator[str]:
            buffer = io.StringIO()
            writer = csv.writer(buffer)

            def flush() -> str:
                buffer.seek(0)
                chunk = buffer.read()
                buffer.seek(0)
                buffer.truncate(0)
                return chunk

            yield "\ufeff"

            writer.writerow(COLUMNS)
            yield flush()

            count = 0
            result = await db.stream(stmt)

            async for row in result:
                writer.writerow([_csv_safe(value) for value in row])
                count += 1

                if count % BATCH_SIZE == 0:
                    yield flush()

            
            remainder = flush()
            if remainder:
                yield remainder

            logger.info("ticket_export rows=%s user=%s", count, perms.user.id)

    filename = f"tickets-{datetime.now(UTC):%Y-%m-%d}.csv"

    return StreamingResponse(
            generate(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
            },
        )