import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

CATEGORIES_KEY = "catalog:categories:v1"
TEAMS_KEY = "catalog:teams:v1"

CATALOG_TTL_SECONDS = 300

redis_client = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
)


async def get_or_load(
    key: str, ttl: int, loader: Callable[[], Awaitable[Any]]
) -> Any:
    try:
        cached = await redis_client.get(key)
    except RedisError:
        logger.warning("cache_unavailable op=get key=%s", key)
        cached = None

    if cached is not None:
        return json.loads(cached)

    value = await loader()

    try:
        await redis_client.set(key, json.dumps(value), ex=ttl)
    except RedisError:
        logger.warning("cache_unavailable op=set key=%s", key)

    return value


async def invalidate(*keys: str) -> None:
    try:
        await redis_client.delete(*keys)
    except RedisError:
        logger.warning("cache_unavailable op=delete keys=%s", keys)