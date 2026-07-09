"""Application users. Each user owns a private, per-user dataset."""

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column()
    # DEPRECATED: the owner/trainer role axis is retired in U8 (multiuser drops the
    # read-only trainer). Kept here until enforce_role_access is removed so intermediate
    # commits stay green.
    role: Mapped[str] = mapped_column(default="owner", server_default="owner")

    # Admin (invite minting, user provisioning). Seth's account only.
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="false")

    # Per-user capability flags. Default OFF (fail-closed): invited users get the
    # workout + diet surface; the owner's account is elevated in the backfill/seed.
    #   has_diabetes             -> T1D screens + glucose/insulin data
    #   has_health_integrations  -> Google Health + Tidepool + steps/sleep
    #   has_checkins             -> weekly progress check-ins + photos
    has_diabetes: Mapped[bool] = mapped_column(default=False, server_default="false")
    has_health_integrations: Mapped[bool] = mapped_column(default=False, server_default="false")
    has_checkins: Mapped[bool] = mapped_column(default=False, server_default="false")

    # Per-user local timezone for "today" boundaries (moved off global config).
    timezone: Mapped[str] = mapped_column(
        default="Pacific/Auckland", server_default="Pacific/Auckland"
    )
