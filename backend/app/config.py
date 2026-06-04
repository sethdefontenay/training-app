"""Application settings, loaded from environment / .env."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "training-app"
    environment: str = "development"

    # The user's local timezone. Used for "today" boundaries (health sync window,
    # daily-data day buckets) so they match the phone's local date rather than the
    # server's UTC clock. Single user → single zone.
    timezone: str = "Pacific/Auckland"

    # Where uploaded check-in photos are stored (object storage in prod; local dir for dev).
    upload_dir: str = "uploads"

    # Database — async SQLAlchemy URL. Defaults to local docker-compose Postgres.
    database_url: str = "postgresql+asyncpg://training:training@localhost:5432/training"

    # Auth (single user). Overridden in prod via env.
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 60 * 24 * 14  # 14 days — long-lived on trusted phone

    # OAuth (Google Health connect flow). Override in prod via env.
    # The redirect URI must be registered in the Google Cloud OAuth client.
    google_redirect_uri: str = "http://localhost:8000/api/v1/settings/google-health/callback"
    frontend_url: str = "http://localhost:5173"

    # Optional: create/refresh the single user on startup (handy for first prod deploy).
    seed_email: str | None = None
    seed_password: str | None = None

    # In-app assistant (Claude). Pay-per-token Anthropic API — separate from any
    # Claude subscription. The bot is disabled until anthropic_api_key is set.
    anthropic_api_key: str | None = None
    assistant_model: str = "claude-opus-4-8"

    # Set to enable the MCP server at /mcp for external clients (Claude Desktop/Code/
    # claude.ai). Every /mcp request must send `Authorization: Bearer <this>`.
    mcp_token: str | None = None

    @field_validator("database_url")
    @classmethod
    def _ensure_asyncpg(cls, v: str) -> str:
        # Railway/Heroku give postgres://|postgresql:// — our async stack needs asyncpg.
        if v.startswith("postgresql+"):
            return v
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix) :]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
