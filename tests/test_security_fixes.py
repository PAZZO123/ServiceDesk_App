# ============================================================
#  tests/test_security_fixes.py - the security review of 2026-10-05.
#  One block per fix. Each test fails on the code before the fix.
# ============================================================
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import _reset_serializer, create_password_reset_token
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog, RefreshToken
from app.models.user import User
from tests.conftest import PASSWORD, MakeUser, auth

NEW_PASSWORD = "Brand-New-Pass-7"


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict:
    r = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def make_user_manager(client: AsyncClient, make_user: MakeUser) -> User:
    # A helpdesk lead who may manage users and nothing else.
    admin = await make_user("admin", email="boss@example.com")
    r = await client.post(
        "/api/v1/roles",
        headers=auth(admin),
        json={"name": "user_admin", "permissions": ["user.manage"]},
    )
    assert r.status_code == 201, r.text
    lead = await make_user("requester", email="lead@example.com")
    r = await client.patch(
        f"/api/v1/users/{lead.id}/role", headers=auth(admin), json={"role": "user_admin"}
    )
    assert r.status_code == 200, r.text
    return lead


# ---- Fix 1: user.manage is not a ladder to admin ------------------------


async def test_user_manager_cannot_hand_out_admin(
    client: AsyncClient, make_user: MakeUser
) -> None:
    lead = await make_user_manager(client, make_user)
    my_second_account = await make_user("requester", email="alt@example.com")

    r = await client.patch(
        f"/api/v1/users/{my_second_account.id}/role",
        headers=auth(lead),
        json={"role": "admin"},
    )
    assert r.status_code == 403, r.text


async def test_user_manager_cannot_demote_an_admin(
    client: AsyncClient, make_user: MakeUser
) -> None:
    lead = await make_user_manager(client, make_user)
    other_admin = await make_user("admin", email="other-admin@example.com")

    r = await client.patch(
        f"/api/v1/users/{other_admin.id}/role",
        headers=auth(lead),
        json={"role": "requester"},
    )
    assert r.status_code == 403, r.text


async def test_admin_can_still_assign_every_built_in_role(
    client: AsyncClient, make_user: MakeUser
) -> None:
    admin = await make_user("admin")
    user = await make_user("requester")
    for role in ("agent", "observer", "admin", "requester"):
        r = await client.patch(
            f"/api/v1/users/{user.id}/role", headers=auth(admin), json={"role": role}
        )
        assert r.status_code == 200, (role, r.text)


# ---- Fix 3: a reset link works once ------------------------------------


async def confirm_reset(client: AsyncClient, token: str) -> int:
    r = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": token,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    return r.status_code


async def test_reset_link_cannot_be_used_twice(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    token = create_password_reset_token(user.email, user.hashed_password)

    assert await confirm_reset(client, token) == 200
    # Same link again (from a forwarded email, a browser history...): refused.
    assert await confirm_reset(client, token) == 401
    await login(client, user.email, NEW_PASSWORD)


async def test_old_style_reset_link_is_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    # What create_password_reset_token produced before the fix: the bare email.
    old_token = _reset_serializer.dumps(user.email)
    assert await confirm_reset(client, old_token) == 401


# ---- Fix 4: rate limits on the endpoints that had none ------------------


async def test_change_password_is_rate_limited(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    body = {
        "current_password": "wrong-guess",
        "new_password": NEW_PASSWORD,
        "confirm_password": NEW_PASSWORD,
    }
    for _ in range(5):
        r = await client.post("/api/v1/auth/change-password", headers=auth(user), json=body)
        assert r.status_code == 401, r.text
    r = await client.post("/api/v1/auth/change-password", headers=auth(user), json=body)
    assert r.status_code == 429, r.text


async def test_reset_confirm_is_rate_limited(client: AsyncClient) -> None:
    for _ in range(10):
        assert await confirm_reset(client, "guessed-token-123") == 401
    assert await confirm_reset(client, "guessed-token-123") == 429


# ---- Fix 5: the audit IP cannot be chosen by the client -----------------


async def test_x_forwarded_for_is_not_trusted(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.66"},
    )
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as db:
        ip = await db.scalar(
            select(RefreshToken.ip_address).where(RefreshToken.user_id == user.id)
        )
    assert ip is not None
    assert str(ip) != "203.0.113.66"


# ---- Fix 6: an account can be disabled ----------------------------------


async def set_active(client: AsyncClient, actor: User, target: User, value: bool) -> int:
    r = await client.patch(
        f"/api/v1/users/{target.id}/active",
        headers=auth(actor),
        json={"is_active": value},
    )
    return r.status_code


async def test_disabled_account_is_locked_out_everywhere(
    client: AsyncClient, make_user: MakeUser
) -> None:
    admin = await make_user("admin")
    user = await make_user()
    pair = await login(client, user.email)
    bearer = {"Authorization": f"Bearer {pair['access_token']}"}

    assert await set_active(client, admin, user, False) == 200

    # The access token in the attacker's hands stops working at once...
    assert (await client.get("/api/v1/auth/me", headers=bearer)).status_code == 403
    # ...so does the refresh token, and a new login.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 401, r.text
    r = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": PASSWORD}
    )
    assert r.status_code == 403, r.text

    # Enabled again: a fresh login works, the OLD refresh token stays dead.
    assert await set_active(client, admin, user, True) == 200
    await login(client, user.email)
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 401, r.text

    async with AsyncSessionLocal() as db:
        actions = set(
            await db.scalars(select(AuditLog.action).where(AuditLog.entity_id == user.id))
        )
    assert {"account_disabled", "account_enabled"} <= actions


async def test_nobody_disables_themselves_or_a_stronger_user(
    client: AsyncClient, make_user: MakeUser
) -> None:
    lead = await make_user_manager(client, make_user)
    admin = await make_user("admin", email="target-admin@example.com")
    requester = await make_user("requester", email="plain@example.com")

    assert await set_active(client, admin, admin, False) == 403  # yourself
    assert await set_active(client, lead, admin, False) == 403  # more powers than you
    assert await set_active(client, lead, requester, False) == 200  # fine


async def test_only_user_managers_disable_accounts(
    client: AsyncClient, make_user: MakeUser
) -> None:
    agent = await make_user("agent")
    requester = await make_user("requester")
    assert await set_active(client, agent, requester, False) == 403
