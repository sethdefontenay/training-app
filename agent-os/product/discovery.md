# Discovery — Vision & Behaviors

> Capture of the design interview (2026-06-02). Source of truth for the BDD scenario suite. Supersedes assumptions in `HANDOFF.md` where they conflict.

## The why (in one paragraph)

A **low-overhead aggregation hub** for Seth's whole-system health — training, nutrition, recovery, and **Type 1 diabetes** management — built around the honest constraint that Seth won't reliably do manual admin. Its killer output is an **easy, accurate weekly check-in to his PT**. The progressive-overload "last week" column is the sharp edge; the point is the whole loop. Insights/correlation are explicitly *deferred* — but the data is modelled well now so they can be added later.

## Cross-cutting principles (these constrain every feature)

1. **Minimal manual admin is the prime directive.** Automate ingestion; keep everything editable. Everything else bends to this.
2. **The daily task list is the anchor screen.** Open it each day → see activities + meals (with carbs) + log the daily /10s. It is the daily habit; the carb number for pump dosing is itself the reason to open it.
3. **Carb accuracy is safety-critical.** Carbs drive insulin dosing. Show the carb number's source, never present a silent guess as fact.
4. **Human-in-the-loop for all AI ingestion.** The agent *proposes* structured data; Seth reviews/edits; *then* it commits. No silent writes of medical-relevant data.
5. **Medical-grade data → privacy/security first.** Private repo; careful auth; deliberate about storage/access.
6. **Model data backwards from the weekly check-in.** Whatever the check-in needs, captured accurately, is the spine.
7. **Structure for future insights.** No insight engine in v1, but the schema must not preclude one.
8. **Single user (Seth).** Coach login / multi-user is deferred.

## The weekly PT check-in (the killer output)

Fields the PT asks for each week:
- All body measurements (waist, tummy, bum, R/L thigh, weight)
- Energy /10, Motivation /10, Stress /10, Hunger /10 — **captured daily**, summarised weekly
- Posed photos → **requires image upload + storage**
- "Anything I worked on specifically last week" (reflection)
- "Any struggles I had last week" (reflection)

Implications: a quick **daily wellbeing log**; **photo storage**; report assembly that is easy *and* accurate; reflections may be assisted by surfacing the week's logged adherence.

## The AI plan-ingestion agent (key architecture)

The PT sends a fresh plan ~every 6 weeks. Instead of hand-entering it, an in-app **Claude agent** parses it into structured data.

- **Input (real, from the vault):**
  - Email **prose** — goals, philosophy, non-negotiables, shoulder protocol, daily targets (7,000 steps, 2–3L water, 1 electrolyte/day, macros 2,400 kcal / 170P / 212C / 83F).
  - **`.docx` attachments** — `Day-1/2/3.docx` (training day exercise tables), `Mobility.docx`. Agent must parse Word docs, not just email text.
  - Gmail metadata is captured (from, date, thread id). Current manual process: email + docs saved into `Raw/`.
- **Output (target schema):** training days + exercises + prescriptions (sets×reps, prescribed weight), mobility, meals + macros, shopping list, daily targets, and retained guidance/context.
- **Constraints:** review-gated (principle 4); carbs verified; a new plan starts a new **~6-week plan block** (versioned — vault uses `current: true` + `phase`); history retained.

## Behavioral domain map (BDD feature areas)

| # | Domain | v1? | Confidence |
|---|---|---|---|
| 1 | Plan ingestion (Claude agent: email + .docx → structured plan, review-gated) | ✅ core | Medium — input understood, delivery mechanism open |
| 2 | Daily task list (activities + meals w/ carbs + daily /10 log) | ✅ core | High |
| 3 | Workout logging (sessions, sets: reps/weight/RPE, edit/delete, bodyweight) | ✅ core | High |
| 4 | Progressive-overload "last week" column | ✅ core | High |
| 5 | Weekly PT check-in report (assemble + accurate + easy) | ✅ core | High |
| 6 | Measurements (entry + trend) | ✅ core | High |
| 7 | Daily wellbeing log (energy/motivation/stress/hunger /10) | ✅ core | High |
| 8 | Posed photos (upload, store, week-to-week) | ✅ core | Medium |
| 9 | Mobility tracking | ✅ core | Medium |
| 10 | Auth (single-user) | ✅ core | Low — mechanism TBD |
| 11 | Data migration/import (full Obsidian history) | ✅ core | High — source mapped |
| 12 | Steps/sleep sync (Fitbit/Google — has API, `catch_up.py` exists) | ✅ first cut | Medium |
| 13 | CGM data (Dexcom/Libre) | ⏳ later | Low — feasibility + need TBD |
| 14 | Insulin/pump data (Omnipod/Tandem/Medtronic) | ⏳ later | Low — likely no API; core doesn't need it |
| 15 | Insight/correlation engine | ❌ deferred | n/a — structure data to allow it |

## Key data facts (from the real Obsidian vault)

- **Meals:** meal-level macros in frontmatter (`calories/protein/carbs/fat` as integers). **Carbs are per-meal, not per-ingredient** — that meal-level carb is the insulin number. Ingredients are measured (g/ml), no per-ingredient macros stored.
- **Plan = ~6-week block**, versioned (`current: true`, `phase`), source-stamped (`"PT, 2026-05-21"`).
- **Training days:** exercise tables; `sets×reps` is a string (`"4 × 15"`, `"3 × 10 per leg"`); prescribed weight is a string in kg; bodyweight = empty weight.
- **Sets (logged):** `reps`/`weight` are strings (empty = bodyweight), 1-indexed `set_index`.
- **Measurements:** waist/tummy/bum/right_thigh/left_thigh/weight_kg (string numbers).
- **Steps/sleep:** already synced from `google-health` (`catch_up.py`); rich sleep stages, efficiency; steps target 7,000.
- **Daily note** already aggregates targets + workout + mobility + meal checklist (with macros) + notes + a "For the PT (weekly check-in)" accumulator.
- **Weekly review** keyed by ISO week (`2026-W23`).

## Explicitly out of scope (v1)

- **MyFitnessPal integration** — the PT's chosen app where Seth reports intake *to them*; no API; managed outside this app.
- **Insight/correlation engine** — deferred (structure data to allow it later).
- **Coach login / multi-user** — deferred.
- **Talking to the insulin pump or CGM** for the core loop — the app *shows* the carb number; Seth enters it into the pump manually. The daily spine needs no device integration.

## Decisions locked (from the scenario interview)

- **v1 scope:** everything — including CGM/pump. Device-integration scenarios spec the happy path *and* an explicit manual fallback so the suite is buildable even where a vendor has no API.
- **Last-week column** shows the **heaviest weight only** (not reps) from the most recent prior session (e.g. "40 kg"); ties are irrelevant to the display; bodyweight exercises show "BW"; no history shows "—". (The progression view still plots heaviest weight over time, and reps over time for bodyweight.)
- **RPE:** out of v1 (not captured).
- **Gherkin style:** declarative / behaviour-focused.
- **Meal check-off** = adherence only ("ate as planned"); no macros logged here (intake goes to the PT via MyFitnessPal). Off-plan extras captured as day notes.
- **Plan delivery:** auto-pull from Gmail (broad inbox access acknowledged), with manual upload as fallback when Gmail is unavailable.
- **Weekly check-in window:** rolling **last 7 days** from when the button is pressed (not a fixed ISO week). Shows the daily /10 values across those 7 days **plus a 7-day average**; missing days shown as missing, never zero.
- **Posed photos:** attach-only — saved with the check-in, viewable by date; no comparison/gallery view in v1.
- **Steps/sleep sync:** scheduled daily **and** on app open; idempotent; manual entry/override fallback. Source = existing `google-health` (Fitbit Sense 2).
- **Device kit:** CGM = **Dexcom (G6/G7/One)** (real API); pump = **Tandem t:slim X2** (no sanctioned API).
- **Diabetes data architecture:** single integration with **Tidepool**. Tidepool pulls Dexcom (cloud) and receives Tandem via the Tidepool Uploader (desktop, manual, weekly before check-in). The app pulls the **last 7 days from Tidepool at check-in time, and the latest on opening the diabetes record**, into **Seth's own record/dashboard — NOT part of the package sent to the PT** (her form is measurements / four /10s / photos / reflections only). Missing pump upload is shown as missing, never faked. ⚠️ Tidepool API access/auth to be verified against live docs before building.
- **Auth:** single-user **email + password**, long-lived JWT session on the trusted phone.
- **Home / navigation:** **Home is a separate hub** (dashboard/launcher), not the daily list — because non-daily areas (weekly shopping list, PT check-in) need a place to live. Login → Home. Home launches Today (daily anchor, most prominent) + the non-daily areas. Every screen has a **home** control (→ Home hub) and a **back** control (one step). The **weekly shopping list** is a first-class non-daily area (generated from the plan's meals, items checkable).

## Decisions added during the build (kept in sync with `features/`)

- **Daily mobility section** shows on **workout days**, derived from the mobility moves actually logged (MobilityDone), with today's done-state; items tick/un-tick. (Upgrade to a prescribed round if a Mobility source is parsed.)
- **Meals and mobility can be un-checked** (not just checked); shopping toggles too.
- **Current plan detail** is an aggregated read-only view: schedule, training days + exercises, meals (expandable to ingredient quantities/units), targets, days-since-start.
- **Google Health = OAuth offline access** (client id/secret + refresh token), connected once via Settings ("Connect with Google" → consent → refresh token captured server-side) or by pasting a refresh token. NOT an API key. Live client ported from `google-health-fetch` (v4 steps rollup + sleep dataPoints).

## BDD suite status (in `features/`)

Declarative style (navigation is necessarily screen-named): `home`, `navigation`, `daily_task_list`, `workout_logging`, `exercise_progression`, `plan_ingestion`, `plan_detail`, `shopping_list`, `weekly_checkin`, `diabetes_data`, `health_sync_steps_sleep`, `google_health_connect`, `measurements`, `mobility`, `auth`, `obsidian_import` — 16 files. Kept in sync with features as they're built/changed.

## Open questions

All interview questions resolved. Remaining items are **build-time verifications**, not design unknowns:

- ⚠️ **Tidepool API** access/auth model (developer registration, OAuth scopes, regional availability) — verify against live docs before building the integration.
- ⚠️ **Gmail auto-pull** — OAuth scopes + detection heuristics (sender = `my PT’s address`) to confirm at build time.
- **Meal source: RESOLVED** — the full plan (training, mobility, *and* nutrition/macros) is contained in the PT's email + its attachments. The `Raw/2026-05-21` note is a hand-made summary that didn't preserve the meal content; the agent parses the real email + `.docx`.
