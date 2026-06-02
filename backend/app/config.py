"""Application settings, loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "training-app"
    environment: str = "development"

    # Where uploaded check-in photos are stored (object storage in prod; local dir for dev).
    upload_dir: str = "uploads"

    # Database — async SQLAlchemy URL. Defaults to local docker-compose Postgres.
    database_url: str = "postgresql+asyncpg://training:training@localhost:5432/training"

    # Auth (single user). Overridden in prod via env.
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 60 * 24 * 14  # 14 days — long-lived on trusted phone


@lru_cache
def get_settings() -> Settings:
    return Settings()
