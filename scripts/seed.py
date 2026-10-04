import argparse
import asyncio
import getpass
import os

from sqlalchemy import func, select

from app.core.cache import CATEGORIES_KEY, TEAMS_KEY, invalidate, redis_client
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.enums import SystemRole, TeamRole
from app.models.role import Role
from app.models.tag import Tag
from app.models.team import Category, Team, TeamMembership
from app.models.user import User

#The Data
TEAMS:list[tuple[str, str, str]]=[
    #(name, slug, description)
    ("Network & Infrastructure",
    "network",
    "Connectivity, Wi-Fi, VPN, servers and cabling"),
    (
        "Hardware Support",
        "hardware",
        "Laptops, desktops, printers, phones and peripherals.",
    ),
    (
        "Software & Applications",
        "software",
        "Business applications, licensing and installations.",
    ),
    (
        "Accounts & Access",
        "accounts",
        "User accounts, passwords, permissions and onboarding.",
    ),
]

CATEGORIES: list[tuple[str, str, int, str]]=[
    #(name, tem_slug, sla_hours, description)
    ("Network Outage", "network", 2,"No connectivity for a site or floor."),
     ("Wi-Fi & Connectivity", "network", 4, "Cannot connect, or unstable connection."),
    ("VPN Access", "network", 4, "Remote access problems."),

    ("Laptop Fault", "hardware", 8, "Hardware failure, damage or performance."),
    ("Printer Problem", "hardware", 8, "Printing, scanning or toner."),
    ("Peripheral Request", "hardware", 24, "Monitors, keyboards, headsets, docks."),

    ("Application Error", "software", 8, "An application crashes or misbehaves."),
    ("Software Installation", "software", 24, "Request to install or license software."),

    ("Password Reset", "accounts", 2, "Locked out or forgotten password."),
    ("New Account Request", "accounts", 24, "Onboarding a new joiner."),
    ("Permission Change", "accounts", 8, "Access to a system, folder or mailbox."),
]

TAGS: list[tuple[str, str]] = [
    # (name, color). Color must be #RRGGBB: the database checks it.
    ("urgent", "#DC2626"),
    ("vip", "#9333EA"),
    ("hardware", "#2563EB"),
    ("network", "#0891B2"),
    ("security", "#EA580C"),
    ("onboarding", "#16A34A"),
    ("remote", "#CA8A04"),
    ("waiting-vendor", "#6B7280"),
]

# Demo accounts: one or more per role, so a demo never starts with sign ups.
# (email, full name, role, team slug or None, role in team or None)
DEMO_USERS: list[tuple[str, str, str, str | None, TeamRole | None]] = [
    ("grace@example.com", "Grace Uwase", "admin", None, None),
    ("eric@example.com", "Eric Mugisha", "observer", None, None),
    ("amina@example.com", "Amina Kayitesi", "agent", "network", TeamRole.LEAD),
    ("olivier@example.com", "Olivier Habimana", "agent", "network", TeamRole.MEMBER),
    ("jean@example.com", "Jean Bosco Niyonzima", "agent", "hardware", TeamRole.LEAD),
    ("diane@example.com", "Diane Ingabire", "agent", "software", TeamRole.LEAD),
    ("kevin@example.com", "Kevin Mutabazi", "agent", "accounts", TeamRole.LEAD),
    ("claire@example.com", "Claire Mukamana", "requester", None, None),
    ("sandrine@example.com", "Sandrine Uwimana", "requester", None, None),
]

# Seeding
async def seed_teams(db)->dict[str, Team]:
    result =await db.execute(select(Team))
    existing={team.slug: team for team in result.scalars().all()}
    created=0
    for name, slug, description in TEAMS:
        if slug in existing:
            continue
        team=Team(name=name, slug=slug, description=description)
        db.add(team)
        existing[slug]=team
        created +=1
    await db.flush()
    print(f"teams  :{created} , {len(TEAMS) - created} already present!")
    return existing

async def seed_categories(db, teams:dict[str, Team])->None:
    result= await db.execute(select(Category))
    existing={(category.team_id, category.name) for category in result.scalars().all()}
    created=0
    for name , team_slug, sla_hours, description in CATEGORIES:
        team=teams.get(team_slug)
        if team is None:
            raise ValueError(
                f"Category {name!r} references unkown team slug {team_slug}"
            )
        if (team.id, name) in existing:
            continue
        db.add(
            Category(
                name=name,
                description=description,
                team_id=team.id,
                sla_hours=sla_hours
            )
        )
        created+=1
    await db.flush()
    print(
        f"categories: {created} created,"
        f"{len(CATEGORIES)- created} already present."
    )

async def seed_tags(db) -> None:
    existing = set((await db.scalars(select(Tag.name))).all())
    created = 0
    for name, color in TAGS:
        if name in existing:
            continue
        db.add(Tag(name=name, color=color))
        created += 1
    await db.flush()
    print(f"tags      : {created} created, {len(TAGS) - created} already present.")
    
def demo_password() -> str:
    password = os.environ.get("DEMO_PASSWORD") or getpass.getpass("Password for the demo accounts: ")
    if len(password) < 8 or password.isdigit():
        raise SystemExit("Demo password: at least 8 characters, not only numbers.")
    return password


async def seed_demo_users(db, teams: dict[str, Team], password: str) -> None:
    roles = {role.name: role for role in (await db.scalars(select(Role))).all()}
    existing = set((await db.scalars(select(func.lower(User.email)))).all())
    hashed = await hash_password(password)  # one hash, shared: bcrypt is slow on purpose
    created = 0
    for email, full_name, role_name, team_slug, team_role in DEMO_USERS:
        if email in existing:
            continue
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed,
            role=roles[role_name],
            is_verified=True,  # demo accounts skip the email link
        )
        db.add(user)
        await db.flush()  # gives user.id, needed by the membership below
        if team_slug is not None and team_role is not None:
            db.add(
                TeamMembership(
                    user_id=user.id, team_id=teams[team_slug].id, role_in_team=team_role
                )
            )
        created += 1
    await db.flush()
    print(f"demo users: {created} created, {len(DEMO_USERS) - created} already present.")

async def promote_user(db, email:str, role_name: str)-> None:
    user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        print(f" promote  : no user found with this email {email!r}")
        return
    role = await db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        print(f" promote  : no role named {role_name!r} (run: alembic upgrade head)")
        return
    previous=user.role.name
    user.role=role
    print(f" promote : {email} {previous} -> {role.name}")


async def main(promote_email: str | None, promote_role: str | None, demo: bool) -> None:
    password = demo_password() if demo else None
    print("\n Seeding reference data....")

    async with AsyncSessionLocal() as db:
        teams = await seed_teams(db)
        await seed_categories(db, teams)
        await seed_tags(db)
        if password is not None:
            await seed_demo_users(db, teams, password)
        if promote_email and promote_role:
            await promote_user(db, promote_email, promote_role)
        await db.commit()
    await invalidate(CATEGORIES_KEY, TEAMS_KEY)
    await redis_client.aclose()
    await engine.dispose()
    print("Done. ")
if __name__ == "__main__":
    parser =argparse.ArgumentParser(description="Seed ServiceDesk reference data.")
    parser.add_argument(
        "--promote",
        metavar="EMAIL",
        help=" Email address of a user to  promote"
    )
    parser.add_argument(
        "--role",
        choices=[r.value for r in SystemRole],
        default='admin',
        help="Role to grant (default: admin)."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Also create the demo accounts (asks for their password).",
    )
    args=parser.parse_args()
    asyncio.run(main(args.promote, args.role, args.demo))
