from typing import Any

from httpx import AsyncClient

from app.models.team import Category, Team
from app.models.user import User
from tests.conftest import MakeUser, auth
from tests.test_teams_comments_notifications import comment, new_ticket


async def inbox(client: AsyncClient, user: User) -> list[dict[str, Any]]:
    r = await client.get("/api/v1/notifications", headers=auth(user))
    assert r.status_code == 200, r.text
    return r.json()["items"]


def of_type(items: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [n for n in items if n["type"] == kind]


async def test_status_change_tells_the_requester_not_the_actor(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    # The agent takes the ticket, so they are an owner too (the assignee).
    r = await client.post(f"/api/v1/tickets/{ticket_id}/claim", headers=auth(agent))
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/status", headers=auth(agent), json={"status": "in_progress"}
    )
    assert r.status_code == 200, r.text

    [n] = of_type(await inbox(client, requester), "ticket_status_changed")
    assert n["payload"]["from"] == "open"
    assert n["payload"]["to"] == "in_progress"
    assert n["payload"]["changed_by"] == agent.full_name
    # The agent is an owner, but made the change, so is not told about it.
    assert of_type(await inbox(client, agent), "ticket_status_changed") == []


async def test_mention_replaces_the_comment_notification(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")  # requester@example.com -> "@requester"
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])

    await comment(client, agent, ticket_id, "@requester can you try another cable?")

    # One comment, one notification: "mentioned", not also "new comment".
    assert [n["type"] for n in await inbox(client, requester)] == ["ticket_mentioned"]


async def test_mention_reaches_a_team_mate(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    sam = await make_user("agent", email="sam.lee@example.com", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])

    # An internal note: team mates may read it, so the mention counts.
    await comment(client, agent, ticket_id, "Thanks @Sam.Lee.", internal=True)

    [n] = of_type(await inbox(client, sam), "ticket_mentioned")
    assert n["payload"]["author"] == agent.full_name
    assert n["payload"]["internal"] is True


async def test_no_mention_for_people_who_cannot_read_it(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    bob = await make_user("requester", email="bob@example.com")
    sam = await make_user("agent", email="sam@example.com", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    before = len(await inbox(client, requester))

    await comment(client, agent, ticket_id, "@bob had the same problem last week.", internal=True)
    await comment(client, agent, ticket_id, "@requester keeps restarting it.", internal=True)
    await comment(client, agent, ticket_id, "Old mailbox was it@sam, now retired.", internal=True)

    assert await inbox(client, bob) == []
    assert len(await inbox(client, requester)) == before
    assert of_type(await inbox(client, sam), "ticket_mentioned") == []


async def test_ambiguous_handle_mentions_nobody(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    sam_a = await make_user("agent", email="sam@example.com", team=teams["network"])
    sam_b = await make_user("agent", email="sam@other.org", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])

    await comment(client, agent, ticket_id, "@sam please look.", internal=True)

    # Two people are "sam": better to tell nobody than the wrong one.
    assert of_type(await inbox(client, sam_a), "ticket_mentioned") == []
    assert of_type(await inbox(client, sam_b), "ticket_mentioned") == []