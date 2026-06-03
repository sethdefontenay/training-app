"""Config: Railway/Heroku DATABASE_URL normalization to asyncpg."""

from app.config import Settings


def test_postgresql_url_gets_asyncpg() -> None:
    s = Settings(database_url="postgresql://u:p@host:5432/db")
    assert s.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_postgres_scheme_gets_asyncpg() -> None:
    s = Settings(database_url="postgres://u:p@host/db")
    assert s.database_url == "postgresql+asyncpg://u:p@host/db"


def test_already_asyncpg_unchanged() -> None:
    s = Settings(database_url="postgresql+asyncpg://u:p@host/db")
    assert s.database_url == "postgresql+asyncpg://u:p@host/db"
