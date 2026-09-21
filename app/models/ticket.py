import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TicketPriority, TicketStatus

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
 
    requester_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
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
    requester: Mapped["User"] = relationship(
        back_populates="tickets_requested",
        foreign_keys=[requester_id],
    )

    assignee: Mapped["User | None"] = relationship(
        back_populates="tickets_assigned",
        foreign_keys=[assignee_id],
    )

    category: Mapped["Category"] = relationship(back_populates="tickets")
    team: Mapped["Team"] = relationship(back_populates="tickets")

    merged_into: Mapped["Ticket | None"] = relationship(
        "Ticket",
        back_populates="duplicates",
        remote_side="Ticket.id",
        foreign_keys=[merged_into_id],
    )

    duplicates: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="merged_into",
        foreign_keys=[merged_into_id],
    )

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

    def __repr__(self) -> str:
        return f"<Ticket {self.reference} {self.status.value}>"


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

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


    body: Mapped[str] = mapped_column(Text, nullable=False)

    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    ticket: Mapped["Ticket"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")

    parent: Mapped["Comment | None"] = relationship(
        "Comment",
        back_populates="replies",
        remote_side="Comment.id",   # same pattern as merged_into
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        kind = "internal" if self.is_internal else "public"
        return f"<Comment {self.id} on {self.ticket_id} ({kind})>"