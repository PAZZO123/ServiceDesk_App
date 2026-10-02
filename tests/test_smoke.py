
from httpx import AsyncClient

from app.models.team import Category
from tests.conftest import PASSWORD, MakeUser, auth


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200


async def test_login_right_and_wrong_password(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user("agent")

    ok = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": PASSWORD}
    )
    assert ok.status_code == 200, ok.text
    assert {"access_token", "refresh_token"} <= ok.json().keys()

    bad = await client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "wrong-password"},
    )
    assert bad.status_code == 401


async def test_me_needs_a_token(client: AsyncClient, make_user: MakeUser) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    user = await make_user("observer")
    r = await client.get("/api/v1/auth/me", headers=auth(user))
    assert r.status_code == 200, r.text
    assert r.json()["role"]["name"] == "observer"


async def test_each_test_starts_empty(make_user: MakeUser) -> None:
    await make_user("agent")


async def test_requester_can_create_ticket(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    user = await make_user("requester")
    r = await client.post(
        "/api/v1/tickets",
        headers=auth(user),
        json={
            "title": "Wi-Fi is down",
            "description": "No Wi-Fi on floor 2 since 9 am.",
            "category_id": str(categories["network"].id),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["reference"].startswith("TCK-")
    assert body["priority"] == "medium"