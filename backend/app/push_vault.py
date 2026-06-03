"""Zip a local Obsidian vault and push it to a deployed training-app via the API.

Usage: uv run python -m app.push_vault <base_url> <email> <password> <vault_path>
(Or via invoke: `invoke import-vault-remote --base-url ... --email ... --password ...`.)

Logs in, zips the vault, and POSTs it to /api/v1/import/vault — no DB access needed.
"""

import sys
import tempfile
import zipfile
from pathlib import Path

import httpx


def main() -> None:
    if len(sys.argv) != 5:
        print("usage: python -m app.push_vault <base_url> <email> <password> <vault_path>")
        raise SystemExit(1)
    base_url = sys.argv[1].rstrip("/")
    email, password, vault = sys.argv[2], sys.argv[3], sys.argv[4]
    vault_path = Path(vault)
    if not vault_path.is_dir():
        print(f"vault path not found: {vault_path}")
        raise SystemExit(1)

    login = httpx.post(
        f"{base_url}/api/v1/auth/login", json={"email": email, "password": password}, timeout=30
    )
    login.raise_for_status()
    token = login.json()["access_token"]

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "vault.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in vault_path.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(vault_path))
        with open(zip_path, "rb") as fh:
            resp = httpx.post(
                f"{base_url}/api/v1/import/vault",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("vault.zip", fh, "application/zip")},
                timeout=600,
            )
    resp.raise_for_status()
    print("Imported:", resp.json())


if __name__ == "__main__":
    main()
