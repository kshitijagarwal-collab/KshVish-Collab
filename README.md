# KYC Onboarding Platform

Global KYC Onboarding Platform for Fund Management Companies — Individuals & Corporates across all jurisdictions.

## Quick start (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at `http://localhost:8000`. OpenAPI docs at `/docs`.

## Quick start (local Python)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head      # creates kyc.db (sqlite by default)
uvicorn main:app --reload
```

## Environment

Copy `.env.example` and adjust. Key vars:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./kyc.db` | SQLAlchemy URL. Use `postgresql+psycopg2://...` in prod. |
| `KYC_AUTH_SECRET` | `dev-secret-change-me` | **Must override in prod.** Signs JWT access tokens. |
| `KYC_AUTH_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `KYC_AUTH_ACCESS_TOKEN_TTL_MINUTES` | `60` | Token lifetime. |
| `WORKERS` | `2` | Uvicorn worker count (container entrypoint only). |

## Tests

```bash
pytest tests/                       # all
ruff check src/ tests/              # lint
mypy src/                           # types
```

## Routes

All API routes are mounted under `/api`. The container also exposes `/health` for orchestrator probes.
