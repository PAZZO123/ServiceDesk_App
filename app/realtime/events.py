import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import TicketPermissions
from app.models.ticket import Ticket, TicketOwner

# PostgreSQL LISTEN/NOTIFY channel names.
TICKET_CHANNEL = "ticket_events"
NOTIFICATION_CHANNEL = "notifications"

ALL_TICKETS_ROOM = "tickets:all"


def team_room(team_id: uuid.UUID) -> str:
    return f"team:{team_id}"


def user_room(user_id: uuid.UUID) -> str:
    return f"user:{user_id}"


def inbox_room(user_id: uuid.UUID | str) -> str:
    return f"inbox:{user_id}"

# a room is a promise that you may see every ticket announced in it.
def rooms_for(perms: TicketPermissions) -> set[str]:
    rooms = {user_room(perms.user.id)}
    if perms.sees_all_tickets:
        rooms.add(ALL_TICKETS_ROOM)
    if perms.is_staff:
        rooms.update(team_room(team_id) for team_id in perms.team_ids)
    return rooms


async def emit_ticket_event(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    kind: str,
    *,
    internal: bool = False,
) -> None:
    await db.flush()

    team_id = await db.scalar(select(Ticket.team_id).where(Ticket.id == ticket_id))
    rooms = {ALL_TICKETS_ROOM, team_room(team_id)} if team_id else {ALL_TICKETS_ROOM}

    if not internal:
        owner_ids = await db.scalars(
            select(TicketOwner.user_id).where(TicketOwner.ticket_id == ticket_id)
        )
        rooms.update(user_room(user_id) for user_id in owner_ids)

    payload = json.dumps(
        {
            "rooms": sorted(rooms),
            "event": {"type": "ticket", "kind": kind, "ticket_id": str(ticket_id)},
        }
    )
    await db.execute(select(func.pg_notify(TICKET_CHANNEL, payload)))