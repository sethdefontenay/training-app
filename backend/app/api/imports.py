"""Import endpoints — push an Obsidian vault to a deployed instance via the API.

Lets you load history into prod without exposing the database: upload a zip of the
vault, the server extracts it to a temp dir and runs the same importer.
"""

import tempfile
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.importer import import_vault

router = APIRouter(prefix="/import", tags=["import"])

_VAULT_MARKERS = ("Plan", "Sets", "Logs", "Measurements", "Exercises", "Steps", "Sleep")


def _find_vault_root(base: Path) -> Path:
    """The extracted root, or a single wrapping folder if the zip nested the vault."""
    if any((base / m).is_dir() for m in _VAULT_MARKERS):
        return base
    for child in sorted(base.iterdir()):
        if child.is_dir() and any((child / m).is_dir() for m in _VAULT_MARKERS):
            return child
    return base


@router.post("/vault")
async def import_vault_zip(
    session: SessionDep, user: CurrentUser, file: Annotated[UploadFile, File()]
) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        zip_path = root / "vault.zip"
        zip_path.write_bytes(await file.read())
        extract_dir = root / "vault"
        extract_dir.mkdir()
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.namelist():
                    dest = (extract_dir / member).resolve()
                    if not str(dest).startswith(str(extract_dir.resolve())):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Unsafe path in archive",
                        )
                zf.extractall(extract_dir)
        except zipfile.BadZipFile as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Not a valid zip file"
            ) from e
        summary = await import_vault(session, _find_vault_root(extract_dir), user.id)
    return {"counts": summary.counts, "failures": summary.failures}
