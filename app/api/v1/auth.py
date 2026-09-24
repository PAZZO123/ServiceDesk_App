from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import (
    AuthSvc,
    ClientInfo,
    UserSvc,
    VerifiedUser,
)
from app.core.email import (
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)
from app.core.exceptions import AlreadyVerified, InvalidCredentials, InvalidToken
from app.core.security import (
    create_email_verification_token,
    create_password_reset_token,
    verify_email_verification_token,
    verify_password,
    verify_password_reset_token,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailRequest,
    PasswordResetConfirm,
    RefreshRequest,
    RegisterResponse,
    TokenPair,
    TokenRequest,
)
from app.schemas.common import Message
from app.schemas.user import (
    UserCreate,
    UserProfileUpdate,
    UserRead,
    UserUpdate,
    UserWithProfile,
)

router = APIRouter(prefix="/auth", tags=["Authenticated"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="create an account",
    responses={409: {"description": "Email Address already registered."}},
)
async def register(
    data: UserCreate, background: BackgroundTasks, users: UserSvc
) -> RegisterResponse:
    user = await users.create(data)
    token = create_email_verification_token(user.email)
    background.add_task(
        send_verification_email,
        to=user.email,
        full_name=user.full_name,
        token=token,
    )
    return RegisterResponse(
        message="Account created . Check your email to activate it.",
        user=UserRead.model_validate(user),
    )


@router.post(
    "/verify-email",
    response_model=Message,
    summary="Confirm an email address",
)
async def verify_email(
    data: TokenRequest,
    background: BackgroundTasks,
    users: UserSvc,
) -> Message:
    email = verify_email_verification_token(data.token)
    if email is None:
        raise InvalidToken()
    user =await users.require_by_email(email)
    if user.is_verified:
        raise AlreadyVerified()
    await users.set_verified(user)

    background.add_task(send_welcome_email, to=user.email, full_name=user.full_name)
    return Message(message="Email Verified. You can now sign in.")


@router.post(
    "/resend-verification",
    response_model=Message,
    summary="Send the verification email again",
)
async def resend_verification(
    data: EmailRequest,
    background: BackgroundTasks,
    users: UserSvc,
) -> Message:

    user = await users.get_by_email(data.email)

    if user is not None and not user.is_verified:
        background.add_task(
            send_verification_email,
            to=user.email,
            full_name=user.full_name,
            token=create_email_verification_token(user.email),
        )

    return Message(
        message="If that address has an unverified account, a new link has been sent."
    )


# Session
@router.post(
    "/login",
    response_model=TokenPair,
    summary="Sign in",
    responses={
        401: {"description": "Incorrect email or password"},
        403: {"description": "Account not verified, or disabled"},
    },
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthSvc,
    client: ClientInfo,
) -> TokenPair:
    user = await auth.authenticate(form.username, form.password)
    return await auth.issue_token_pair(
        user,
        user_agent=client["user_agent"],
        ip_address=client["ip_address"],
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Rotate the refresh token",
    responses={401: {"description": "Invalid, expired, or reused token"}},
)
async def refresh(
    data: RefreshRequest,
    auth: AuthSvc,
    client: ClientInfo,
) -> TokenPair:
    return await auth.rotate_refresh_token(
        data.refresh_token,
        user_agent=client["user_agent"],
        ip_address=client["ip_address"],
    )


@router.post("/logout", response_model=Message, summary="sign out")
async def logout(data: RefreshRequest, auth: AuthSvc) -> Message:
    await auth.logout(data.refresh_token)
    return Message(message="Signed out.")


# Current User


@router.get(
    "/me",
    response_model=UserWithProfile,
    summary="Get the signed-in user",
)
async def read_me(user: VerifiedUser) -> UserWithProfile:
    return UserWithProfile.model_validate(user)


@router.patch("/me", response_model=UserWithProfile, summary="Update your name")
async def update_me(
    data: UserUpdate,
    user: VerifiedUser,
    users: UserSvc,
) -> UserWithProfile:

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)
    await users.db.commit()
    return UserWithProfile.model_validate(user)


@router.patch(
    "/me/profile",
    response_model=UserWithProfile,
    summary="Update your preferences",
)
async def update_my_profile(
    data: UserProfileUpdate,
    user: VerifiedUser,
    users: UserSvc,
) -> UserWithProfile:
    await users.update_profile(user, data)
    return UserWithProfile.model_validate(user)


# Passwords


@router.post(
    "/password-reset",
    response_model=Message,
    summary="Request a password reset link",
)
async def request_password_reset(
    data: EmailRequest,
    background: BackgroundTasks,
    users: UserSvc,
) -> Message:
    user = await users.get_by_email(data.email)

    if user is not None and user.is_active:
        background.add_task(
            send_password_reset_email,
            to=user.email,
            full_name=user.full_name,
            token=create_password_reset_token(user.email),
        )

    return Message(
        message="If that address has an account, a reset link has been sent."
    )


@router.post(
    "/password-reset/confirm",
    response_model=Message,
    summary="Set a new password using an emailed token",
)
async def confirm_password_reset(
    data: PasswordResetConfirm,
    users: UserSvc,
    auth: AuthSvc,
) -> Message:
    email = verify_password_reset_token(data.token)
    if email is None:
        raise InvalidToken()

    user = await users.require_by_email(email)

    await users.set_password(user, data.new_password)
    await auth.revoke_all_for_user(user.id)

    return Message(message="Password updated. You have been signed out of all devices.")


@router.post(
    "/change-password",
    response_model=Message,
    summary="Change your password while signed in",
)
async def change_password(
    data: ChangePasswordRequest,
    user: VerifiedUser,
    users: UserSvc,
    auth: AuthSvc,
) -> Message:
    if not await verify_password(data.current_password, user.hashed_password):
        raise InvalidCredentials("Your current password is incorrect.")

    await users.set_password(user, data.new_password)
    await auth.revoke_all_for_user(user.id)

    return Message(message="Password changed. You have been signed out of all devices.")
