
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TeamRole

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.user import User


class Team(Base, UUIDPrimaryKeyMixin, TimestampMixin):

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )
    members: Mapped[list["User"]] = relationship(
        secondary="team_memberships",
        viewonly=True,
    )
    categories: Mapped[list["Category"]] = relationship(back_populates="team")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="team")

    def __repr__(self) -> str:
        return f"<Team {self.slug}>"


class TeamMembership(Base):
    __tablename__ = "team_memberships"
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_in_team: Mapped[TeamRole] = mapped_column(
        SAEnum(
            TeamRole,
            name="team_role",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=TeamRole.MEMBER,
        server_default=TeamRole.MEMBER.value,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="memberships")
    team: Mapped["Team"] = relationship(back_populates="memberships")

    def __repr__(self) -> str:
        return (
            f"<TeamMembership user={self.user_id} "
            f"team={self.team_id} role={self.role_in_team.value}>"
        )


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    team_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    sla_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24, server_default="24"
    )

    team: Mapped["Team"] = relationship(back_populates="categories")

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="category")

    __table_args__ = (
        CheckConstraint(
            "sla_hours > 0",
            name="positive_sla_hours",
        ),
    )

    def __repr__(self) -> str:
        return f"<Category {self.name} sla={self.sla_hours}h>"