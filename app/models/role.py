from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Permission

if TYPE_CHECKING:
    from app.models.user import User


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    permissions: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    users: Mapped[list["User"]] = relationship(back_populates="role")

    __table_args__ = (
        Index("ix_roles_permissions", "permissions", postgresql_using="gin"),
    )

    def grants(self, permission: Permission) -> bool:
        return permission.value in self.permissions

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
