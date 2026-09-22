import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.audit import Notification, RefreshToken
    from app.models.team import TeamMembership
    from app.models.ticket import Comment, Ticket
    
    
    
class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__="users"
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=UserRole.REQUESTER,
        server_default=UserRole.REQUESTER.value,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    
    profile: Mapped["UserProfile"]= relationship(
        back_populates="user",
        uselist=False, 
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    tickets_requested: Mapped[list["Ticket"]] = relationship(
        back_populates="requester",
        foreign_keys="Ticket.requester_id",   # note: a STRING
    )

    tickets_assigned: Mapped[list["Ticket"]] = relationship(
        back_populates="assignee",
        foreign_keys="Ticket.assignee_id",
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
    
    def __repr__(self)->str:
        return f"<User {self.email} ({self.role.value})>"
    
class UserProfile(Base, TimestampMixin):

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Africa/Kigali",
        server_default="Africa/Kigali",
    )

    notify_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notify_in_app: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    signature: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile user_id={self.user_id}>"