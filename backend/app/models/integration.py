"""UI-managed integration settings (key/value), e.g. Google Health OAuth config."""

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class IntegrationSetting(Base, TimestampMixin):
    __tablename__ = "integration_setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True, index=True)  # e.g. "google_health.refresh_token"
    value: Mapped[str | None] = mapped_column(default=None)
