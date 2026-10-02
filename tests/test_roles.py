# ============================================================
#  tests/test_roles.py - permissions as tables, role management.
# ============================================================
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.enums import Permission
from app.models.role import PermissionRecord
from app.models.team import Category, Team
from app.models.user import User
from tests.conftest import MakeUser, auth


async def create_role(
    client: AsyncClient, actor: User, name: str, permissions: list[str]
) -> dict:
    r = await client.post(
        "/api/v1/roles",
        headers=auth(actor),
        json={"name": name, "permissions": permissions},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_permission_table_matches_the_code() -> None:
    # The enum (what the code can check) and the table (what roles can be
    # given) must list the same permissions. A new enum member without a
    # migration inserting its row fails here.
    async with AsyncSessionLocal() as db:
        codes = set(await db.scalars(select(PermissionRecord.code)))
    assert codes == {p.value for p in Permission}


async def test_migration_kept_every_role_as_it_was(
    client: AsyncClient, make_user: MakeUser
) -> None:
    admin = await make_user("admin")
    r = await client.get("/api/v1/roles", headers=auth(admin))
    assert r.status_code == 200, r.text
    roles = {role["name"]: set(role["permissions"]) for role in r.json()}

    assert roles["requester"] == set()
    assert roles["agent"] == {"ticket.work", "comment.read_internal", "ticket.starts_high"}
    assert roles["observer"] == {"ticket.view_all", "comment.read_internal"}
    assert roles["admin"] == {p.value for p in Permission} - {"ticket.starts_high"}


async def test_supervisor_scenario_extra_permission_for_one_agent(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    admin = await make_user("admin")
    agent = await make_user("agent", team=teams["network"])
    requester = await make_user("requester")

    r = await client.post(
        "/api/v1/tickets",
        headers=auth(requester),
        json={
            "title": "Old duplicate ticket",
            "description": "Raised twice by mistake.",
            "category_id": str(categories["network"].id),
        },
    )
    ticket_id = r.json()["id"]

    # Before: an agent may not delete tickets.
    r = await client.delete(f"/api/v1/tickets/{ticket_id}", headers=auth(agent))
    assert r.status_code == 403, r.text

    # A new role through the API - no code change, no SQL.
    await create_role(
        client,
        admin,
        "senior_agent",
        ["ticket.work", "comment.read_internal", "ticket.starts_high", "ticket.delete"],
    )
    r = await client.patch(
        f"/api/v1/users/{agent.id}/role",
        headers=auth(admin),
        json={"role": "senior_agent"},
    )
    assert r.status_code == 200, r.text

    # After: the same agent can.
    r = await client.delete(f"/api/v1/tickets/{ticket_id}", headers=auth(agent))
    assert r.status_code == 204, r.text


async def test_only_role_managers_manage_roles(
    client: AsyncClient, make_user: MakeUser
) -> None:
    agent = await make_user("agent")
    r = await client.post(
        "/api/v1/roles", headers=auth(agent), json={"name": "sneaky", "permissions": []}
    )
    assert r.status_code == 403, r.text
    assert (await client.get("/api/v1/roles", headers=auth(agent))).status_code == 403


async def test_unknown_permission_and_duplicate_name_are_rejected(
    client: AsyncClient, make_user: MakeUser
) -> None:
    admin = await make_user("admin")
    r = await client.post(
        "/api/v1/roles",
        headers=auth(admin),
        json={"name": "typo_role", "permissions": ["ticket.wrok"]},
    )
    assert r.status_code == 422, r.text  # the old text[] accepted this silently

    r = await client.post(
        "/api/v1/roles", headers=auth(admin), json={"name": "agent", "permissions": []}
    )
    assert r.status_code == 409, r.text


async def test_cannot_grant_what_you_do_not_have(
    client: AsyncClient, make_user: MakeUser
) -> None:
    admin = await make_user("admin")
    await create_role(client, admin, "team_lead", ["role.manage", "ticket.work"])
    lead = await make_user("team_lead", email="lead@example.com")

    # The lead holds role.manage but not ticket.delete.
    r = await client.post(
        "/api/v1/roles",
        headers=auth(lead),
        json={"name": "deleter", "permissions": ["ticket.delete"]},
    )
    assert r.status_code == 403, r.text

    await create_role(client, lead, "helper", ["ticket.work"])


async def test_cannot_edit_your_own_role(client: AsyncClient, make_user: MakeUser) -> None:
    admin = await make_user("admin")
    role = await create_role(client, admin, "team_lead", ["role.manage", "ticket.work"])
    lead = await make_user("team_lead", email="lead@example.com")

    r = await client.put(
        f"/api/v1/roles/{role['id']}/permissions",
        headers=auth(lead),
        json={"permissions": ["role.manage"]},
    )
    assert r.status_code == 403, r.text


async def test_permission_change_is_audited(client: AsyncClient, make_user: MakeUser) -> None:
    admin = await make_user("admin")
    role = await create_role(client, admin, "helper", ["ticket.work"])

    r = await client.put(
        f"/api/v1/roles/{role['id']}/permissions",
        headers=auth(admin),
        json={"permissions": ["ticket.work", "comment.read_internal"]},
    )
    assert r.status_code == 200, r.text
    assert sorted(r.json()["permissions"]) == ["comment.read_internal", "ticket.work"]

    async with AsyncSessionLocal() as db:
        row = await db.scalar(
            select(AuditLog).where(AuditLog.action == "role_permissions_changed")
        )
    assert row is not None
    assert row.actor_id == admin.id
    assert row.changes == {"added": ["comment.read_internal"], "removed": []}


async def test_delete_role_rules(client: AsyncClient, make_user: MakeUser) -> None:
    admin = await make_user("admin")
    roles = {r["name"]: r for r in (await client.get("/api/v1/roles", headers=auth(admin))).json()}

    # Built-in role -> 409.
    r = await client.delete(f"/api/v1/roles/{roles['agent']['id']}", headers=auth(admin))
    assert r.status_code == 409, r.text

    # Custom role still in use -> 409.
    used = await create_role(client, admin, "helper", ["ticket.work"])
    await make_user("helper", email="helper@example.com")
    r = await client.delete(f"/api/v1/roles/{used['id']}", headers=auth(admin))
    assert r.status_code == 409, r.text

    # Unused custom role -> 204, and its grants go with it (ON DELETE CASCADE).
    unused = await create_role(client, admin, "temp", ["ticket.work"])
    r = await client.delete(f"/api/v1/roles/{unused['id']}", headers=auth(admin))
    assert r.status_code == 204, r.text
    async with AsyncSessionLocal() as db:
        left = await db.scalar(
            text("SELECT count(*) FROM role_permissions WHERE role_id = :id"),
            {"id": unused["id"]},
        )
    assert left == 0
