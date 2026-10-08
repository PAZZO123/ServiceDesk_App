# ============================================================
#  ServiceDesk - one image with the API, the React app and Celery.
#  Built by Render from GitHub (see render.yaml). Two stages:
#  Node builds the frontend, then only its output (dist/) is copied
#  into the Python image - Node itself never reaches production.
# ============================================================

# ---- Stage 1: build the React app -------------------------------------
FROM node:22-slim AS frontend
WORKDIR /frontend
# package files first: Docker caches the npm install layer until they change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ---- Stage 2: the Python app ------------------------------------------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libmagic: python-magic reads the real type of every uploaded file.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The lock file = the exact versions CI tests with.
COPY requirements.lock.txt ./
RUN pip install -r requirements.lock.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY --from=frontend /frontend/dist ./frontend/dist

# Never run as root: a bug in the app must not own the whole container.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p uploads \
    && chown appuser:appuser uploads
USER appuser

# Render sets PORT; start.sh migrates, seeds, starts Celery, then uvicorn.
CMD ["sh", "scripts/start.sh"]
