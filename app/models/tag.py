
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket


ticket_tags = Table(
    "ticket_tags",
    Base.metadata,
    Column(
        "ticket_id",
        PGUUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        PGUUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Tag(Base, UUIDPrimaryKeyMixin, TimestampMixin):

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )

    color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#6B7280", server_default="#6B7280"
    )

    tickets: Mapped[list["Ticket"]] = relationship(
        secondary="ticket_tags",
        back_populates="tags",
    )

    __table_args__ = (
        CheckConstraint(
            "color ~ '^#[0-9A-Fa-f]{6}$'",
            name="valid_hex_color",
        ),
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"