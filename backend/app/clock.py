"""Time helpers anchored to the user's configured timezone.

Everything "today"-shaped must use this rather than date.today()/datetime.now(),
which follow the server's UTC clock and trail the user's local date for UTC+
zones (e.g. NZ) — that mismatch is what made daily data appear a day off.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def local_now() -> datetime:
    """Current time in the user's configured timezone (tz-aware)."""
    return datetime.now(ZoneInfo(get_settings().timezone))


def local_today() -> date:
    """Today's date in the user's configured timezone."""
    return local_now().date()
