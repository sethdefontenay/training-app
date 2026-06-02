# Tech Stack

This project follows the installed `python` profile standard (`agent-os/standards/global/tech-stack.md`) for the backend, with four deliberate divergences (see "Divergences" below) and an added frontend stack the standard does not cover.

## Frontend

- **Framework:** React + Vite + TypeScript
- **Styling:** Tailwind CSS
- **Delivery:** installable **PWA**, mobile-first (logging happens on a phone at the gym)

## Backend

- **Language/Runtime:** Python 3.11+ (pinned to 3.12 in-project via **uv**; system Python is irrelevant once uv manages it)
- **Web Framework:** FastAPI (async), served by Uvicorn
- **API:** RESTful, `/api/v1`, OpenAPI/Swagger auto-docs at `/docs`
- **Serialization:** Pydantic models
- **Authentication:** JWT (single-user)
- **Package Manager:** uv (`pyproject.toml` + `uv.lock`)
- **Scheduled jobs:** for health sync (steps/sleep) — APScheduler or a GitHub Actions cron, decided in Phase 3

## Database

- **Database:** PostgreSQL (production and local, for prod parity). SQLite acceptable only if needed for fast unit tests.
- **ORM:** SQLAlchemy 2.0 (`Mapped` / `mapped_column` style)
- **Migrations:** Alembic

## Testing & Quality

- **Test framework:** pytest, with **pytest-bdd** for a BDD-first Gherkin suite (one runner covers BDD scenarios + unit tests)
- **Method:** TDD (red-green-refactor) driving each phase's `.feature` scenarios to green
- **Coverage:** pytest-cov
- **Linting/Formatting:** Ruff (lint + format)
- **Type checking:** mypy (strict)
- **Pre-commit:** Ruff checks via pre-commit hooks

## Infrastructure & Deployment

- **Containerization:** Docker (multi-stage builds)
- **Local stack:** `docker compose` — Postgres + API + web, with prod parity
- **Hosting:** **Railway** (FastAPI service + Postgres plugin + static frontend), ~$5/mo
- **CI:** GitHub Actions (lint + tests as a merge gate)
- **CD:** Railway native GitHub auto-deploy on `main`
- **Repo:** `github.com/sethdefontenay/training-app` — private monorepo (holds health/body data)

## Divergences from the `python` profile standard

1. **Python 3.11+ pinned via uv** — the standard allows 3.11+; we pin 3.12 in-project rather than relying on system Python (3.10).
2. **SQLAlchemy 2.0** — we follow the standard's `models.md` explicitly (not SQLModel).
3. **BDD added** — the standard's `testing/test-writing.md` covers pytest but not BDD; we add `pytest-bdd` and extend the testing standard to document the BDD-first workflow.
4. **Hosting = Railway** — the standard lists Azure/AKS (work context); this personal project intentionally uses Railway instead.
