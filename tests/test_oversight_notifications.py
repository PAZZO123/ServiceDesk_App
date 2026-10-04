
from typing import Any

from httpx import AsyncClient
from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.team import Category, Team
from app.models.user import User
from tests.conftest import MakeUser, auth
from tests.test_sla import make_overdue, sweep
from tests.test_teams_comments_notifications import comment, new_ticket


async def inbox(client: AsyncClient, user: User) -> list[dict[str, Any]]:
    r = await client.get("/api/v1/notifications", headers=auth(user))
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def types(client: AsyncClient, user: User) -> list[str]:
    return sorted(n["type"] for n in await inbox(client, user))


async def test_new_ticket_reaches_admin_and_observer_once(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    admin = await make_user("admin")
    observer = await make_user("observer")
    # An admin who is ALSO in the team must get one notification, not two.
    admin_in_team = await make_user("admin", email="lead@example.com", team=teams["network"])
    requester = await make_user("requester")

    await new_ticket(client, requester, categories["network"])

    [n] = await inbox(client, admin)
    assert n["type"] == "ticket_created"
    assert n["payload"]["created_by"] == requester.full_name
    assert await types(client, observer) == ["ticket_created"]
    assert await types(client, admin_in_team) == ["ticket_assigned"]
    assert await inbox(client, requester) == []


async def test_status_assignment_and_comment_reach_oversight(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    observer = await make_user("observer")
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])

    r = await client.post(f"/api/v1/tickets/{ticket_id}/claim", headers=auth(agent))
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/status", headers=auth(agent), json={"status": "in_progress"}
    )
    assert r.status_code == 200, r.text
    await comment(client, agent, ticket_id, "Replacing the cable now.")

    items = {n["type"]: n["payload"] for n in await inbox(client, observer)}
    assert set(items) == {
        "ticket_created",
        "ticket_assigned",
        "ticket_status_changed",
        "comment_added",
    }
    # Not "assigned to you": the observer is told WHO got it.
    assert items["ticket_assigned"]["assignee"] == agent.full_name


async def test_internal_note_only_for_roles_that_may_read_it(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    admin = await make_user("admin")
    # A custom role: sees every ticket, but NOT internal notes.
    r = await client.post(
        "/api/v1/roles",
        headers=auth(admin),
        json={"name": "auditor", "permissions": ["ticket.view_all"]},
    )
    assert r.status_code == 201, r.text
    auditor = await make_user("auditor")
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])

    await comment(client, agent, ticket_id, "Between us: it is the switch.", internal=True)

    # A role created through the API is included with no code change...
    assert "ticket_created" in await types(client, auditor)
    # ...but it never hears about a note it is not allowed to read.
    assert "comment_added" not in await types(client, auditor)
    assert "comment_added" in await types(client, admin)


async def test_sla_breach_reaches_oversight(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    observer = await make_user("observer")
    requester = await make_user("requester")
    ticket_id = await new_ticket(client, requester, categories["network"])

    await make_overdue(ticket_id)
    assert await sweep() == 1

    assert "sla_breached" in await types(client, observer)


async def test_in_app_switched_off_means_no_oversight_notifications(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    admin = await make_user("admin")
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == admin.id).values(notify_in_app=False))
        await db.commit()
    requester = await make_user("requester")

    await new_ticket(client, requester, categories["network"])

    assert await inbox(client, admin) == []


async def test_admin_on_the_ticket_gets_one_comment_notification(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    # The admin raised this ticket, so the normal comment rules already
    # notify them as the requester. Oversight must not add a second one.
    admin = await make_user("admin")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, admin, categories["network"])

    await comment(client, agent, ticket_id, "Looking at it now.")

    assert [n["type"] for n in await inbox(client, admin)] == ["comment_added"]