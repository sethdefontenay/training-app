"""Execute features/obsidian_import.feature via pytest-bdd.

Builds a tiny temp Obsidian vault of valid markdown notes matching what app/importer.py
parses, runs import_vault via the seed runner, and asserts on the returned ImportSummary
plus rows landed (checked through the API and follow-up queries).
"""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import select

from app.importer import import_vault
from app.models import Session as WorkoutSession
from tests.bdd.seed import _owner_id

scenarios("obsidian_import.feature")


async def _do_import(s, root):
    """Run the importer as the seeded owner (resolved from the DB)."""
    return await import_vault(s, root, await _owner_id(s))


# --- vault construction ----------------------------------------------------

# Dates used across the vault. These must be preserved end-to-end.
SET_DATE = "2026-05-25"
SESSION_DATE = "2026-05-24"
MEAS_DATE = "2026-05-23"
STEPS_DATE = "2026-05-22"
SLEEP_DATE = "2026-05-21"
MOB_DATE = "2026-05-20"
# A second, earlier set of the same exercise so last-week has a prior session to draw on.
PRIOR_SET_DATE = "2026-05-18"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_vault(root: Path, *, malformed: bool = False) -> None:
    """Lay down a minimal but valid vault covering every importer sub-step."""
    # Plan: current meal plan + overview + one training day + weekly schedule.
    _write(
        root / "Plan" / "Meal-Plan.md",
        "---\ncurrent: true\nsource: PT, 2026-05-21\nphase: 1\n---\n# Meal Plan\n",
    )
    _write(
        root / "Plan" / "Overview.md",
        "# Overview\nTarget 7000 steps per day. Water 2-3 l.\n",
    )
    _write(
        root / "Plan" / "Training-Day-1.md",
        "---\nweekday: monday\n---\n"
        "# Training Day 1\n\n"
        "| Exercise | Sets × Reps | Weight |\n"
        "| --- | --- | --- |\n"
        "| [[leg-press-machine|Leg Press Machine]] | 4 × 15 | 50kg |\n"
        "| [[crunches|Crunches]] | 4 × 15 |  |\n",
    )
    _write(
        root / "Schedule" / "Weekly-Schedule.md",
        "---\nmonday:\n  - '[[Training-Day-1|Training Day 1]]'\n  - '[[mobility|Mobility]]'\n---\n",
    )

    # Exercises catalog note.
    _write(
        root / "Exercises" / "leg-press-machine.md",
        "---\nname: Leg Press Machine\nis_bodyweight: false\n---\n# Leg Press Machine\n",
    )

    # Measurement.
    _write(
        root / "Measurements" / f"{MEAS_DATE}.md",
        f"---\ndate: {MEAS_DATE}\nweight_kg: 82.5\nwaist_cm: 96\n---\n",
    )

    # Steps day.
    _write(
        root / "Steps" / f"{STEPS_DATE}.md",
        f"---\ndate: {STEPS_DATE}\nsteps: 8123\ntarget_steps: 7000\ntarget_met: true\n---\n",
    )

    # Sleep night.
    _write(
        root / "Sleep" / f"{SLEEP_DATE}.md",
        f"---\ndate: {SLEEP_DATE}\nbedtime: '22:30'\nwake_time: '07:00'\nasleep_min: 420\n---\n",
    )

    # Session log (no sets of its own).
    _write(root / "Logs" / f"{SESSION_DATE}.md", f"---\ndate: {SESSION_DATE}\n---\n# Session\n")

    # Sets: a bodyweight set (empty weight) on SET_DATE, plus a prior weighted set so
    # the last-week column has a strictly-earlier session to read from.
    _write(
        root / "Sets" / f"leg-press-{PRIOR_SET_DATE}.md",
        f"---\ndate: {PRIOR_SET_DATE}\nexercise: leg-press-machine\nset_index: 1\n"
        "reps: '15'\nweight: '50'\n---\n",
    )
    _write(
        root / "Sets" / f"crunches-{SET_DATE}.md",
        f"---\ndate: {SET_DATE}\nexercise: crunches\nset_index: 1\nreps: '15'\nweight: ''\n---\n",
    )

    # Mobility tick.
    _write(
        root / "Mobility-Done" / f"{MOB_DATE}.md",
        f"---\ndate: {MOB_DATE}\nexercise: cat-cow\n---\n",
    )

    if malformed:
        # A measurement note with no frontmatter block at all -> ValueError, reported.
        _write(root / "Measurements" / "broken.md", "no frontmatter here at all\n")


def _make_vault(context: dict, *, malformed: bool = False) -> Path:
    tmp = tempfile.mkdtemp(prefix="vault_")
    root = Path(tmp)
    _build_vault(root, malformed=malformed)
    context["vault"] = root
    return root


# --- background ------------------------------------------------------------


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given("my Obsidian vault is available to the importer")
def _vault_available(context: dict) -> None:
    _make_vault(context)


# --- shared "run the import" steps ------------------------------------------


def _run_import(seed, context: dict) -> None:
    root = context["vault"]
    context["summary"] = seed(lambda s: _do_import(s, root))


@when("I run the import")
@when("the import finishes")
def _when_import(seed, context: dict) -> None:
    _run_import(seed, context)


# --- Scenario: Import the full history --------------------------------------


@then("my sessions, sets, measurements, steps, sleep and mobility records are loaded")
def _records_loaded(context: dict, bdd_client: TestClient) -> None:
    counts = context["summary"].counts
    for key in ("sessions", "sets", "measurements", "steps", "sleep", "mobility"):
        assert counts.get(key, 0) > 0, f"expected {key} imported, counts={counts}"
    # Cross-check a couple through the API.
    assert any(r["date"] == MEAS_DATE for r in bdd_client.get("/api/v1/measurements").json())
    assert bdd_client.get("/api/v1/sessions").json()


@then("each record keeps its original date")
def _dates_preserved(seed, context: dict, bdd_client: TestClient) -> None:
    meas_dates = {r["date"] for r in bdd_client.get("/api/v1/measurements").json()}
    assert MEAS_DATE in meas_dates

    # /api/v1/sessions only lists days that have sets; query the DB for all session
    # dates (the Logs note produced a session with no sets of its own).
    async def _dates(s):
        return (await s.scalars(select(WorkoutSession.date))).all()

    session_dates = seed(_dates)
    date_strs = {d.isoformat() if hasattr(d, "isoformat") else str(d) for d in session_dates}
    assert SET_DATE in date_strs  # the crunches set created a session for that day
    assert SESSION_DATE in date_strs  # the Logs note created a bare session


# --- Scenario: Bodyweight sets import with an empty weight -------------------


@given(parsers.parse('a logged set with reps "{reps}" and an empty weight'))
def _bodyweight_set(context: dict, reps: str) -> None:
    # The crunches set in the vault already has reps "15" and an empty weight.
    assert reps == "15"


@then(parsers.parse("it is stored as a bodyweight set of {reps:d} reps"))
def _stored_bodyweight(context: dict, bdd_client: TestClient, reps: int) -> None:
    sessions = bdd_client.get("/api/v1/sessions").json()
    day = next(s for s in sessions if s["date"] == SET_DATE)
    detail = bdd_client.get(f"/api/v1/sessions/{day['id']}").json()
    crunch = next(x for x in detail["sets"] if x["exercise_slug"] == "crunches")
    assert crunch["reps"] == str(reps)
    assert crunch["weight"] is None  # empty weight -> bodyweight
    assert crunch["display"] == f"BW × {reps}"


# --- Scenario: The current Obsidian plan becomes the active plan block -------


@given("the vault has a meal/training plan marked current")
def _plan_marked_current(context: dict) -> None:
    pass  # Meal-Plan.md carries `current: true`


@then("it becomes my active plan")
def _active_plan(context: dict, bdd_client: TestClient) -> None:
    resp = bdd_client.get("/api/v1/plans/current/detail")
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["start_date"] == "2026-05-21"  # from source "PT, 2026-05-21"
    labels = [td["label"] for td in detail["training_days"]]
    assert "Training Day 1" in labels
    assert context["summary"].counts.get("plans", 0) == 1


# --- Scenario: The import is re-runnable without duplicating -----------------


@given("I have already imported my history")
def _already_imported(seed, context: dict) -> None:
    _run_import(seed, context)


@when("I run the import again")
def _import_again(seed, context: dict) -> None:
    # Re-run against the same vault.
    context["summary_second"] = seed(lambda s: _do_import(s, context["vault"]))


@then("no duplicate records are created")
def _no_duplicates(context: dict, bdd_client: TestClient) -> None:
    # One measurement row per date.
    meas = bdd_client.get("/api/v1/measurements").json()
    assert len([r for r in meas if r["date"] == MEAS_DATE]) == 1
    # One session per date (the set-created day appears once).
    sessions = bdd_client.get("/api/v1/sessions").json()
    assert len([s for s in sessions if s["date"] == SET_DATE]) == 1
    # Exactly one active plan.
    assert bdd_client.get("/api/v1/plans/current/detail").status_code == 200
    # The bodyweight set is not duplicated.
    day = next(s for s in sessions if s["date"] == SET_DATE)
    detail = bdd_client.get(f"/api/v1/sessions/{day['id']}").json()
    crunches = [x for x in detail["sets"] if x["exercise_slug"] == "crunches"]
    assert len(crunches) == 1


@then("records changed in the vault are updated in place")
def _updated_in_place(seed, context: dict, bdd_client: TestClient) -> None:
    # Change the measurement in the vault, re-import, and confirm the same row updates.
    _write(
        context["vault"] / "Measurements" / f"{MEAS_DATE}.md",
        f"---\ndate: {MEAS_DATE}\nweight_kg: 80.0\nwaist_cm: 95\n---\n",
    )
    seed(lambda s: _do_import(s, context["vault"]))
    meas = bdd_client.get("/api/v1/measurements").json()
    rows = [r for r in meas if r["date"] == MEAS_DATE]
    assert len(rows) == 1
    assert rows[0]["weight_kg"] == 80.0


# --- Scenario: Unparseable files reported, never silently dropped -----------


@given("one record file is malformed")
def _one_malformed(context: dict) -> None:
    # Rebuild the vault including a malformed measurement note.
    _make_vault(context, malformed=True)


@then("that file is listed in the import summary as needing attention")
def _listed_in_failures(context: dict) -> None:
    failures = context["summary"].failures
    assert any("broken.md" in f for f in failures), f"failures={failures}"


@then("the rest of the import still completes")
def _rest_completes(context: dict, bdd_client: TestClient) -> None:
    counts = context["summary"].counts
    # The valid measurement still landed despite the broken sibling.
    assert counts.get("measurements", 0) >= 1
    assert any(r["date"] == MEAS_DATE for r in bdd_client.get("/api/v1/measurements").json())
    assert counts.get("steps", 0) > 0


# --- Scenario: The import reports what it did -------------------------------


@then(
    parsers.parse(
        "I see counts of how many sessions, sets, measurements, steps, "
        "sleep and mobility records were imported"
    )
)
def _reports_counts(context: dict) -> None:
    counts = context["summary"].counts
    assert isinstance(counts, dict) and counts
    for key in ("sessions", "sets", "measurements", "steps", "sleep", "mobility"):
        assert key in counts, f"missing {key} in {counts}"


# --- Scenario: The last-week column works immediately after import ----------


@given("my history is imported")
def _history_imported(seed, context: dict) -> None:
    _run_import(seed, context)


@when("I open today's session")
def _open_todays_session(context: dict, bdd_client: TestClient) -> None:
    # last-week for leg-press before SET_DATE should surface the prior weighted session.
    context["last_week"] = bdd_client.get(
        "/api/v1/exercises/leg-press-machine/last-week", params={"before": SET_DATE}
    )


@then("the last-week column shows numbers drawn from my imported history")
def _last_week_shows(context: dict) -> None:
    resp = context["last_week"]
    assert resp.status_code == 200, resp.text
    display = resp.json()["display"]
    assert display not in ("—", ""), f"expected a number, got {display!r}"
    # The prior leg-press set was 50kg.
    assert "50" in display
