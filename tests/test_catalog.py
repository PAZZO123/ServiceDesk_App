
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from app.core import cache
from app.db.session import AsyncSessionLocal
from app.models.team import Category, Team
from tests.conftest import MakeUser, auth


@pytest.fixture(autouse=True)
async def empty_cache() -> None:
    await cache.redis_client.flushdb()


async def category_names(client: AsyncClient, headers: dict[str, str]) -> set[str]:
    r = await client.get("/api/v1/categories", headers=headers)
    assert r.status_code == 200, r.text
    return {c["name"] for c in r.json()}


async def test_cache_hit_then_invalidate(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    headers = auth(await make_user())

    assert await category_names(client, headers) == {"Wi-Fi", "Password Reset"}
    ttl = await cache.redis_client.ttl(cache.CATEGORIES_KEY)
    assert 0 < ttl <= cache.CATALOG_TTL_SECONDS  # stored WITH an expiry

    async with AsyncSessionLocal() as db:
        db.add(Category(name="VPN", team_id=teams["network"].id, sla_hours=4))
        await db.commit()


    assert await category_names(client, headers) == {"Wi-Fi", "Password Reset"}

  
    await cache.invalidate(cache.CATEGORIES_KEY)
    assert await category_names(client, headers) == {"Wi-Fi", "Password Reset", "VPN"}


async def test_teams_are_cached_too(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team]
) -> None:
    r = await client.get("/api/v1/teams", headers=auth(await make_user()))
    assert r.status_code == 200, r.text
    assert {t["slug"] for t in r.json()} == {"network", "accounts"}
    assert await cache.redis_client.exists(cache.TEAMS_KEY) == 1


async def test_catalog_still_works_when_redis_is_down(
    client: AsyncClient,
    make_user: MakeUser,
    categories: dict[str, Category],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dead = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    monkeypatch.setattr(cache, "redis_client", dead)

    headers = auth(await make_user())
    assert await category_names(client, headers) == {"Wi-Fi", "Password Reset"}
    await dead.aclose()