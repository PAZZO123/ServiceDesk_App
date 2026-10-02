
from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal
from app.models.audit import Notification
from app.models.enums import NotificationType
from app.models.team import Category, Team
from app.models.ticket import Ticket
from app.models.user import User
from app.workers.sla_tasks import sweep_sla_breaches, sweep_sla_breaches_task
from tests.conftest import MakeUser, auth


@dataclass
class Setup:
    ticket_id: str
    agent: User  # network team
    teammate: User  # network team too
    outsider: User  # accounts team - must never be notified


@pytest.fixture
async def setup(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> Setup:
    requester = await make_user("requester")
    agent = await make_user("agent", email="a1@example.com", team=teams["network"])
    teammate = await make_user("agent", email="a2@example.com", team=teams["network"])
    outsider = await make_user("agent", email="a3@example.com", team=teams["accounts"])
    r = await client.post(
        "/api/v1/tickets",
        headers=auth(requester),
        json={
            "title": "VPN keeps dropping",
            "description": "Disconnects every 5 minutes.",
            "category_id": str(categories["network"].id),
        },
    )
    assert r.status_code == 201, r.text
    return Setup(r.json()["id"], agent, teammate, outsider)


async def run_sql(sql: str, **params: object) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text(sql), params)
        await db.commit()


async def make_overdue(ticket_id: str) -> None:
    await run_sql(
        "UPDATE tickets SET sla_due_at = now() - interval '1 hour' WHERE id = :id",
        id=ticket_id,
    )


async def sweep() -> int:
    async with AsyncSessionLocal() as db:
        return await sweep_sla_breaches(db)


async def notified_users() -> set:
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(
            select(Notification.user_id).where(
                Notification.type == NotificationType.SLA_BREACHED
            )
        )
        return set(rows)


async def test_not_yet_due_is_left_alone(setup: Setup) -> None:
    assert await sweep() == 0


async def test_overdue_unassigned_ticket_notifies_the_team(setup: Setup) -> None:
    await make_overdue(setup.ticket_id)

    assert await sweep() == 1

    async with AsyncSessionLocal() as db:
        ticket = await db.get_one(Ticket, setup.ticket_id)
        assert ticket.sla_breached is True
    assert await notified_users() == {setup.agent.id, setup.teammate.id}


async def test_sweep_is_idempotent(setup: Setup) -> None:
    await make_overdue(setup.ticket_id)
    assert await sweep() == 1
    assert await sweep() == 0
    assert len(await notified_users()) == 2


async def test_assigned_ticket_notifies_only_the_assignee(
    client: AsyncClient, setup: Setup
) -> None:
    r = await client.post(
        f"/api/v1/tickets/{setup.ticket_id}/claim", headers=auth(setup.agent)
    )
    assert r.status_code == 200, r.text
    await make_overdue(setup.ticket_id)

    assert await sweep() == 1
    assert await notified_users() == {setup.agent.id}


@pytest.mark.parametrize("status", ["resolved", "closed"])
async def test_finished_tickets_are_skipped(setup: Setup, status: str) -> None:
    await make_overdue(setup.ticket_id)
    await run_sql(
        "UPDATE tickets SET status = CAST(:s AS ticket_status) WHERE id = :id",
        s=status,
        id=setup.ticket_id,
    )
    assert await sweep() == 0


async def test_soft_deleted_tickets_are_skipped(setup: Setup) -> None:
    await make_overdue(setup.ticket_id)
    await run_sql("UPDATE tickets SET deleted_at = now() WHERE id = :id", id=setup.ticket_id)
    assert await sweep() == 0

def test_celery_task_runs_twice_in_a_row() -> None:
    assert sweep_sla_breaches_task.apply().get() == 0
    assert sweep_sla_breaches_task.apply().get() == 0