# ============================================================
#  tests/test_resolved_count.py - GET /tickets?resolved=true
#  Closing a resolved ticket must not take it out of "resolved":
#  the dashboard's Resolved and Closed counters both go up.
# ============================================================
from httpx import AsyncClient

from app.models.team import Category, Team
from app.models.user import User
from tests.conftest import MakeUser, auth
from tests.test_teams_comments_notifications import new_ticket


async def move(client: AsyncClient, user: User, ticket_id: str, *statuses: str) -> None:
    for status in statuses:
        r = await client.post(
            f"/api/v1/tickets/{ticket_id}/status", headers=auth(user), json={"status": status}
        )
        assert r.status_code == 200, r.text


async def ids(client: AsyncClient, user: User, **params: str) -> set[str]:
    r = await client.get("/api/v1/tickets", headers=auth(user), params=params)
    assert r.status_code == 200, r.text
    return {t["id"] for t in r.json()["items"]}


async def test_closed_after_resolving_counts_as_resolved_and_closed(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    network = categories["network"]

    resolved_then_closed = await new_ticket(client, requester, network)
    still_resolved = await new_ticket(client, requester, network)
    closed_never_resolved = await new_ticket(client, requester, network)
    reopened = await new_ticket(client, requester, network)
    still_open = await new_ticket(client, requester, network)

    await move(client, agent, resolved_then_closed, "resolved")
    await move(client, requester, resolved_then_closed, "closed")
    await move(client, agent, still_resolved, "resolved")
    # The requester closes it straight away: it was never resolved.
    await move(client, requester, closed_never_resolved, "closed")
    # Resolved, then the fix did not hold: back to work.
    await move(client, agent, reopened, "resolved", "in_progress")

    assert await ids(client, agent, resolved="true") == {resolved_then_closed, still_resolved}
    assert await ids(client, agent, status="closed") == {resolved_then_closed, closed_never_resolved}
    assert await ids(client, agent, resolved="false") == {closed_never_resolved, reopened, still_open}
