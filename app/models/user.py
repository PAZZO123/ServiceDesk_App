import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audit import Notification, RefreshToken
    from app.models.role import Role
    from app.models.team import TeamMembership
    from app.models.ticket import Comment, TicketOwner


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    sessions_valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Preferences (were in user_profiles)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Africa/Kigali",
        server_default="Africa/Kigali",
    )

    notify_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notify_in_app: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    signature: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Joined on every load so permission checks never lazy-load in async code.
    role: Mapped["Role"] = relationship(back_populates="users", lazy="joined")

    ticket_ownerships: Mapped[list["TicketOwner"]] = relationship(
        back_populates="user"
    )

    memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    comments: Mapped[list["Comment"]] = relationship(back_populates="author")

    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.name})>"
