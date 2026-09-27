import uuid

from pydantic import Field

from app.schemas.common import APISchema


class RoleRead(APISchema):
    id: uuid.UUID
    name: str
    description: str | None = None
    permissions: list[str]
    is_system: bool


class RoleAssignment(APISchema):
    role: str = Field(min_length=1, max_length=50, examples=["observer"])
