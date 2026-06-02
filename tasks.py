"""Developer tasks for training-app.

Run with `invoke <task>` (or `uvx invoke <task>` if invoke isn't installed globally).
List everything with `invoke -l`.

Common flows:
  invoke bootstrap --email you@example.com --password secret   # first-time full setup
  invoke up                                                    # db + migrate, then run servers
  invoke backend        # API on :8000 (/docs)
  invoke frontend       # PWA on :5173
  invoke ci             # lint + tests + frontend build (what CI runs)
"""

import subprocess
import time

from invoke import task

BACKEND = "backend"
FRONTEND = "frontend"
DEFAULT_VAULT = "/mnt/c/automation/Training"


# --- setup -----------------------------------------------------------------


@task
def install(c):
    """Install backend (uv) and frontend (npm) dependencies."""
    with c.cd(BACKEND):
        c.run("uv sync")
    with c.cd(FRONTEND):
        c.run("npm install")


@task
def bootstrap(c, email=None, password=None):
    """First-time setup: deps + db + migrations (+ seed a login if email/password given)."""
    install(c)
    db_up(c)
    migrate(c)
    if email and password:
        seed(c, email, password)
    print("\nBootstrapped. Now run `invoke backend` and `invoke frontend` (separate terminals).")


# --- database --------------------------------------------------------------


@task
def db_up(c):
    """Start Postgres via docker compose and wait until healthy."""
    c.run("docker compose up -d --wait db")


@task
def db_down(c):
    """Stop the local stack (keeps the data volume)."""
    c.run("docker compose down")


@task
def db_reset(c):
    """Drop the Postgres volume and recreate an empty, migrated database."""
    c.run("docker compose down -v")
    db_up(c)
    migrate(c)


@task
def migrate(c):
    """Apply Alembic migrations (upgrade head)."""
    with c.cd(BACKEND):
        c.run("uv run alembic upgrade head")


@task(help={"message": "short migration message"})
def makemigration(c, message):
    """Autogenerate a new Alembic migration from model changes."""
    with c.cd(BACKEND):
        c.run(f'uv run alembic revision --autogenerate -m "{message}"')


# --- data ------------------------------------------------------------------


@task(help={"email": "login email", "password": "login password"})
def seed(c, email, password):
    """Create or reset the single user's login."""
    with c.cd(BACKEND):
        c.run(f"uv run python -m app.seed {email} {password}", pty=True)


@task(help={"path": f"vault path (default {DEFAULT_VAULT})"})
def import_vault(c, path=DEFAULT_VAULT):
    """Import the full Obsidian history into the DB (idempotent, re-runnable)."""
    with c.cd(BACKEND):
        c.run(f'uv run python -m app.import_vault "{path}"', pty=True)


# --- run -------------------------------------------------------------------


@task
def backend(c):
    """Run the API with auto-reload (http://localhost:8000, docs at /docs)."""
    with c.cd(BACKEND):
        c.run("uv run uvicorn app.main:app --reload", pty=True)


@task
def frontend(c):
    """Run the Vite dev server (http://localhost:5173)."""
    with c.cd(FRONTEND):
        c.run("npm run dev", pty=True)


@task
def dev(c):
    """Start everything in one: db + migrations, then backend + frontend together.

    Streams both logs; Ctrl+C stops both.
    """
    db_up(c)
    migrate(c)
    print(
        "\nStarting servers — Ctrl+C to stop both."
        "\n  API      : http://localhost:8000  (/docs)"
        "\n  Frontend : http://localhost:5173\n"
    )
    procs = [
        subprocess.Popen(["uv", "run", "uvicorn", "app.main:app", "--reload"], cwd=BACKEND),
        subprocess.Popen(["npm", "run", "dev"], cwd=FRONTEND),
    ]
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


@task
def up(c):
    """Bring up db + migrations, then print how to start the servers."""
    db_up(c)
    migrate(c)
    print("\nDB up and migrated. In two terminals:")
    print("  invoke backend     # API on :8000  (/docs)")
    print("  invoke frontend    # PWA on :5173")
    print("First run? create a login:  invoke seed --email you@example.com --password secret")


# --- quality ---------------------------------------------------------------


@task
def test(c):
    """Run the backend test suite."""
    with c.cd(BACKEND):
        c.run("uv run pytest", pty=True)


@task
def lint(c):
    """Lint + type-check backend, lint frontend (no changes)."""
    with c.cd(BACKEND):
        c.run("uv run ruff check .")
        c.run("uv run ruff format --check .")
        c.run("uv run mypy app")
    with c.cd(FRONTEND):
        c.run("npm run lint")


@task
def fmt(c):
    """Auto-fix lint + format the backend."""
    with c.cd(BACKEND):
        c.run("uv run ruff check --fix .")
        c.run("uv run ruff format .")


@task
def ci(c):
    """Run everything CI runs: backend lint+tests, frontend build."""
    lint(c)
    test(c)
    with c.cd(FRONTEND):
        c.run("npm run build")
