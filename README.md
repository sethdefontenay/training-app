# training-app

A mobile-first, single-user **personal health & training hub** — a low-overhead place to
aggregate training, nutrition, recovery and **Type 1 diabetes** data, whose headline output
is an easy, accurate **weekly check-in with a personal trainer**. Built to replace an
Obsidian-based system with a hosted API + Postgres so logging works the same on phone and
desktop, installable as a PWA.

## What it does

Everything is organised around a **Home** hub:

- **Today** — the daily task list: the day's prescribed workout, meals (check off as eaten,
  with carbs), wellbeing scores (energy / motivation / stress / hunger), and steps. Pulls
  steps & sleep from Google Health in the background on open.
- **Log workout** — log sets per exercise with a progressive-overload **"last week"** column
  (the most recent prior session's top set shown next to the input). Reps/weight stick
  between sets.
- **Exercise progress** — weight-over-time per exercise, grouped by training day.
- **Workout history** — past sessions and their sets.
- **Measurements** — body measurements with history and per-day detail.
- **Weekly check-in** — assembles the last 7 days (measurements, sleep avg, steps avg,
  posed photos, reflections) into the package for the PT.
- **Weekly shopping list** — generated from the current plan.
- **Current plan** — aggregated view of the active plan (training days, meals, macro/step
  targets, time since start). Plans are ingested from the PT's email (Gmail) via an AI parser.
- **Diabetes record** — glucose & insulin pulled from **Tidepool** (Dexcom CGM + Tandem pump);
  a BG graph over 1 day / 1 week / 1 month with an **insulin-on-board** overlay and meal /
  workout markers, plus average & time-in-range summaries.
- **Sleep** — per-night **stage timeline** (hypnogram: when each stage occurred and for how
  long) and weekly stage/efficiency trends, from Google Health.
- **Ask the hub** — an in-app **Claude (Opus) assistant** (bottom-right drawer) that can read
  *and* update your data via tools, search the web (e.g. exercise-technique videos), and
  renders Markdown tables/lists with inline YouTube previews.
- **Settings** — connect Google Health (OAuth) and Tidepool.

All "today/this week" logic is anchored to a configurable local timezone, not the server's UTC.

## Integrations

- **Google Health** (OAuth offline) — steps and sleep, including sleep-stage segments.
- **Tidepool** — Dexcom glucose + Tandem pump (bolus/basal), pulled on demand / at check-in.
- **Gmail** — ingest the PT's plan email into a structured plan.
- **Anthropic API** — powers the assistant (default model `claude-opus-4-8`).
- **MCP server** — the assistant's tool registry is also exposed over an authenticated MCP
  server at `/mcp` (Streamable HTTP) for external clients (Claude Desktop / Code / claude.ai),
  enabled by setting `MCP_TOKEN`.

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2.0 (async, asyncpg) · Alembic · Pydantic v2
  · JWT + bcrypt · `anthropic` + `mcp` SDKs · httpx
- **Frontend:** React 19 · Vite · TypeScript · Tailwind v4 · vite-plugin-pwa · Recharts ·
  react-markdown — shipped as an installable, self-updating PWA
- **Database:** PostgreSQL
- **Hosting:** Railway (single service) · **CI:** GitHub Actions
- **Method:** BDD-first (`features/*.feature`) + tests; `ruff` + `mypy`; local-first via Docker

## Architecture

A single Railway service: a multi-stage Docker build compiles the frontend and serves the
static PWA from FastAPI, which also exposes the API under `/api/v1`. Alembic migrations run
on boot. The database is **never exposed publicly** — historical data is loaded via an
authenticated **API vault-import** endpoint, and the MCP server is an authed capability API
over the same services (not raw DB access).

## Local development

Uses [`invoke`](https://www.pyinvoke.org/) tasks (`tasks.py`) and `uv` for the backend.

```bash
invoke install            # backend (uv) + frontend (npm) deps
invoke db-up              # local Postgres via docker compose
invoke migrate            # alembic upgrade head
invoke seed --email you@example.com --password secret
invoke dev                # run backend (:8000) + frontend (:5173) together
```

Other useful tasks: `invoke ci` (lint + types + tests), `invoke lint`, `invoke fmt`,
`invoke test`, `invoke bdd` (run the executable Gherkin suite), `invoke makemigration`,
`invoke import-vault-remote` (push an Obsidian vault to a deployed instance over the API).

## Configuration

Set via environment / `.env` (see `backend/app/config.py`):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres URL (`postgres://` / `postgresql://` auto-rewritten to asyncpg) |
| `JWT_SECRET` | Auth signing secret |
| `TIMEZONE` | User's local timezone (default `Pacific/Auckland`) — drives all "today" logic |
| `FRONTEND_URL` | Base URL for OAuth redirects back to the app |
| `GOOGLE_REDIRECT_URI` | Google Health OAuth callback |
| `SEED_EMAIL` / `SEED_PASSWORD` | Create/refresh the single login on boot |
| `ANTHROPIC_API_KEY` | Enables the assistant (pay-per-token; separate from any subscription) |
| `ASSISTANT_MODEL` | Assistant model (default `claude-opus-4-8`) |
| `MCP_TOKEN` | Enables + protects the `/mcp` server (bearer token) |

Google Health and Tidepool credentials are entered in-app (Settings) and stored in the DB.

## Tests & specs

Behaviour is specified BDD-first in `features/*.feature` (18 feature files), and **every
feature is now executable** via `pytest-bdd`: each `.feature` has step definitions in
`backend/tests/bdd/` that drive the real API. Run them with `invoke bdd`. Scenarios that
require a live external service (Google Health / Tidepool / Gmail) or a live LLM (the
assistant, plan extraction) are wired but `pytest.skip`-ped with a reason; pure client-side
behaviour (home hub, navigation) is wired as documented no-ops. CI runs backend
lint/format/type-check/tests (including the BDD suite) and the frontend lint/build on every push.
