# Product Roadmap

## Scope note

The v1 MVP is intentionally broad: it commits **three pillars** — workout logging, automated health sync, and nutrition — rather than shipping logging alone. This is a deliberate choice (driven by "minimal manual admin" and not wanting a half-system), accepting that a usable *complete* v1 arrives later than a logging-only MVP would.

To offset that, the build stays **incrementally deployable**: a walking skeleton goes through the full deploy pipeline first, then each pillar lands as a working, deployed increment. So there is usable software early even though "v1 complete" is the larger target.

## Phase 1: MVP (v1)

Delivered as sequenced, individually-deployable increments. All of the following are in v1.

### Phase 0 — Walking skeleton
Monorepo scaffold, GitHub repo (done), Railway project + Postgres, local `docker compose` stack, CI green, a `/health` endpoint + "Hello" PWA shipped **through the whole pipeline**. Proves the stack end-to-end before features. **← build starts here.**

### Phase 1 — Data model + auth + import
- **Finalize the data model first** (gate on the importer — per the migration decision, the structure is settled before we move weeks of existing logs).
- SQLAlchemy 2.0 models + Alembic migrations.
- Single-user JWT login.
- Obsidian importer: migrate the **full** existing history into Postgres (re-runnable), so no logged data is lost.

### Phase 2 — Workout logging (the core)
- Sessions + set logging (reps, weight, RPE).
- The **progressive-overload "last week" column** — most recent prior top set shown next to each input.

### Phase 3 — Health sync (automated, minimal admin)
- Port the existing `google-health-fetch` job to write steps + sleep into Postgres on a schedule (no manual entry).
- This is a v1 requirement, not deferred.

### Phase 4 — Nutrition
- Meal plan, meals, and shopping-list generation (migrated/carried forward from the Obsidian nutrition system).
- In v1 MVP.

### Phase 5 — Measurements, dashboard, weekly review
- Body measurements entry + trends.
- Dashboard (steps / sleep / adherence).
- Weekly review (adherence + progression aggregates).

## Phase 2: Post-Launch / Future

- Read-only **coach view** (e.g. for the PT) — multi-user / role-based access.
- Richer progression analytics and charts.
- Anything surfaced during the build that's better deferred than rushed into v1.
