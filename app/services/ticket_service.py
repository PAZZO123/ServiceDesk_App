
import base64
import uuid
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import TicketNotFound
from app.models.ticket import Ticket
from app.schemas.common import PaginationParams
from app.schemas.ticket import SortOrder, TicketFilters, TicketSortField

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.core.exceptions import (
    CategoryNotFound,
    InvalidStatusTransition,
    TicketNotFound,
)
from app.models.audit import AuditLog, Notification
from app.models.enums import NotificationType, TicketStatus
from app.models.team import Category
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketUpdate

ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.IN_PROGRESS: {
        TicketStatus.OPEN,
        TicketStatus.WAITING,
        TicketStatus.RESOLVED,
    },
    TicketStatus.WAITING: {
        TicketStatus.OPEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
    },
    TicketStatus.RESOLVED: {
        TicketStatus.CLOSED,
        TicketStatus.IN_PROGRESS,
    },
    TicketStatus.CLOSED: set(),
}


class TicketService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _base_query(self) -> Select:
        return (
            select(Ticket)
            .where(Ticket.deleted_at.is_(None))
            .options(
                joinedload(Ticket.requester),
                joinedload(Ticket.assignee),
                joinedload(Ticket.category),
                joinedload(Ticket.team),
            )
        )

    def _conditions(self, filters: TicketFilters) -> list:
        conditions = []

        if filters.status is not None:
            conditions.append(Ticket.status == filters.status)

        if filters.priority is not None:
            conditions.append(Ticket.priority == filters.priority)

        if filters.category_id is not None:
            conditions.append(Ticket.category_id == filters.category_id)

        if filters.team_id is not None:
            conditions.append(Ticket.team_id == filters.team_id)

        if filters.requester_id is not None:
            conditions.append(Ticket.requester_id == filters.requester_id)

        if filters.sla_breached is not None:
            conditions.append(Ticket.sla_breached == filters.sla_breached)

        if filters.unassigned:
            conditions.append(Ticket.assignee_id.is_(None))
        elif filters.assignee_id is not None:
            conditions.append(Ticket.assignee_id == filters.assignee_id)

        if filters.created_after is not None:
            conditions.append(Ticket.created_at >= filters.created_after)

        if filters.created_before is not None:
            conditions.append(Ticket.created_at <= filters.created_before)

        if filters.q:
            pattern = (
                filters.q.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            term = f"%{pattern}%"

            conditions.append(
                or_(
                    Ticket.title.ilike(term, escape="\\"),
                    Ticket.description.ilike(term, escape="\\"),
                )
            )
 

        return conditions

    def _apply_sort(self, stmt: Select, filters: TicketFilters) -> Select:
        columns = {
            TicketSortField.CREATED_AT: Ticket.created_at,
            TicketSortField.UPDATED_AT: Ticket.updated_at,
            TicketSortField.PRIORITY: Ticket.priority,
            TicketSortField.SLA_DUE_AT: Ticket.sla_due_at,
            TicketSortField.STATUS: Ticket.status,
        }

        column = columns[filters.sort]
        direction = column.desc() if filters.order == SortOrder.DESC else column.asc()
        return stmt.order_by(direction, Ticket.id.desc())

    async def list_tickets(
        self,
        filters: TicketFilters,
        pagination: PaginationParams,
        *,
        extra_conditions: list | None = None,
    ) -> tuple[list[Ticket], int]:
        conditions = self._conditions(filters)
        if extra_conditions:
            conditions.extend(extra_conditions)
        count_stmt = (
            select(func.count(Ticket.id))
            .where(Ticket.deleted_at.is_(None))
            .where(*conditions)
        )
        total = await self.db.scalar(count_stmt) or 0

        # Query 2: the page itself.
        stmt = self._base_query().where(*conditions)
        stmt = self._apply_sort(stmt, filters)
        stmt = stmt.offset(pagination.offset).limit(pagination.size)

        result = await self.db.execute(stmt)
        tickets = list(result.unique().scalars().all())

        return tickets, total

    async def list_tickets_cursor(
        self,
        filters: TicketFilters,
        limit: int = 20,
        cursor: str | None = None,
        *,
        extra_conditions: list | None = None,
    ) -> tuple[list[Ticket], str | None]:
        conditions = self._conditions(filters)
        if extra_conditions:
            conditions.extend(extra_conditions)

        if cursor:
            created_at, ticket_id = self._decode_cursor(cursor)
          
            conditions.append(
                func.row(Ticket.created_at, Ticket.id)
                < func.row(created_at, ticket_id)
            )

        stmt = (
            self._base_query()
            .where(*conditions)
            .order_by(Ticket.created_at.desc(), Ticket.id.desc())
            .limit(limit + 1)
        )

        result = await self.db.execute(stmt)
        rows = list(result.unique().scalars().all())

        has_more = len(rows) > limit
        rows = rows[:limit]

        next_cursor = (
            self._encode_cursor(rows[-1].created_at, rows[-1].id)
            if has_more and rows
            else None
        )

        return rows, next_cursor

    @staticmethod
    def _encode_cursor(created_at: datetime, ticket_id: uuid.UUID) -> str:
        raw = f"{created_at.isoformat()}|{ticket_id}"
        return base64.urlsafe_b64encode(raw.encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
        """Unpack a cursor, rejecting anything malformed."""
        try:
            raw = base64.urlsafe_b64decode(cursor.encode()).decode()
            created_str, id_str = raw.split("|")
            return datetime.fromisoformat(created_str), uuid.UUID(id_str)
        except (ValueError, UnicodeDecodeError) as exc:
            raise TicketNotFound("Invalid pagination cursor.") from exc
    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        """Fetch one ticket, or None. Deleted tickets are invisible."""
        stmt = self._base_query().where(Ticket.id == ticket_id)
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def require_by_id(self, ticket_id: uuid.UUID) -> Ticket:
        """Fetch one ticket, or raise 404."""
        ticket = await self.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFound()
        return ticket

    async def get_by_reference(self, reference: str) -> Ticket | None:
        """Look a ticket up by its human reference, e.g. TCK-2026-0042."""
        stmt = self._base_query().where(Ticket.reference == reference.upper())
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()
    
    
    async def _next_reference(self) -> str:
        year = datetime.now(timezone.utc).year
        lock_key = hash(f"ticket_reference:{year}") % (2**31)

        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": lock_key},
        )
        prefix = f"TCK-{year}-"

        highest = await self.db.scalar(
            select(func.max(Ticket.reference)).where(
                Ticket.reference.like(f"{prefix}%")
            )
        )

        if highest is None:
            next_number = 1
        else:
      
            next_number = int(highest.rsplit("-", 1)[1]) + 1

        return f"{prefix}{next_number:04d}"

    async def create(
        self,
        data: TicketCreate,
        requester: User,
        *,
        ip_address: str | None = None,
    ) -> Ticket:
        category = await self.db.get(Category, data.category_id)

        if category is None:
            raise CategoryNotFound()

        now = datetime.now(timezone.utc)

        ticket = Ticket(
            reference=await self._next_reference(),
            title=data.title,
            description=data.description,
            priority=data.priority,
            category_id=category.id,
            team_id=category.team_id,
            requester_id=requester.id,
            sla_due_at=now + timedelta(hours=category.sla_hours),

            extra_data=data.extra_data,
         
        )
        self.db.add(ticket)
        await self.db.flush()

        self._add_audit(
            actor_id=requester.id,
            entity_id=ticket.id,
            action="created",
            changes={
                "reference": ticket.reference,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "category": category.name,
            },
            ip_address=ip_address,
        )
        await self._notify_team(ticket, category)
        await self.db.commit()
        return await self.require_by_id(ticket.id)


    async def update(
        self,
        ticket: Ticket,
        data: TicketUpdate,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> Ticket:
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return ticket 
        changes: dict[str, Any] = {}

        for field, new_value in updates.items():
            old_value = getattr(ticket, field)

            if old_value == new_value:
                continue  
            changes[field] = {
                "from": old_value.value if hasattr(old_value, "value") else old_value,
                "to": new_value.value if hasattr(new_value, "value") else new_value,
            }
            setattr(ticket, field, new_value)

        if not changes:
            return ticket

        if "category_id" in updates:
            category = await self.db.get(Category, updates["category_id"])
            if category is None:
                raise CategoryNotFound()
            ticket.team_id = category.team_id
            changes["team_id"] = {"to": str(category.team_id)}

        self._add_audit(
            actor_id=actor.id,
            entity_id=ticket.id,
            action="updated",
            changes=changes,
            ip_address=ip_address,
        )

        await self.db.commit()
        return await self.require_by_id(ticket.id)

    async def change_status(
        self,
        ticket: Ticket,
        new_status: TicketStatus,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> Ticket:
        current = ticket.status

        if new_status == current:
            return ticket

        if new_status not in ALLOWED_TRANSITIONS[current]:
            raise InvalidStatusTransition(
                f"Cannot move a ticket from {current.value} to {new_status.value}."
            )

        ticket.status = new_status

       
        now = datetime.now(timezone.utc)

        if new_status == TicketStatus.RESOLVED and ticket.resolved_at is None:
            ticket.resolved_at = now
        if new_status == TicketStatus.CLOSED and ticket.closed_at is None:
            ticket.closed_at = now

        self._add_audit(
            actor_id=actor.id,
            entity_id=ticket.id,
            action="status_changed",
            changes={"status": {"from": current.value, "to": new_status.value}},
            ip_address=ip_address,
        )

        await self.db.commit()
        return await self.require_by_id(ticket.id)

    async def soft_delete(
        self,
        ticket: Ticket,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> None:
        if ticket.deleted_at is not None:
            return  

        ticket.deleted_at = datetime.now(timezone.utc)

        self._add_audit(
            actor_id=actor.id,
            entity_id=ticket.id,
            action="deleted",
            changes={"reference": ticket.reference},
            ip_address=ip_address,
        )

        await self.db.commit()
    def _add_audit(
        self,
        *,
        actor_id: uuid.UUID | None,
        entity_id: uuid.UUID,
        action: str,
        changes: dict[str, Any],
        ip_address: str | None = None,
        entity_type: str = "ticket",
    ) -> None:
      
        self.db.add(
            AuditLog(
                actor_id=actor_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                changes=changes,
                ip_address=ip_address,
            )
        )

    async def _notify_team(self, ticket: Ticket, category: Category) -> None:
        from app.models.team import TeamMembership

        member_ids = (
            await self.db.execute(
                select(TeamMembership.user_id).where(
                    TeamMembership.team_id == ticket.team_id
                )
            )
        ).scalars().all()

        for user_id in member_ids:
            self.db.add(
                Notification(
                    user_id=user_id,
                    type=NotificationType.TICKET_ASSIGNED,
                    payload={
                        "ticket_id": str(ticket.id),
                        "reference": ticket.reference,
                        "title": ticket.title,
                        "priority": ticket.priority.value,
                        "category": category.name,
                    },
                )
            )
        # Staged, not committed - the caller's commit covers these too.