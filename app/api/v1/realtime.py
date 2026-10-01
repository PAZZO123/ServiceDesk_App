import asyncio
import contextlib
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_current_user
from app.core.exceptions import AccountNotVerified, AppError, InvalidToken
from app.core.permissions import TicketPermissions, load_team_ids
from app.core.security import TokenType, decode_token
from app.db.session import AsyncSessionLocal
from app.realtime.events import rooms_for
from app.realtime.hub import Subscriber, hub
from app.services.user_service import UserService

router =APIRouter(tags=["Realtime"])
AUTH_TIMEOUT_SECONDS=5
CLOSE_UNAUTHORIZED=4401

async def _authenticate(token:str)->tuple[set[str], float]:
    #the rooms this token may join and when the token expires
    async with AsyncSessionLocal( ) as db:
        user= await get_current_user(token, UserService(db))
        if not user.is_verified:
            raise AccountNotVerified()
        perms=TicketPermissions(user=user, team_ids=await load_team_ids(db, user))
        expires_at=decode_token(token, TokenType.ACCESS)["exp"]
        return rooms_for(perms), float(expires_at)
    
async def _forward(websocket: WebSocket, subscriber: Subscriber) -> None:
    with contextlib.suppress(WebSocketDisconnect):
        # Sent after subscribing, so nothing can slip through the gap.
        await websocket.send_json({"type": "ready"})
        while True:
            await websocket.send_json(await subscriber.get())


async def _wait_until_closed(websocket: WebSocket) -> None:
    with contextlib.suppress(WebSocketDisconnect):
        while True:
            await websocket.receive_text()


@router.websocket("/ws")
async def live_updates(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        message = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
        token = message.get("token") if isinstance(message, dict) else None
        if not isinstance(token, str):
            raise InvalidToken()
        rooms, expires_at = await _authenticate(token)
    except WebSocketDisconnect:
        return
    except (TimeoutError, ValueError, KeyError, AppError):
        await websocket.close(CLOSE_UNAUTHORIZED, "Authentication failed.")
        return

    subscriber = hub.subscribe(rooms)
    forward = asyncio.create_task(_forward(websocket, subscriber))
    closed = asyncio.create_task(_wait_until_closed(websocket))
    try:
        done, _ = await asyncio.wait(
            {forward, closed},
            timeout=max(0.0, expires_at - time.time()),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            await websocket.close(CLOSE_UNAUTHORIZED, "Token expired.")
        for task in done:
            task.result()  
    finally:
        forward.cancel()
        closed.cancel()
        hub.unsubscribe(subscriber)