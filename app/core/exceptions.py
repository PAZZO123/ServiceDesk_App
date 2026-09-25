import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Something went wrong."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:

        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class UserNotFound(NotFoundError):
    code = "user_not_found"
    message = "User not found."


class TicketNotFound(NotFoundError):
    code = "ticket_not_found"
    message = "Ticket not found."


class TeamNotFound(NotFoundError):
    code = "team_not_found"
    message = "Team not found."


class CategoryNotFound(NotFoundError):
    code = "category_not_found"
    message = "Category not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "That action conflicts with the current state."


class UserAlreadyExists(ConflictError):
    code = "user_already_exists"
    message = "An account with this email address already exists."


class AlreadyVerified(ConflictError):
    code = "already_verified"
    message = "This account has already been verified."


class InvalidStatusTransition(ConflictError):
    code = "invalid_status_transition"
    message = "That status change is not allowed."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "not_authenticated"
    message = "Authentication required."


class InvalidCredentials(AuthenticationError):
    code = "invalid_credentials"
    message = "Incorrect email or password."


class InvalidToken(AuthenticationError):
    code = "invalid_token"
    message = "The token is invalid or has expired."


class TokenReuseDetected(AuthenticationError):
    code = "token_reuse_detected"
    message = "Session revoked for security reasons. Please sign in again."


class PermissionDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class AccountNotVerified(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "account_not_verified"
    message = "Please verify your email address before signing in."


class AccountDisabled(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "account_disabled"
    message = "This account has been disabled. Contact your administrator."


class BadRequest(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"
    message = "The request could not be processed."


class PasswordMismatch(BadRequest):
    code = "password_mismatch"
    message = "The two passwords do not match."


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down and try again shortly."


class FileTooLarge(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "file_too_large"
    message = "The uploaded file is too large."


class UnsupportedFileType(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_file_type"
    message = "That file type is not allowed."
class CommentNotFound(NotFoundError):
    code = "comment_not_found"
    message = "Comment not found."

class AttachmentNotFound(NotFoundError):
    code = "attachment_not_found"
    message = "Attachment not found."
    
def _envelope(error_body: dict[str, Any], request: Request) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        error_body["request_id"] = request_id
    return {"error": error_body}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error code=%s status=%s path=%s",
        exc.code,
        exc.status_code,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.to_dict(), request),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields = [
        {
            "field": ".".join(str(part) for part in err["loc"][1:]) or "body",
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envelope(
            {
                "code": "validation_error",
                "message": "Some fields are invalid.",
                "details": {"fields": fields},
            },
            request,
        ),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(
            {"code": f"http_{exc.status_code}", "message": str(exc.detail)},
            request,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:

    logger.exception(
        "unhandled_exception path=%s method=%s",
        request.url.path,
        request.method,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope(
            {
                "code": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
            },
            request,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
