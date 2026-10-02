from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Permission

if TYPE_CHECKING:
    from app.models.user import User


# Which role has which permission. Deleting a role removes its grants;
# a permission that is still granted cannot be deleted.
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        PGUUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        PGUUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Index("ix_role_permissions_permission_id", "permission_id"),
)


# One row per Permission enum member: the code decides WHAT can be checked,
# the role_permissions rows decide WHO has it. Named PermissionRecord so it
# does not clash with the Permission enum used in every check.
class PermissionRecord(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    description: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PermissionRecord {self.code}>"


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # selectin: loaded together with the role (User.role is joined), so
    # grants() never lazy-loads in async code.
    permission_records: Mapped[list[PermissionRecord]] = relationship(
        secondary=role_permissions,
        lazy="selectin",
        order_by=PermissionRecord.code,
    )

    users: Mapped[list["User"]] = relationship(back_populates="role")

    # Same shape as the old text[] column, so schemas and the client are unchanged.
    @property
    def permissions(self) -> list[str]:
        return [p.code for p in self.permission_records]

    def grants(self, permission: Permission) -> bool:
        return any(p.code == permission.value for p in self.permission_records)

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
