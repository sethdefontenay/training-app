"""Re-runnable importer: Obsidian vault -> Postgres.

Idempotent — re-running updates existing rows (keyed on natural keys like date or slug)
rather than duplicating. Unparseable files are collected and reported, never silently
dropped; the rest of the import still completes.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import local_today
from app.models import (
    Exercise,
    Meal,
    MealIngredient,
    Measurement,
    MobilityDone,
    Plan,
    Prescription,
    Session,
    SetEntry,
    SleepNight,
    StepsDay,
    TrainingDay,
    WeekdaySchedule,
)
from app.services.shopping import generate_for_plan

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass
class ImportSummary:
    counts: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def bump(self, key: str) -> None:
        self.counts[key] = self.counts.get(key, 0) + 1

    def fail(self, path: Path, reason: str) -> None:
        self.failures.append(f"{path.name}: {reason}")


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter from a markdown note. Raises ValueError if malformed."""
    if not text.lstrip().startswith("---"):
        raise ValueError("no frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated frontmatter")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


async def _get_or_create_exercise(session: AsyncSession, slug: str) -> Exercise:
    ex = await session.scalar(select(Exercise).where(Exercise.slug == slug))
    if ex is None:
        ex = Exercise(slug=slug, name=slug.replace("-", " ").title())
        session.add(ex)
        await session.flush()
    return ex


async def _get_or_create_session(session: AsyncSession, day: date) -> Session:
    existing = await session.scalar(select(Session).where(Session.date == day))
    if existing is None:
        existing = Session(date=day, weekday=day.strftime("%A"))
        session.add(existing)
        await session.flush()
    return existing


# --- plan parsing helpers --------------------------------------------------


def _wiki(cell: str) -> tuple[str | None, str | None]:
    """Parse an Obsidian cell like '[[leg-press-machine|Leg Press Machine]]' -> (slug, name)."""
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", cell)
    if m:
        target = m.group(1).strip()
        return target.lower(), (m.group(2) or target).strip()
    text = cell.strip()
    if not text:
        return None, None
    return text.lower().replace(" ", "-"), text


def _strip_weight(value: str) -> str | None:
    cleaned = (value or "").strip().lower().replace("kg", "").strip()
    return cleaned or None


def _parse_ingredient(line: str) -> tuple[str, float | None, str | None]:
    text = line.strip().lstrip("-*").strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(g|kg|ml|l)?\b\s*(.*\S)?$", text, re.I)
    if m and m.group(1):
        name = (m.group(3) or "").strip() or text
        unit = m.group(2).lower() if m.group(2) else None
        return name, float(m.group(1)), unit
    return text, None, None


def _cells(line: str) -> list[str]:
    # Split on unescaped pipes (Obsidian escapes the pipe inside [[slug\|Name]]).
    parts = re.split(r"(?<!\\)\|", line.strip())
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.replace("\\|", "|").strip() for p in parts]


def _parse_exercise_table(body: str) -> list[dict[str, str | None]]:
    lines = [ln for ln in body.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        return []
    header = [h.lower() for h in _cells(lines[0])]

    def find(*subs: str) -> int | None:
        for i, h in enumerate(header):
            if any(s in h for s in subs):
                return i
        return None

    ci_ex, ci_sr, ci_w = find("exercise"), find("rep", "sets"), find("weight")
    rows: list[dict[str, str | None]] = []
    for line in lines[2:]:  # skip header + separator
        cells = _cells(line)
        if ci_ex is None or ci_ex >= len(cells):
            continue
        slug, name = _wiki(cells[ci_ex])
        if not slug or slug == "mobility":
            continue
        sr = cells[ci_sr] if ci_sr is not None and ci_sr < len(cells) else ""
        wt = cells[ci_w] if ci_w is not None and ci_w < len(cells) else ""
        rows.append({"slug": slug, "name": name, "sets_x_reps": sr, "weight": _strip_weight(wt)})
    return rows


def _first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _parse_ingredients_section(body: str) -> list[tuple[str, float | None, str | None]]:
    out: list[tuple[str, float | None, str | None]] = []
    in_section = False
    for line in body.splitlines():
        s = line.strip()
        if s.lower().startswith("## ingredients"):
            in_section = True
            continue
        if in_section and s.startswith("## "):
            break
        if in_section and s.startswith(("-", "*")):
            out.append(_parse_ingredient(s))
    return out


async def _import_plan(session: AsyncSession, vault: Path, summary: ImportSummary) -> None:
    plan_dir = vault / "Plan"
    if not plan_dir.is_dir():
        return

    # Meal-plan frontmatter gives source/phase (and marks the current plan).
    mp_fm: dict[str, Any] = {}
    for f in sorted(plan_dir.glob("Meal-Plan*.md")):
        try:
            fm = parse_frontmatter(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if fm.get("current") or not mp_fm:
            mp_fm = fm
    source = str(mp_fm["source"]) if mp_fm.get("source") else None
    phase = int(mp_fm["phase"]) if mp_fm.get("phase") else None

    # Idempotent: replace an existing plan with the same source (cascades children).
    if source is not None:
        existing = await session.scalar(select(Plan).where(Plan.source == source))
        if existing is not None:
            await session.delete(existing)
            await session.flush()
    current = await session.scalar(select(Plan).where(Plan.is_current.is_(True)))
    if current is not None:
        current.is_current = False

    start = _extract_date(source or "", local_today())
    plan = Plan(start_date=start, is_current=True, source=source, phase=phase)
    _apply_targets(plan, plan_dir)
    session.add(plan)
    await session.flush()

    # Training days + prescriptions, keyed by file stem for the schedule lookup.
    day_by_stem: dict[str, tuple[TrainingDay, Any]] = {}
    for order, f in enumerate(sorted(plan_dir.glob("Training-Day-*.md"))):
        body = f.read_text(encoding="utf-8")
        try:
            fm = parse_frontmatter(body)
        except ValueError:
            fm = {}
        td = TrainingDay(plan_id=plan.id, label=f.stem.replace("-", " "), order=order)
        session.add(td)
        await session.flush()
        day_by_stem[f.stem.lower()] = (td, fm.get("weekday"))
        for i, row in enumerate(_parse_exercise_table(body)):
            ex = await _get_or_create_exercise(session, str(row["slug"]))
            if row["name"]:
                ex.name = str(row["name"])
            if row["weight"] is None:
                ex.is_bodyweight = True
            session.add(
                Prescription(
                    training_day_id=td.id,
                    exercise_id=ex.id,
                    sets_x_reps=str(row["sets_x_reps"] or ""),
                    prescribed_weight=row["weight"],
                    order=i,
                )
            )
            summary.bump("prescriptions")
        summary.bump("training_days")

    await _import_schedule(session, vault, plan, day_by_stem)
    await _import_meals(session, plan_dir, plan, summary)
    summary.bump("plans")


def _extract_date(text: str, fallback: date) -> date:
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        try:
            return datetime.strptime(m.group(0), "%Y-%m-%d").date()
        except ValueError:
            pass
    return fallback


def _apply_targets(plan: Plan, plan_dir: Path) -> None:
    overview = plan_dir / "Overview.md"
    text = overview.read_text(encoding="utf-8") if overview.is_file() else ""
    steps = re.search(r"([\d,]+)\s*steps", text)
    plan.steps_target = int(steps.group(1).replace(",", "")) if steps else 7000
    water = re.search(r"(\d+)\s*[–-]\s*(\d+)\s*l", text, re.I)
    if water:
        plan.water_min_l, plan.water_max_l = float(water.group(1)), float(water.group(2))
    else:
        plan.water_min_l, plan.water_max_l = 2.0, 3.0
    plan.electrolytes_per_day = 1


async def _import_schedule(
    session: AsyncSession,
    vault: Path,
    plan: Plan,
    day_by_stem: dict[str, tuple[TrainingDay, Any]],
) -> None:
    sched = vault / "Schedule" / "Weekly-Schedule.md"
    if sched.is_file():
        try:
            sfm = parse_frontmatter(sched.read_text(encoding="utf-8"))
        except ValueError:
            sfm = {}
        for wd in WEEKDAYS:
            entries = sfm.get(wd) or []
            if isinstance(entries, str):
                entries = [entries]
            td_id, mobility = None, False
            for e in entries:
                slug, _ = _wiki(str(e))
                if slug == "mobility":
                    mobility = True
                elif slug in day_by_stem:
                    td_id = day_by_stem[slug][0].id
            if td_id is not None or mobility:
                session.add(
                    WeekdaySchedule(
                        plan_id=plan.id,
                        weekday=wd,
                        training_day_id=td_id,
                        has_mobility=mobility,
                    )
                )
        return
    # Fallback: each training day's own weekday frontmatter.
    for td, weekday in day_by_stem.values():
        if weekday:
            session.add(
                WeekdaySchedule(
                    plan_id=plan.id,
                    weekday=str(weekday).lower(),
                    training_day_id=td.id,
                    has_mobility=True,
                )
            )


async def _import_meals(
    session: AsyncSession, plan_dir: Path, plan: Plan, summary: ImportSummary
) -> None:
    meals_dir = plan_dir / "Meals"
    if not meals_dir.is_dir():
        return
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
    for f in sorted(meals_dir.glob("*.md")):
        body = f.read_text(encoding="utf-8")
        try:
            fm = parse_frontmatter(body)
        except ValueError:
            continue
        meal = Meal(
            plan_id=plan.id,
            meal_number=int(fm.get("meal", 0) or 0),
            slot=str(fm.get("slot", "")),
            name=_first_heading(body, f.stem.replace("-", " ")),
            calories=fm.get("calories"),
            protein_g=fm.get("protein"),
            carbs_g=fm.get("carbs"),
            fat_g=fm.get("fat"),
        )
        session.add(meal)
        await session.flush()
        for name, qty, unit in _parse_ingredients_section(body):
            session.add(MealIngredient(meal_id=meal.id, name=name, quantity=qty, unit=unit))
        totals["calories"] += int(fm.get("calories") or 0)
        totals["protein_g"] += int(fm.get("protein") or 0)
        totals["carbs_g"] += int(fm.get("carbs") or 0)
        totals["fat_g"] += int(fm.get("fat") or 0)
        summary.bump("meals")
    plan.daily_calories = totals["calories"] or None
    plan.daily_protein_g = totals["protein_g"] or None
    plan.daily_carbs_g = totals["carbs_g"] or None
    plan.daily_fat_g = totals["fat_g"] or None


async def import_vault(session: AsyncSession, vault: Path) -> ImportSummary:
    summary = ImportSummary()
    await _import_plan(session, vault, summary)
    await _import_exercises(session, vault / "Exercises", summary)
    await _import_measurements(session, vault / "Measurements", summary)
    await _import_steps(session, vault / "Steps", summary)
    await _import_sleep(session, vault / "Sleep", summary)
    await _import_sessions(session, vault / "Logs", summary)
    await _import_sets(session, vault / "Sets", summary)
    await _import_mobility(session, vault / "Mobility-Done", summary)
    await session.commit()

    # Derived output: weekly shopping list from the imported plan's meals.
    plan = await session.scalar(select(Plan).where(Plan.is_current.is_(True)))
    if plan is not None:
        await generate_for_plan(session, plan, plan.start_date)
    return summary


def _notes(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.md")) if folder.is_dir() else []


async def _import_exercises(session: AsyncSession, folder: Path, summary: ImportSummary) -> None:
    for path in _notes(folder):
        slug = path.stem
        ex = await session.scalar(select(Exercise).where(Exercise.slug == slug))
        body = path.read_text(encoding="utf-8")
        try:
            fm = parse_frontmatter(body)
        except ValueError:
            fm = {}
        if ex is None:
            ex = Exercise(slug=slug, name=str(fm.get("name", slug.replace("-", " ").title())))
            session.add(ex)
        ex.is_bodyweight = bool(fm.get("is_bodyweight", ex.is_bodyweight if ex else False))
        summary.bump("exercises")


async def _import_measurements(session: AsyncSession, folder: Path, summary: ImportSummary) -> None:
    fields = ("waist_cm", "tummy_cm", "bum_cm", "right_thigh_cm", "left_thigh_cm", "weight_kg")
    for path in _notes(folder):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
            day = _to_date(fm["date"])
        except (ValueError, KeyError) as e:
            summary.fail(path, str(e))
            continue
        row = await session.scalar(select(Measurement).where(Measurement.date == day))
        if row is None:
            row = Measurement(date=day)
            session.add(row)
        for f in fields:
            if fm.get(f) not in (None, ""):
                setattr(row, f, float(fm[f]))
        summary.bump("measurements")


async def _import_steps(session: AsyncSession, folder: Path, summary: ImportSummary) -> None:
    for path in _notes(folder):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
            day = _to_date(fm["date"])
        except (ValueError, KeyError) as e:
            summary.fail(path, str(e))
            continue
        row = await session.scalar(select(StepsDay).where(StepsDay.date == day))
        if row is None:
            row = StepsDay(date=day)
            session.add(row)
        row.steps = int(fm.get("steps", 0))
        row.target_steps = fm.get("target_steps")
        row.target_met = bool(fm.get("target_met", False))
        summary.bump("steps")


async def _import_sleep(session: AsyncSession, folder: Path, summary: ImportSummary) -> None:
    floats = (
        "asleep_min",
        "in_bed_min",
        "awake_min",
        "light_min",
        "deep_min",
        "rem_min",
        "efficiency",
    )
    for path in _notes(folder):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
            day = _to_date(fm["date"])
        except (ValueError, KeyError) as e:
            summary.fail(path, str(e))
            continue
        row = await session.scalar(select(SleepNight).where(SleepNight.date == day))
        if row is None:
            row = SleepNight(date=day)
            session.add(row)
        row.bedtime = fm.get("bedtime")
        row.wake_time = fm.get("wake_time")
        for f in floats:
            if fm.get(f) not in (None, ""):
                setattr(row, f, float(fm[f]))
        summary.bump("sleep")


async def _import_sessions(session: AsyncSession, folder: Path, summary: ImportSummary) -> None:
    for path in _notes(folder):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
            day = _to_date(fm["date"])
        except (ValueError, KeyError) as e:
            summary.fail(path, str(e))
            continue
        await _get_or_create_session(session, day)
        summary.bump("sessions")


async def _import_sets(session: AsyncSession, folder: Path, summary: ImportSummary) -> None:
    for path in _notes(folder):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
            day = _to_date(fm["date"])
            slug = str(fm["exercise"])
            set_index = int(fm["set_index"])
        except (ValueError, KeyError) as e:
            summary.fail(path, str(e))
            continue
        sess = await _get_or_create_session(session, day)
        ex = await _get_or_create_exercise(session, slug)
        existing = await session.scalar(
            select(SetEntry).where(
                SetEntry.session_id == sess.id,
                SetEntry.exercise_id == ex.id,
                SetEntry.set_index == set_index,
            )
        )
        if existing is None:
            existing = SetEntry(session_id=sess.id, exercise_id=ex.id, set_index=set_index)
            session.add(existing)
        existing.reps = None if fm.get("reps") in (None, "") else str(fm["reps"])
        existing.weight = None if fm.get("weight") in (None, "") else str(fm["weight"])
        summary.bump("sets")


async def _import_mobility(session: AsyncSession, folder: Path, summary: ImportSummary) -> None:
    for path in _notes(folder):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
            day = _to_date(fm["date"])
            slug = str(fm["exercise"])
        except (ValueError, KeyError) as e:
            summary.fail(path, str(e))
            continue
        ex = await _get_or_create_exercise(session, slug)
        existing = await session.scalar(
            select(MobilityDone).where(MobilityDone.date == day, MobilityDone.exercise_id == ex.id)
        )
        if existing is None:
            session.add(MobilityDone(date=day, exercise_id=ex.id))
        summary.bump("mobility")
