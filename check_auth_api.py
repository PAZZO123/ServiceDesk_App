"""Fire many ticket creations at once and check every reference is unique."""
import asyncio

from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal, engine
from app.models.audit import AuditLog, Notification
from app.models.team import Category
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import TicketService

CONCURRENT = 25


async def create_one(category_id, user_id, n: int) -> str:
    # Each task gets its OWN session. Sharing one session across
    # concurrent tasks is undefined behaviour - a session is not
    # thread-safe or task-safe.
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        svc = TicketService(db)
        ticket = await svc.create(
            TicketCreate(
                title=f"Concurrent test ticket number {n}",
                description="Created to test reference generation under load.",
                category_id=category_id,
            ),
            requester=user,
        )
        return ticket.reference


async def main() -> None:
    await engine.dispose(close=False)

    async with AsyncSessionLocal() as db:
        category = await db.scalar(
            select(Category).where(Category.name == "Wi-Fi & Connectivity")
        )
        user = await db.scalar(select(User))
        if category is None or user is None:
            print("Run `python -m scripts.seed` and register a user first.")
            return
        category_id, user_id = category.id, user.id

    print(f"Firing {CONCURRENT} creations simultaneously...")

    # asyncio.gather starts them all before any finishes - this is what
    # makes them genuinely concurrent rather than sequential.
    refs = await asyncio.gather(
        *(create_one(category_id, user_id, n) for n in range(CONCURRENT))
    )

    unique = set(refs)
    print(f"  created : {len(refs)}")
    print(f"  unique  : {len(unique)}")
    print(f"  sample  : {sorted(refs)[:5]}")

    if len(unique) == len(refs):
        print("\nPASS - every reference is unique.")
    else:
        dupes = [r for r in unique if refs.count(r) > 1]
        print(f"\nFAIL - duplicates: {dupes}")

    # Cleanup
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(select(Ticket.id))).scalars().all()
        await db.execute(delete(Notification))
        await db.execute(delete(AuditLog))
        await db.execute(delete(Ticket))
        await db.commit()
        print(f"Cleaned up {len(ids)} tickets.")

    await engine.dispose()


asyncio.run(main())