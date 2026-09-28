import asyncio
import json
import logging

import asyncpg  

from app.core.config import settings
from app.realtime.events import NOTIFICATION_CHANNEL, TICKET_CHANNEL, inbox_room
from app.realtime.hub import RESYNC, hub

logger = logging.getLogger(__name__)

RETRY_SECONDS = 5


def _on_ticket_event(connection: object, pid: int, channel: str, payload: str) -> None:
    try:
        data = json.loads(payload)
        hub.dispatch(data["rooms"], data["event"])
    except (ValueError, KeyError, TypeError):
        logger.exception("Bad payload on %s: %r", channel, payload)


def _on_notification(connection: object, pid: int, channel: str, payload: str) -> None:
    hub.dispatch([inbox_room(payload)], {"type": "notification"})


async def _listen_until_lost(
    connection: asyncpg.Connection, *, after_gap: bool
) -> None:
    lost = asyncio.Event()
    connection.add_termination_listener(lambda _connection: lost.set())
    await connection.add_listener(TICKET_CHANNEL, _on_ticket_event)
    await connection.add_listener(NOTIFICATION_CHANNEL, _on_notification)
    logger.info("Realtime: listening for database events")

    if after_gap:
        hub.broadcast(RESYNC)

    await lost.wait()


async def listen_forever() -> None:
  #One PostgreSQL connection per process that only LISTENs.
   
    reconnecting = False
    while True:
        try:
            connection = await asyncpg.connect(settings.sync_database_url)
        except (OSError, asyncpg.PostgresError) as exc:
            logger.warning("Realtime: cannot reach the database (%s), retrying", exc)
            await asyncio.sleep(RETRY_SECONDS)
            continue

        try:
            await _listen_until_lost(connection, after_gap=reconnecting)
            logger.warning("Realtime: lost the database connection, reconnecting")
        except (OSError, asyncpg.PostgresError) as exc:
            logger.warning("Realtime: listener failed (%s), reconnecting", exc)
        finally:
            reconnecting = True
            if not connection.is_closed():
                await connection.close()