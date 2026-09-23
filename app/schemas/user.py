import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.common import APISchema, PasswordStr


# ======================================================================
#  INPUT
# ======================================================================
class UserCreate(APISchema):
    email: EmailStr = Field(
        max_length=255,
        description="Work email address.",
    )

    full_name: str = Field(
        min_length=2,
        max_length=120,
        description="Full name as it should appear to colleagues.",
    )

    password: PasswordStr

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower()


class UserUpdate(APISchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class UserProfileUpdate(APISchema):
    timezone: str | None = Field(default=None, max_length=64)
    notify_email: bool | None = None
    notify_in_app: bool | None = None
    signature: str | None = Field(default=None, max_length=2000)


class UserPublic(APISchema):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None


class UserRead(UserPublic):
    email: EmailStr
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserProfileRead(APISchema):
    timezone: str
    notify_email: bool
    notify_in_app: bool
    signature: str | None = None


class UserWithProfile(UserRead):
    profile: UserProfileRead | None = None
