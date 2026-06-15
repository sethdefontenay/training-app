"""The single user (auth)."""

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column()
    # "owner" has full access; "trainer" is read-only everywhere except the assistant
    # chat, and cannot touch settings. Enforced in app.api.deps.enforce_role_access.
    role: Mapped[str] = mapped_column(default="owner", server_default="owner")
