# training-app — Session Handoff

> Written 2026-06-02. Read this first when you `cd ~/training-app` and start a fresh Claude Code session.
> It captures every decision made so far so you (or a new agent) can resume cleanly.

---

## 0. Resume here (do this first)

When you open Claude Code **inside `~/training-app`**, the agent-os slash commands become live (they live in `.claude/commands/agent-os/`). Suggested order:

1. **Prereqs** (one-time, see §7): re-auth `gh` to your **personal** account, install Railway CLI, fix `docker compose` v2.
2. Run **`/plan-product`** → it interviews you and writes `agent-os/product/{mission,roadmap,tech-stack}.md`.
   - Feed it the decisions in §2–§3 below. (We also offered a shortcut where the agent pre-fills these from this handoff — your call.)
3. Enter **plan mode**, then run **`/shape-spec`** for the first feature (**Phase 0 — walking skeleton**, see §6).
4. Build Phase 0 TDD/BDD-first, deploy through the whole pipeline, then proceed phase by phase.

The agent-os installer also suggests `/discover-standards` + `/inject-standards`, but those extract patterns from an *existing* codebase — skip until we have code. For greenfield, start with `/plan-product`.

---

## 1. Why this project exists

We're migrating an Obsidian-based personal training system to a proper hosted web app. The trigger: **Syncthing is a pain to keep alive** for syncing the Obsidian vault between desktop (`WELLS2023007`) and Android phone (`CPH2637`). A hosted API + DB **eliminates the sync problem entirely** — both devices hit the same backend. Mobile-first web also matches how sets get logged (on a phone, at the gym).

Tradeoff accepted: we give up Obsidian's free-form notes/wiki-linking and take on a little infra to maintain. Fair trade — the data is already tabular.

The existing Obsidian system still lives at **`/mnt/c/automation/Training`** and is the migration source (see §5).

---

## 2. Decisions locked in

| Decision | Choice |
|---|---|
| **Backend** | Python · **FastAPI** · **SQLAlchemy 2.0** (`Mapped`/`mapped_column`) · Pydantic schemas · Alembic · JWT auth |
| **Frontend** | **React + Vite + TypeScript + Tailwind**, shipped as an installable **PWA** (mobile-first) |
| **Database** | **PostgreSQL** (prod + local via Docker); SQLite acceptable only if needed for fast unit tests |
| **Hosting** | **Railway** (all-in-one: FastAPI service + Postgres plugin + static frontend). ~$5/mo. |
| **Repo** | **`github.com/sethdefontenay/training-app`** — monorepo, **assumed private** (holds health/body data; confirm) |
| **CI/CD** | **GitHub Actions** for lint + tests as a gate; Railway native GitHub auto-deploy on `main` |
| **Dev method** | **TDD** (red-green-refactor) + **BDD-first** — a fully-specced Gherkin suite up front using **`pytest-bdd`** (one runner for BDD scenarios + unit tests) |
| **Local-first** | Everything runs locally via **`docker compose`** (Postgres + API + web) with prod parity |
| **Planning** | **agent-os v3.0** (already installed, `python` profile) drives planning via `/plan-product` + `/shape-spec` |

### Assumed defaults (not explicitly confirmed — verify during `/plan-product`)
- **Auth scope:** single-user (just Seth). Simplest secure login. (Alt: add read-only coach "Holly" view later.)
- **Data migration:** migrate **all** Obsidian history into Postgres via a Python importer.
- **Health sync:** **keep** the Fitbit/Google steps + sleep sync (see §5).
- **Repo visibility:** private.

---

## 3. Stack reconciliation — 4 deltas vs the agent-os `python` profile

The installed `python` profile standards (`agent-os/standards/`) already match us on FastAPI/uv/Postgres/SQLAlchemy/Alembic/Pydantic/JWT/pytest/Ruff/mypy/Docker Compose/GH Actions. Differences to honor:

1. **Python 3.11+** (profile) vs **3.10** (machine) → pin 3.11/3.12 via **uv** in-project; system Python is irrelevant once uv manages it.
2. **SQLAlchemy 2.0** (profile's `models.md`) — **we follow the standard**, not SQLModel.
3. **BDD** — profile's `testing/test-writing.md` covers pytest but not BDD. **We add `pytest-bdd`** and should extend the project testing standard to document the BDD-first workflow.
4. **Hosting** — profile lists Azure/AKS (Seth's work context); **we use Railway**. The project `tech-stack.md` diverges here intentionally.

---

## 4. Target architecture

```
training-app/  (monorepo)
├── backend/    FastAPI · SQLAlchemy 2.0 · Alembic · pytest + pytest-bdd
├── frontend/   React + Vite + TS + Tailwind (PWA)
├── migrate/    Obsidian → Postgres importer (re-runnable)
├── sync/       Fitbit/Google steps+sleep scheduled job
├── docker-compose.yml      local: postgres + api + web
├── .github/workflows/ci.yml
└── agent-os/   (installed) standards + product docs
```

### Data model (derived from the Obsidian system — see §5 for field sources)
| Table | Key fields |
|---|---|
| `exercise` | slug, name, kind (resistance/mobility), is_bodyweight, cues/notes, muscle_group |
| `training_day` | label (Day 1/2/3), program_week range |
| `prescription` | training_day → exercise, target_sets, target_reps, target_weight, order |
| `session` | date, weekday, training_day, bodyweight, energy, shoulder_check, how_it_felt, cardio |
| `set_entry` | session, exercise, set_index, reps, weight, **rpe** |
| `mobility_log` | date, exercise, done |
| `measurement` | date, waist_cm, tummy_cm, bum_cm, right_thigh_cm, left_thigh_cm, weight_kg |
| `steps_day` | date, steps, target_steps, target_met |
| `sleep_night` | date, asleep_min, efficiency, bedtime, wake_time |

### ⭐ First-class feature: progressive-overload "last week" column
This is the feature that kicked off the pivot. On the session-logging screen, each exercise shows the **most recent prior session's top set** (`weight×reps`) next to the input. "Most recent prior date" resolves to last week on a weekly split, and stays correct across skipped/shifted sessions.
- Server endpoint: `GET /exercises/{slug}/previous?before=<date>` → top set of the latest earlier date.
- Logic already validated against real Obsidian data (leg-press 40×15, lat-pulldown 47×15, etc.).
- Bodyweight moves → `BW×reps`; no history → `—`.
- NOTE: this was also prototyped in Obsidian (a `Last wk` column added to `Templates/Session.md` + `Templates/AddSetButton.md`). Carry the behavior forward; the Obsidian version can be retired after migration.

### API surface (FastAPI, `/api/v1`, auto-docs at `/docs`)
- `POST /auth/login` (single-user JWT)
- `GET /today` — scheduled session + prescriptions + last-week numbers
- Sessions: create / get / list / patch-notes
- Sets: `POST /sessions/{id}/sets`, edit/delete, `GET /exercises/{slug}/previous`
- Mobility, Measurements, Steps, Sleep: read + write
- `GET /reviews/{iso-week}` — adherence + progression aggregates

### Frontend screens (mobile-first)
1. **Today** — today's session card → tap to log
2. **Session logging** — exercise rows, **Last wk** column, +set, RPE (the core screen)
3. **Exercise** — progression chart over time
4. **Measurements** — entry + trend
5. **Dashboard** — steps/sleep/adherence
6. **Weekly review**

---

## 5. Obsidian migration source (`/mnt/c/automation/Training`)

The importer parses markdown + YAML frontmatter. Folder → table mapping and field shapes observed:

| Obsidian | Notes |
|---|---|
| `Sets/<date>-<slug>-<n>.md` | frontmatter: `type: set`, `date`, `weekday`, `exercise` (slug), `session`, `set_index`, `reps` (string), `weight` (string, may be `""` for bodyweight) → **`set_entry`** |
| `Mobility-Done/<date>-<slug>.md` | date + exercise slug → **`mobility_log`** |
| `Measurements/<date>.md` | `waist_cm`, `tummy_cm`, `bum_cm`, `right_thigh_cm`, `left_thigh_cm`, `weight_kg` → **`measurement`** |
| `Steps/` | `date`, `steps`, `target_steps`, `target_met` → **`steps_day`** |
| `Sleep/` | `date`, `asleep_min`, `efficiency`, `bedtime`, `wake_time` → **`sleep_night`** |
| `Plan/Training-Day-1/2/3.md` | prescription tables (exercise, sets×reps) → **`training_day`** + **`prescription`** |
| `Exercises/<slug>.md` | technique/cues per exercise → **`exercise`** |
| `Schedule/Weekly-Schedule.md` | frontmatter maps weekday → `[[Training-Day-N]]` |
| `Logs/Session <date> <Weekday>.md` | session notes (bodyweight, energy, shoulder, how-it-felt, cardio) → **`session`** |

**Health sync source:** `/mnt/c/Users/Seth/personal/google-health-fetch/` — `catch_up.py` (pulls N days of steps+sleep), `auth_bootstrap.py` (OAuth). These wrote `Steps/` and `Sleep/` notes in Obsidian; port them to write to Postgres instead (scheduled via GH Actions cron or a backend task).

**Nutrition (deferred):** Obsidian also has `Plan/Meal-Plan-1.md`, meals, and a shopping-list generator. Left **out of MVP** to stay focused — pull into a later phase if wanted.

---

## 6. Phased delivery (each phase deploys and is usable)

- **Phase 0 — Walking skeleton:** monorepo scaffold, create GitHub repo, Railway project + Postgres, `docker compose` local stack, CI green, deploy a `/health` endpoint + "Hello" PWA **through the whole pipeline**. Proves the stack end-to-end before features. **← start here.**
- **Phase 1 — Data + auth + import:** models, Alembic migrations, single-user login, Obsidian importer (full history into Postgres).
- **Phase 2 — Workout logging:** sessions, set logging, the **last-week / progressive-overload** feature. The heart of the app.
- **Phase 3 — Measurements + dashboard + weekly review.**
- **Phase 4 — Health sync:** port `google-health-fetch` into a scheduled job.
- **Phase 5 (optional):** nutrition/meal-plan/shopping.

BDD-first means: before implementing each phase, write its Gherkin `.feature` scenarios (the behavior spec), then drive implementation TDD-style to make them green.

---

## 7. Environment state & prereqs

**Already done this session:**
- `~/training-app` created, `git init` on `main`.
- agent-os v3.0 installed into the project (`python` profile): `agent-os/standards/` (6 files + `index.yml`) and `.claude/commands/agent-os/` (5 commands).
- Nothing else — no code, no commit yet.

**Toolchain present:** Python 3.10.12, **uv 0.9.0**, Node 23.11, npm 10.9.2, Docker 29.1.3, git 2.34. agent-os base at `~/agent-os` (v3.0).

**Prereqs to fix before/while building:**
- ⚠️ **`gh` CLI auth expired** → run `gh auth login` and select your **personal** account (the stored token looked work-oriented). Needed to create `sethdefontenay/training-app`.
- ⚠️ **Railway CLI not installed** → install when wiring deploys (or rely on Railway's native GitHub auto-deploy).
- ⚠️ **`docker compose` v2 plugin not wired up** (`docker compose version` failed) → fix for local Postgres parity. Either install the compose plugin or use a `docker run postgres` fallback.
- **Python 3.11+** → install/pin via `uv python install 3.12` and set in `pyproject.toml`.

**Not yet committed:** consider an initial commit of the agent-os install + this handoff once `gh`/git identity is sorted (no commit was made automatically).

---

## 8. Open questions to confirm during `/plan-product`
- Repo **public or private**? (assumed private)
- Auth: **single-user only**, or build for **Seth + coach Holly** now? (assumed single-user)
- Migrate **all** history or **recent-only** first? (assumed all)
- Keep **health sync** in MVP or defer? (assumed keep — but it's Phase 4, so effectively deferred to after core logging)
- Pull **nutrition/shopping** into scope, or leave deferred? (assumed deferred)
