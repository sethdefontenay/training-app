"""Re-runnable importer: Obsidian vault -> Postgres.

Idempotent — re-running updates existing rows (keyed on natural keys like date or slug)
rather than duplicating. Unparseable files are collected and reported, never silently
dropped; the rest of the import still completes.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Exercise,
    Measurement,
    MobilityDone,
    Session,
    SetEntry,
    SleepNight,
    StepsDay,
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


async def import_vault(session: AsyncSession, vault: Path) -> ImportSummary:
    summary = ImportSummary()
    await _import_exercises(session, vault / "Exercises", summary)
    await _import_measurements(session, vault / "Measurements", summary)
    await _import_steps(session, vault / "Steps", summary)
    await _import_sleep(session, vault / "Sleep", summary)
    await _import_sessions(session, vault / "Logs", summary)
    await _import_sets(session, vault / "Sets", summary)
    await _import_mobility(session, vault / "Mobility-Done", summary)
    await session.commit()
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
