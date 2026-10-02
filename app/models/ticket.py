import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TicketOwnerRole, TicketPriority, TicketStatus

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.tag import Tag
    from app.models.team import Category, Team
    from app.models.user import User


class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A reported problem."""

    __tablename__ = "tickets"
    reference: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
        index=True,
    )

    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(
            TicketPriority,
            name="ticket_priority",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=TicketPriority.MEDIUM,
        server_default=TicketPriority.MEDIUM.value,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    sla_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    first_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sla_breached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        deferred=True,
    )

    # The only writable path to ticket_owners; removing an item deletes the row.
    owners: Mapped[list["TicketOwner"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    category: Mapped["Category"] = relationship(back_populates="tickets")
    team: Mapped["Team"] = relationship(back_populates="tickets")

    comments: Mapped[list["Comment"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    tags: Mapped[list["Tag"]] = relationship(
        secondary="ticket_tags",
        back_populates="tickets",
    )

    __table_args__ = (
        Index(
            "ix_tickets_queue",
            "status",
            "priority",
            "created_at",
        ),
        Index(
            "ix_tickets_active",
            "team_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_tickets_search",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    # Read-only views over `owners` (must be loaded - see TicketService._base_query)
    def _owners_with_role(self, role: TicketOwnerRole) -> list["User"]:
        return [owner.user for owner in self.owners if owner.role == role]

    @property
    def requester(self) -> "User | None":
        found = self._owners_with_role(TicketOwnerRole.REQUESTER)
        return found[0] if found else None

    @property
    def assignee(self) -> "User | None":
        found = self._owners_with_role(TicketOwnerRole.ASSIGNEE)
        return found[0] if found else None

    @property
    def watchers(self) -> list["User"]:
        return self._owners_with_role(TicketOwnerRole.WATCHER)

    def has_owner(self, user_id: uuid.UUID, role: TicketOwnerRole | None = None) -> bool:
        return any(
            owner.user_id == user_id and (role is None or owner.role == role)
            for owner in self.owners
        )

    def __repr__(self) -> str:
        return f"<Ticket {self.reference} {self.status.value}>"


class TicketOwner(Base):
    __tablename__ = "ticket_owners"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    role: Mapped[TicketOwnerRole] = mapped_column(
        SAEnum(
            TicketOwnerRole,
            name="ticket_owner_role",
            values_callable=lambda e: [m.value for m in e],
        ),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="owners")
    user: Mapped["User"] = relationship(back_populates="ticket_ownerships")

    __table_args__ = (
        Index("ix_ticket_owners_user_id_role", "user_id", "role"),
        # One requester and one assignee per ticket; watchers are unlimited.
        Index(
            "uq_ticket_owners_single_holder",
            "ticket_id",
            "role",
            unique=True,
            postgresql_where=text("role IN ('requester', 'assignee')"),
        ),
    )

    def __repr__(self) -> str:
        return f"<TicketOwner {self.role.value} user={self.user_id} ticket={self.ticket_id}>"


class Comment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "comments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    ticket: Mapped["Ticket"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        kind = "internal" if self.is_internal else "public"
        return f"<Comment {self.id} on {self.ticket_id} ({kind})>"
