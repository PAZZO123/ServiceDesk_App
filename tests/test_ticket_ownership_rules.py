from httpx import AsyncClient

from app.models.team import Category, Team
from tests.conftest import MakeUser, auth
from tests.test_teams_comments_notifications import comment, new_ticket


async def test_a_claimed_ticket_cannot_be_taken_by_another_agent(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    amina = await make_user("agent", email="amina@example.com", team=teams["network"])
    olivier = await make_user("agent", email="olivier@example.com", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])

    r = await client.post(f"/api/v1/tickets/{ticket_id}/claim", headers=auth(amina))
    assert r.status_code == 200, r.text

    # Olivier may neither claim it...
    r = await client.post(f"/api/v1/tickets/{ticket_id}/claim", headers=auth(olivier))
    assert r.status_code == 403, r.text
    assert amina.full_name in r.text  # the message names who has it
    # ...nor assign it to himself through the other door.
    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        headers=auth(olivier),
        json={"assignee_id": str(olivier.id)},
    )
    assert r.status_code == 403, r.text


async def test_the_assignee_hands_over_and_the_admin_reassigns(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    admin = await make_user("admin")
    amina = await make_user("agent", email="amina@example.com", team=teams["network"])
    olivier = await make_user("agent", email="olivier@example.com", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    await client.post(f"/api/v1/tickets/{ticket_id}/claim", headers=auth(amina))

    # The agent who owns it may hand it over to a team mate.
    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        headers=auth(amina),
        json={"assignee_id": str(olivier.id)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee"]["id"] == str(olivier.id)

    # The admin (ticket.reassign) may move it, although Olivier owns it now.
    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        headers=auth(admin),
        json={"assignee_id": str(amina.id)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee"]["id"] == str(amina.id)


async def test_staff_change_only_category_and_priority(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    admin = await make_user("admin")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    url = f"/api/v1/tickets/{ticket_id}"

    # The requester's own words are theirs: not even the admin rewrites them.
    r = await client.patch(url, headers=auth(admin), json={"title": "Changed by the admin"})
    assert r.status_code == 403, r.text
    r = await client.patch(url, headers=auth(agent), json={"description": "Rewritten by the agent."})
    assert r.status_code == 403, r.text

    r = await client.patch(url, headers=auth(agent), json={"priority": "high"})
    assert r.status_code == 200, r.text
    # The requester still edits their own text while the ticket is open.
    r = await client.patch(url, headers=auth(requester), json={"title": "Monitor still flickers"})
    assert r.status_code == 200, r.text


async def test_agent_who_raised_a_ticket_edits_its_text(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    # Staff can be requesters too: then the text is their own.
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, agent, categories["network"])
    r = await client.patch(
        f"/api/v1/tickets/{ticket_id}", headers=auth(agent), json={"title": "My own laptop is slow"}
    )
    assert r.status_code == 200, r.text


async def test_category_fix_moves_the_ticket_out_of_the_old_team(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    admin = await make_user("admin")
    network_agent = await make_user("agent", email="net@example.com", team=teams["network"])
    accounts_agent = await make_user("agent", email="acc@example.com", team=teams["accounts"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    await client.post(f"/api/v1/tickets/{ticket_id}/claim", headers=auth(network_agent))
    await comment(client, network_agent, ticket_id, "This looks like a password problem.")

    # The requester picked the wrong category: the admin fixes it.
    r = await client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=auth(admin),
        json={"category_id": str(categories["accounts"].id)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["team"]["id"] == str(teams["accounts"].id)
    # The old team's agent no longer owns it...
    assert r.json()["assignee"] is None

    # ...and no longer sees it at all; the new team does.
    r = await client.get(f"/api/v1/tickets/{ticket_id}", headers=auth(network_agent))
    assert r.status_code == 404, r.text
    r = await client.get(f"/api/v1/tickets/{ticket_id}", headers=auth(accounts_agent))
    assert r.status_code == 200, r.text

    # The conversation stays with the ticket.
    r = await client.get(f"/api/v1/tickets/{ticket_id}/comments", headers=auth(requester))
    assert [c["body"] for c in r.json()["items"]] == ["This looks like a password problem."]