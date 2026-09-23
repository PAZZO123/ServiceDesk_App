from pydantic import EmailStr, Field, model_validator

from app.schemas.common import APISchema, PasswordStr
from app.schemas.user import UserRead


class TokenPair(APISchema):
    access_token: str
    refresh_token: str

    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the access token expires.")


class RefreshRequest(APISchema):
    refresh_token: str = Field(min_length=10)


class RegisterResponse(APISchema):
    message: str
    user: UserRead


class TokenRequest(APISchema):
    token: str = Field(min_length=10)


class EmailRequest(APISchema):
    email: EmailStr = Field(max_length=255)

    @model_validator(mode="after")
    def normalise(self) -> "EmailRequest":
        self.email = self.email.lower()
        return self


class PasswordResetConfirm(APISchema):
    token: str = Field(min_length=10, description="From the emailed link.")
    new_password: PasswordStr
    confirm_password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def passwords_must_match(self) -> "PasswordResetConfirm":

        if self.new_password != self.confirm_password:
            raise ValueError("The two passwords do not match.")
        return self


class ChangePasswordRequest(APISchema):
    current_password: str = Field(min_length=1)
    new_password: PasswordStr
    confirm_password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("The two passwords do not match.")
        return self

    @model_validator(mode="after")
    def new_password_must_differ(self) -> "ChangePasswordRequest":
        if self.current_password == self.new_password:
            raise ValueError("The new password must be different from the current one.")
        return self
