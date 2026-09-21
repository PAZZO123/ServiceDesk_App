"""Throwaway connection test. Delete it after Day 1 if you like."""
import asyncio
import asyncpg
from app.core.config import settings


async def main() -> None:
    # asyncpg does not understand the "+asyncpg" part - that is
    # SQLAlchemy's way of naming a driver. Strip it for a raw
    # asyncpg connection.
    url = settings.DATABASE_URL.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    version = await conn.fetchval("SELECT version()")
    print("Connected!")
    print(version)
    await conn.close()


asyncio.run(main())