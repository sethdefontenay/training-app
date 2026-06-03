"""API-based vault import: upload a zip, server extracts + imports (no DB access needed)."""

import io
import textwrap
import zipfile

from httpx import AsyncClient


def _make_vault_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "Sets/2026-05-25-leg-press-machine-1.md",
            textwrap.dedent(
                """
                ---
                date: 2026-05-25
                exercise: leg-press-machine
                set_index: 1
                reps: "15"
                weight: "40"
                ---
                """
            ).lstrip(),
        )
        zf.writestr(
            "Measurements/2026-05-25.md",
            textwrap.dedent(
                """
                ---
                date: 2026-05-25
                waist_cm: "96"
                ---
                """
            ).lstrip(),
        )
    return buf.getvalue()


async def test_import_vault_via_api(auth_client: AsyncClient) -> None:
    files = {"file": ("vault.zip", _make_vault_zip(), "application/zip")}
    resp = await auth_client.post("/api/v1/import/vault", files=files)
    assert resp.status_code == 200
    counts = resp.json()["counts"]
    assert counts["sets"] == 1
    assert counts["measurements"] == 1


async def test_import_rejects_non_zip(auth_client: AsyncClient) -> None:
    files = {"file": ("x.zip", b"not a zip at all", "application/zip")}
    resp = await auth_client.post("/api/v1/import/vault", files=files)
    assert resp.status_code == 400


async def test_import_requires_auth(client: AsyncClient) -> None:
    files = {"file": ("vault.zip", _make_vault_zip(), "application/zip")}
    resp = await client.post("/api/v1/import/vault", files=files)
    assert resp.status_code == 401
