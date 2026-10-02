
import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings

if not settings.TEST_DATABASE_URL.endswith("_test"):
    raise RuntimeError(
        "TEST_DATABASE_URL must name a database ending in '_test'. "
        "Refusing to run: the tests delete all rows."
    )
settings.DATABASE_URL = settings.TEST_DATABASE_URL
settings.REDIS_URL = settings.REDIS_URL.rsplit("/", 1)[0] + "/15"

# above. `noqa: E402` tells ruff "imports not at the top" is on purpose.
import asyncpg  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.enums import TeamRole  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.team import Category, Team, TeamMembership  # noqa: E402
from app.models.user import User  # noqa: E402

PASSWORD = "Correct-Horse-42"


#  Build the schema ONCE per test run
async def _reset_schema() -> None:
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


def pytest_sessionstart(session: pytest.Session) -> None:
    asyncio.run(_reset_schema())
    command.upgrade(Config("alembic.ini"), "head")


#Every test starts with empty tables 
KEEP_TABLES = {"roles"}


@pytest.fixture(autouse=True)  
async def clean_tables() -> None:
    names = ", ".join(
        t.name for t in Base.metadata.sorted_tables if t.name not in KEEP_TABLES
    )
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session", autouse=True)
async def dispose_engine() -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()


#The HTTP client
@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# Users
@pytest.fixture(scope="session")
async def password_hash() -> str:
    return await hash_password(PASSWORD)


MakeUser = Callable[..., Awaitable[User]]


@pytest.fixture
async def make_user(password_hash: str) -> MakeUser:
    async def _make(
        role: str = "requester",
        email: str | None = None,
        team: Team | None = None,
        verified: bool = True,
    ) -> User:
        async with AsyncSessionLocal() as db:
            role_row = await db.scalar(select(Role).where(Role.name == role))
            assert role_row is not None, f"role {role!r} not found - did the migration run?"
            user = User(
                email=email or f"{role}@example.com",
                full_name=f"Test {role.title()}",
                hashed_password=password_hash,
                role=role_row,
                is_verified=verified,
            )
            db.add(user)
            await db.flush()
            if team is not None:
                db.add(
                    TeamMembership(
                        user_id=user.id, team_id=team.id, role_in_team=TeamRole.MEMBER
                    )
                )
            await db.commit()
            # expire_on_commit=False in session.py keeps the attributes
            # readable after the session is closed.
            return user

    return _make


def auth(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role.name)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def teams() -> dict[str, Team]:
    async with AsyncSessionLocal() as db:
        network = Team(name="Network", slug="network")
        accounts = Team(name="Accounts", slug="accounts")
        db.add_all([network, accounts])
        await db.commit()
        return {"network": network, "accounts": accounts}


@pytest.fixture
async def categories(teams: dict[str, Team]) -> dict[str, Category]:
    async with AsyncSessionLocal() as db:
        wifi = Category(name="Wi-Fi", team_id=teams["network"].id, sla_hours=4)
        reset = Category(name="Password Reset", team_id=teams["accounts"].id, sla_hours=2)
        db.add_all([wifi, reset])
        await db.commit()
        return {"network": wifi, "accounts": reset}