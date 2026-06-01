# training-app

A mobile-first web app for personal strength training — migrated from an Obsidian-based system to a hosted API + database so logging works the same on phone and desktop with no sync hassle.

## Status

Greenfield. Planning is complete (see [`HANDOFF.md`](./HANDOFF.md)); this is the first commit verifying the repo pipeline. Build begins with **Phase 0 — walking skeleton**.

## Stack

- **Backend:** Python · FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic · JWT
- **Frontend:** React + Vite + TypeScript + Tailwind, shipped as an installable PWA
- **Database:** PostgreSQL
- **Hosting:** Railway · **CI:** GitHub Actions
- **Method:** TDD + BDD-first (`pytest-bdd`), local-first via `docker compose`

## Headline feature

A progressive-overload **"last week"** column on the logging screen: each exercise shows the most recent prior session's top set (`weight×reps`) right next to the input.

---

See [`HANDOFF.md`](./HANDOFF.md) for the full plan, data model, and phased delivery.
