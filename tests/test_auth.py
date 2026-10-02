from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.user import User
from tests.conftest import PASSWORD, MakeUser, auth

NEW_PASSWORD = "Another-Horse-77"


async def login(client: AsyncClient, user: User, password: str = PASSWORD) -> dict:
    r = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def refresh(client: AsyncClient, token: str) -> tuple[int, dict]:
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    return r.status_code, r.json()


def bearer(access: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access}"}


async def test_refresh_rotates_the_token(client: AsyncClient, make_user: MakeUser) -> None:
    pair = await login(client, await make_user())
    status, new = await refresh(client, pair["refresh_token"])
    assert status == 200, new
    # Rotation: every refresh hands out a NEW refresh token.
    assert new["refresh_token"] != pair["refresh_token"]
    r = await client.get("/api/v1/auth/me", headers=bearer(new["access_token"]))
    assert r.status_code == 200, r.text


async def test_reused_refresh_token_kills_the_whole_family(
    client: AsyncClient, make_user: MakeUser
) -> None:
    pair = await login(client, await make_user())
    _, second = await refresh(client, pair["refresh_token"])

    status, body = await refresh(client, pair["refresh_token"])
    assert status == 401
    assert body["error"]["code"] == "token_reuse_detected"

    status, _ = await refresh(client, second["refresh_token"])
    assert status == 401


async def test_access_token_is_not_a_refresh_token(
    client: AsyncClient, make_user: MakeUser
) -> None:
    # The token_type claim keeps the two kinds apart in BOTH directions.
    pair = await login(client, await make_user())
    status, _ = await refresh(client, pair["access_token"])
    assert status == 401
    r = await client.get("/api/v1/auth/me", headers=bearer(pair["refresh_token"]))
    assert r.status_code == 401


async def test_logout_ends_every_session(client: AsyncClient, make_user: MakeUser) -> None:
    user = await make_user()
    laptop = await login(client, user)
    phone = await login(client, user)

    r = await client.post("/api/v1/auth/logout", json={"refresh_token": laptop["refresh_token"]})
    assert r.status_code == 200, r.text

    assert (await refresh(client, phone["refresh_token"]))[0] == 401
    r = await client.get("/api/v1/auth/me", headers=bearer(phone["access_token"]))
    assert r.status_code == 401


async def test_login_right_after_logout_works(client: AsyncClient, make_user: MakeUser) -> None:
    user = await make_user()
    pair = await login(client, user)
    await client.post("/api/v1/auth/logout", json={"refresh_token": pair["refresh_token"]})

    fresh = await login(client, user)
    r = await client.get("/api/v1/auth/me", headers=bearer(fresh["access_token"]))
    assert r.status_code == 200, r.text


async def test_token_issued_after_session_reset_is_accepted(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User).where(User.id == user.id).values(sessions_valid_from=datetime.now(UTC))
        )
        await db.commit()
    r = await client.get("/api/v1/auth/me", headers=auth(user))
    assert r.status_code == 200, r.text


async def test_change_password(client: AsyncClient, make_user: MakeUser) -> None:
    user = await make_user()
    r = await client.post(
        "/api/v1/auth/change-password",
        headers=auth(user),
        json={
            "current_password": "wrong",
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert r.status_code == 401, r.text

    r = await client.post(
        "/api/v1/auth/change-password",
        headers=auth(user),
        json={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert r.status_code == 200, r.text

    # The old password no longer works, the new one does.
    r = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": PASSWORD}
    )
    assert r.status_code == 401
    await login(client, user, NEW_PASSWORD)