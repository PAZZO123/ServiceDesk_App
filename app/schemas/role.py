import uuid

from pydantic import Field

from app.models.enums import Permission
from app.schemas.common import APISchema


class PermissionRead(APISchema):
    code: str
    description: str


class RoleRead(APISchema):
    id: uuid.UUID
    name: str
    description: str | None = None
    permissions: list[str]
    is_system: bool


class RoleAssignment(APISchema):
    role: str = Field(min_length=1, max_length=50, examples=["observer"])
    signature: str | None = Field(default=None, max_length=2000)


# Permission (the enum) as the item type: an unknown code is a 422 before
# any of our code runs.
class RoleCreate(APISchema):
    name: str = Field(
        min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_]*$", examples=["senior_agent"]
    )
    description: str | None = Field(default=None, max_length=255)
    permissions: list[Permission] = Field(default_factory=list)


class RolePermissionsUpdate(APISchema):
    permissions: list[Permission]
