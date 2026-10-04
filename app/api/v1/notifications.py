import asyncio
import time
import uuid
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import DbSession, NotificationSvc, VerifiedUser, get_token
from app.core.security import TokenType, decode_token
from app.db.session import AsyncSessionLocal
from app.realtime.events import inbox_room
from app.realtime.hub import hub
from app.schemas.common import Page, PaginationParams
from app.schemas.notification import NotificationRead, UnreadCount
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=Page[NotificationRead], summary="Your notifications, newest first")
async def list_notifications(
    svc: NotificationSvc,
    user: VerifiedUser,
    pagination: Annotated[PaginationParams, Depends()],
    unread_only: bool = False,
) -> Page[NotificationRead]:
    items, total = await svc.list_for_user(user, pagination, unread_only=unread_only)
    return Page.create(
        items=[NotificationRead.model_validate(n) for n in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/unread-count", response_model=UnreadCount, summary="How many are unread")
async def unread_count(svc: NotificationSvc, user: VerifiedUser) -> UnreadCount:
    return UnreadCount(unread=await svc.unread_count(user.id))


@router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark every notification as read",
)
async def mark_all_read(svc: NotificationSvc, user: VerifiedUser) -> None:
    await svc.mark_all_read(user)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark one notification as read",
)
async def mark_read(notification_id: uuid.UUID, svc: NotificationSvc, user: VerifiedUser):
    return await svc.mark_read(user, notification_id)


@router.get(
    "/stream",
    response_class=EventSourceResponse,
    summary="Live unread count (Server-Sent Events)",
)
async def stream_unread_count(
    user: VerifiedUser,
    token: Annotated[str, Depends(get_token)],
    db: DbSession,
) -> AsyncIterable[ServerSentEvent]:
    await db.close()
    expires_at = decode_token(token, TokenType.ACCESS)["exp"]

    subscriber = hub.subscribe({inbox_room(user.id)})
    try:
        while True:
            async with AsyncSessionLocal() as session:
                count = await NotificationService(session).unread_count(user.id)
            yield ServerSentEvent(event="unread", data=UnreadCount(unread=count))

            seconds_left = expires_at - time.time()
            if seconds_left <= 0:
                return
            try:
                await asyncio.wait_for(subscriber.get(), seconds_left)
            except TimeoutError:
                return
    finally:
        hub.unsubscribe(subscriber)