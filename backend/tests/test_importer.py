"""obsidian_import.feature: full import, bodyweight handling, idempotency, failure reporting."""

import textwrap
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.importer import import_vault
from app.models import Exercise, Measurement, MobilityDone, SetEntry, StepsDay


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _build_vault(root: Path) -> Path:
    vault = root / "vault"
    _write(
        vault / "Sets" / "2026-05-25-leg-press-machine-1.md",
        """
        ---
        date: 2026-05-25
        exercise: leg-press-machine
        set_index: 1
        reps: "15"
        weight: "40"
        ---
        """,
    )
    _write(
        vault / "Sets" / "2026-05-25-crunches-1.md",
        """
        ---
        date: 2026-05-25
        exercise: crunches
        set_index: 1
        reps: "15"
        weight: ""
        ---
        """,
    )
    _write(
        vault / "Measurements" / "2026-05-25.md",
        """
        ---
        date: 2026-05-25
        waist_cm: "96"
        weight_kg: "94"
        ---
        """,
    )
    _write(
        vault / "Steps" / "2026-05-25.md",
        """
        ---
        date: 2026-05-25
        steps: 733
        target_steps: 7000
        target_met: false
        ---
        """,
    )
    _write(
        vault / "Mobility-Done" / "2026-05-22-bird-dog.md",
        """
        ---
        date: 2026-05-22
        exercise: bird-dog
        ---
        """,
    )
    _write(vault / "Steps" / "broken.md", "this file has no frontmatter\n")
    return vault


async def test_full_import(tmp_path: Path, session: AsyncSession) -> None:
    vault = _build_vault(tmp_path)
    summary = await import_vault(session, vault)

    assert summary.counts["sets"] == 2
    assert summary.counts["measurements"] == 1
    assert summary.counts["steps"] == 1
    assert summary.counts["mobility"] == 1


async def test_bodyweight_set_imports_with_empty_weight(
    tmp_path: Path, session: AsyncSession
) -> None:
    vault = _build_vault(tmp_path)
    await import_vault(session, vault)

    crunch = await session.scalar(
        select(SetEntry).join(Exercise).where(Exercise.slug == "crunches")
    )
    assert crunch is not None
    assert crunch.weight is None
    assert crunch.reps == "15"


async def test_unparseable_file_is_reported_not_dropped(
    tmp_path: Path, session: AsyncSession
) -> None:
    vault = _build_vault(tmp_path)
    summary = await import_vault(session, vault)
    assert any("broken.md" in f for f in summary.failures)
    # the rest still imported
    assert (await session.scalar(select(func.count()).select_from(StepsDay))) == 1


async def test_import_is_rerunnable_without_duplicating(
    tmp_path: Path, session: AsyncSession
) -> None:
    vault = _build_vault(tmp_path)
    await import_vault(session, vault)
    await import_vault(session, vault)

    assert (await session.scalar(select(func.count()).select_from(SetEntry))) == 2
    assert (await session.scalar(select(func.count()).select_from(Measurement))) == 1
    assert (await session.scalar(select(func.count()).select_from(MobilityDone))) == 1
