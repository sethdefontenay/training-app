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

### Phase 6 — Post-v1 increments (shipped)
- **Read-only trainer/coach login** — a second account (`role = "trainer"`) with read
  access to every area except settings, and use of the AI assistant limited to read-only
  tools. Enforced server-side (`app/api/deps.py: enforce_role_access`); the frontend hides
  settings and write controls. Fails closed (unknown role → read-only). Spec: `features/trainer_access.feature`.
- **Guided workout runner** — the daily workout runs set-by-set: pick a weight (defaults to
  last session's top set), then a 60 s work timer → 90 s rest → repeat until the prescribed
  sets are done, with "Set complete"/"Skip rest" shortcuts and auto-return on the final set.
  One session per day (idempotent create + resume). Backend contract in `features/workout_logging.feature`.
- **Daily water + electrolyte checks** — two adherence ticks on the daily view
  (`features/daily_task_list.feature`).
- **Mobility scheduling fix** — mobility belongs to training days only (not rest days).

## Phase 2: Post-Launch / Future

- Richer progression analytics and charts.
- Multi-user beyond the single owner + single trainer.
- Anything surfaced during the build that's better deferred than rushed into v1.
