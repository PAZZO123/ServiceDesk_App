#!/bin/sh
# ============================================================
#  Container start (Render). Render's free plan has no "pre-deploy"
#  step, so the one-time jobs run here, on every boot. Both are safe
#  to repeat: alembic skips applied migrations, the seed skips rows
#  that already exist.
# ============================================================
set -e  # stop at the first failing command: never serve a half-migrated DB

echo "== migrations"
alembic upgrade head

echo "== reference data (teams, categories, tags)"
# Optional, set in the Render dashboard:
#   DEMO_PASSWORD  -> also create the demo accounts (grace@example.com ...)
#   ADMIN_EMAIL    -> make that (already registered) account an admin
set --
if [ -n "$DEMO_PASSWORD" ]; then set -- "$@" --demo; fi
if [ -n "$ADMIN_EMAIL" ]; then set -- "$@" --promote "$ADMIN_EMAIL" --role admin; fi
python -m scripts.seed "$@"

echo "== celery worker + beat (background)"
# Free plan: no separate worker service, so it shares this container.
# --pool=solo: one process, small memory (free instances have 512 MB).
# -B: Beat (the SLA sweep every minute) inside the worker.
celery -A app.workers.celery_app worker -B \
    --pool=solo --loglevel=info --schedule=/tmp/celerybeat-schedule &

echo "== web"
# --proxy-headers: Render's proxy sends the visitor's real IP in
# X-Forwarded-For; uvicorn trusts it (only Render can reach this port)
# and puts it in request.client.host - used by the rate limiter and the
# audit log. exec: uvicorn replaces this shell and receives Render's stop signal.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips="*"
