import argparse
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal, engine
from app.models.enums import UserRole
from app.models.team import Team, Category
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
    existing={category.name for category in result.scalars().all()}
    created=0
    for name , team_slug, sla_hours, description in CATEGORIES:
        if name in existing:
            continue
        team=teams.get(team_slug)
        if team is None:
            raise ValueError(
                f"Category {name!r} references unkown team slug {team_slug}"
            )
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
    
    
async def promote_user(db, email:str, role: UserRole)-> None:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        print(f" promote  : no user found with this email {email!r}")
        return
    previous=user.role
    user.role=role
    print(f" promote : {email} {previous.value} -> { role.value}")
    

async def main( promote_email: str| None, promote_role: str|None)->None:
    print("\n Seeding reference data....")
    
    async with AsyncSessionLocal() as db:
        teams= await seed_teams(db)
        await seed_categories(db, teams)
        if promote_email and promote_role:
            await promote_user(db, promote_email, UserRole(promote_role))
        await db.commit()
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
        choices=[r.value for r in UserRole],
        default='admin',
        help="Role to grant (default: admin)."
    )
    args=parser.parse_args()
    asyncio.run(main(args.promote, args.role))
    
    
    