"""Settings endpoints: manage integration connections from the UI."""

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.config import get_settings
from app.services.settings import (
    GOOGLE_HEALTH_FIELDS,
    TIDEPOOL_FIELDS,
    get_setting,
    google_health_config,
    set_setting,
    tidepool_config,
)

router = APIRouter(prefix="/settings", tags=["settings"])

_settings = get_settings()
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPES = (
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly "
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly"
)


def _back(outcome: str) -> RedirectResponse:
    return RedirectResponse(f"{_settings.frontend_url}/settings?gh={outcome}")


class GoogleHealthIn(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None


async def _gh_status(session: SessionDep) -> dict[str, object]:
    cfg = await google_health_config(session)
    auth_error = await get_setting(session, "google_health.auth_error")
    # Never echo secret values back — only whether each field is set.
    return {
        "connected": all(cfg.values()),
        # Connected but the refresh token died — the UI shows a one-tap reconnect.
        "needs_reconnect": all(cfg.values()) and bool(auth_error),
        "fields": [
            {"key": k, "label": label, "set": bool(cfg[k])} for k, label in GOOGLE_HEALTH_FIELDS
        ],
    }


@router.get("/google-health")
async def google_health_status(session: SessionDep, user: CurrentUser) -> dict[str, object]:
    return await _gh_status(session)


@router.put("/google-health")
async def google_health_save(
    body: GoogleHealthIn, session: SessionDep, user: CurrentUser
) -> dict[str, object]:
    for key, _ in GOOGLE_HEALTH_FIELDS:
        value = getattr(body, key)
        if value is not None:
            await set_setting(session, f"google_health.{key}", value)
    await session.commit()
    return await _gh_status(session)


class TidepoolIn(BaseModel):
    email: str | None = None
    password: str | None = None


async def _tidepool_status(session: SessionDep) -> dict[str, object]:
    cfg = await tidepool_config(session)
    return {
        "connected": all(cfg.values()),
        "fields": [{"key": k, "label": label, "set": bool(cfg[k])} for k, label in TIDEPOOL_FIELDS],
    }


@router.get("/tidepool")
async def tidepool_status(session: SessionDep, user: CurrentUser) -> dict[str, object]:
    return await _tidepool_status(session)


@router.put("/tidepool")
async def tidepool_save(
    body: TidepoolIn, session: SessionDep, user: CurrentUser
) -> dict[str, object]:
    for key, _ in TIDEPOOL_FIELDS:
        value = getattr(body, key)
        if value is not None:
            await set_setting(session, f"tidepool.{key}", value)
    await session.commit()
    return await _tidepool_status(session)


# --- OAuth connect flow (browser navigations — not bearer-authenticated) ---


@router.get("/google-health/authorize")
async def google_health_authorize(session: SessionDep) -> RedirectResponse:
    cfg = await google_health_config(session)
    if not cfg["client_id"]:
        return _back("missing_client")
    state = secrets.token_urlsafe(16)
    await set_setting(session, "google_health.oauth_state", state)
    await session.commit()
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": _settings.google_redirect_uri,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google-health/callback")
async def google_health_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error or not code:
        return _back("denied")
    if not state or state != await get_setting(session, "google_health.oauth_state"):
        return _back("bad_state")
    cfg = await google_health_config(session)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "redirect_uri": _settings.google_redirect_uri,
            },
        )
    if resp.status_code != 200:
        return _back("exchange_failed")
    refresh = resp.json().get("refresh_token")
    if refresh:
        await set_setting(session, "google_health.refresh_token", refresh)
        # Fresh token — clear the "needs reconnect" flag so the banner disappears.
        await set_setting(session, "google_health.auth_error", None)
    await set_setting(session, "google_health.oauth_state", None)
    await session.commit()
    return _back("connected" if refresh else "no_refresh_token")
