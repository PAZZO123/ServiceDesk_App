from collections.abc import AsyncGenerator
import pytest
from httpx import AsyncClient
from limits.aio.storage import RedisStorage
from limits.aio.strategies import MovingWindowRateLimiter

from app.core import cache, rate_limit
from tests.conftest import PASSWORD, MakeUser

NOBODY = "nobody@example.com"


@pytest.fixture(autouse=True)
async def empty_counters() -> AsyncGenerator[None, None]:
    await cache.redis_client.flushdb()
    yield
    await cache.redis_client.flushdb()


async def login(client: AsyncClient, email: str, password: str) -> int:
    r = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    return r.status_code


async def test_sixth_login_in_a_minute_is_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user("requester")

    for _ in range(5):
        assert await login(client, user.email, "wrong-password") == 401

    r = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": "wrong"}
    )
    assert r.status_code == 429, r.text
    error = r.json()["error"]  # our normal error envelope
    assert error["code"] == "rate_limited"
    assert 1 <= error["details"]["retry_after_seconds"] <= 60

    assert await login(client, user.email, PASSWORD) == 429


async def test_scopes_are_counted_separately(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user("requester")
    for _ in range(6):
        await login(client, user.email, "wrong-password")

    # Login is blocked, but password reset has its own counter.
    r = await client.post("/api/v1/auth/password-reset", json={"email": NOBODY})
    assert r.status_code == 200, r.text


async def test_password_reset_allows_three_per_hour(client: AsyncClient) -> None:
    for _ in range(3):
        r = await client.post("/api/v1/auth/password-reset", json={"email": NOBODY})
        assert r.status_code == 200, r.text
    r = await client.post("/api/v1/auth/password-reset", json={"email": NOBODY})
    assert r.status_code == 429, r.text


async def test_refresh_is_not_limited(client: AsyncClient) -> None:
    for _ in range(10):
        r = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"}
        )
        assert r.status_code == 401, r.text


async def test_login_still_works_when_redis_is_down(
    client: AsyncClient, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    dead = RedisStorage(
        "async+redis://127.0.0.1:1/0",
        implementation="redispy",
        wrap_exceptions=True,
        socket_connect_timeout=0.2,
    )
    monkeypatch.setattr(rate_limit, "_limiter", MovingWindowRateLimiter(dead))

    user = await make_user("requester")
    # 7 attempts, all reach the password check: no counting, but no crash.
    for _ in range(6):
        assert await login(client, user.email, "wrong-password") == 401
    assert await login(client, user.email, PASSWORD) == 200