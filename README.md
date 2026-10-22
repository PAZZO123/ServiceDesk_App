# ServiceDesk

An IT help-desk ticketing system: staff open tickets, teams pick them up, and admins follow response times (SLA).

## Features

- Tickets with categories, priorities, tags, comments, @mentions and file attachments
- Teams, ticket routing and clear ownership rules
- Roles and permissions stored as database tables, managed by admins
- JWT login with refresh tokens, email verification, password reset and rate limiting
- Full-text search in PostgreSQL (tsvector) with relevance sorting
- SLA analytics per team (CTEs, window functions, median times) and CSV export
- Notifications and live updates (PostgreSQL NOTIFY)
- Background jobs with Celery and Redis: emails, an SLA-breach check every minute and a nightly file clean-up
- Audit log of important actions

## Built with

Python, FastAPI, async SQLAlchemy, PostgreSQL 16, Alembic, Redis, Celery, pytest; React 19, TypeScript, TanStack Query and Tailwind CSS for the frontend; Docker and GitHub Actions.

## How to run locally

```bash
cp .env.example .env        # then fill in the values
docker compose up -d        # PostgreSQL, Redis and Adminer
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

In a second terminal start the worker: `celery -A app.workers.celery_app worker -B --pool=solo`.

Frontend: `cd frontend && npm install && npm run dev`.

## Tests

```bash
pytest
```

The tests run against a real PostgreSQL database, and GitHub Actions runs them on every push.

## Deployment

The `Dockerfile` builds the frontend and the API into one image. `render.yaml` deploys it on Render; `scripts/start.sh` runs migrations, the seed, Celery and the web server.
