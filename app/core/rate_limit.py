import logging
import math
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from limits import parse
from limits.aio.storage import RedisStorage
from limits.aio.strategies import MovingWindowRateLimiter
from limits.errors import StorageError

from app.core.config import settings
from app.core.exceptions import RateLimited

logger = logging.getLogger(__name__)


_storage = RedisStorage(
    settings.REDIS_URL.replace("redis://", "async+redis://", 1),
    implementation="redispy",
    wrap_exceptions=True,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
)


_limiter = MovingWindowRateLimiter(_storage)


def rate_limit(limit: str, scope: str) -> Callable[[Request], Awaitable[None]]:
    # A FACTORY: rate_limit("5/minute", "login") returns a NEW
    # dependency function with those values baked in - the same
    # pattern as require_permission() in deps.py.
    item = parse(limit)

    async def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"

        try:
            allowed = await _limiter.hit(item, scope, ip)
        except StorageError:
            logger.warning("rate_limit_unavailable scope=%s", scope)
            return

        if not allowed:
            stats = await _limiter.get_window_stats(item, scope, ip)
            retry_after = max(1, math.ceil(stats.reset_time - time.time()))
            logger.warning("rate_limited scope=%s ip=%s", scope, ip)
            raise RateLimited(
                f"Too many attempts. Try again in {retry_after} seconds.",
                details={"retry_after_seconds": retry_after},
            )

    return dependency