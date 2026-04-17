import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.v1.schemas.settings import EmbyAuthSettings, EmbyVerifyResponse, EmbySyncResult
from api.v1.schemas.settings import LASTFM_SECRET_MASK, _is_masked, _mask_secret
from core.dependencies import get_preferences_service, get_auth_service
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from repositories.emby_repository import emby_verify_server, emby_get_all_users
from services.auth_service import AuthService
from services.preferences_service import PreferencesService
import msgspec

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/emby", tags=["emby-auth"])


def _require_admin(request: Request) -> None:
    current_user = getattr(request.state, "current_user", None)
    if current_user is None or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _mask_settings(settings: EmbyAuthSettings) -> EmbyAuthSettings:
    """Return a copy with the API key masked for GET responses."""
    if settings.emby_api_key:
        return msgspec.structs.replace(settings, emby_api_key=_mask_secret(settings.emby_api_key))
    return settings


@router.get("/auth/settings", response_model=EmbyAuthSettings)
async def get_emby_settings(
    request: Request,
    preferences: PreferencesService = Depends(get_preferences_service),
):
    _require_admin(request)
    return _mask_settings(preferences.get_emby_auth_settings())


@router.put("/auth/settings", response_model=EmbyAuthSettings)
async def save_emby_settings(
    request: Request,
    body: EmbyAuthSettings = MsgSpecBody(EmbyAuthSettings),
    preferences: PreferencesService = Depends(get_preferences_service),
):
    _require_admin(request)
    if _is_masked(body.emby_api_key):
        current = preferences.get_emby_auth_settings()
        body = msgspec.structs.replace(body, emby_api_key=current.emby_api_key)
    preferences.save_emby_auth_settings(body)
    return _mask_settings(preferences.get_emby_auth_settings())


@router.post("/auth/verify", response_model=EmbyVerifyResponse)
async def verify_emby_server(
    request: Request,
    body: EmbyAuthSettings = MsgSpecBody(EmbyAuthSettings),
):
    _require_admin(request)
    if not body.emby_url:
        return EmbyVerifyResponse(success=False, message="No server URL provided")
    ok, message = await emby_verify_server(body.emby_url)
    return EmbyVerifyResponse(success=ok, message=message)


@router.post("/auth/sync-users", response_model=EmbySyncResult)
async def sync_emby_users(
    request: Request,
    preferences: PreferencesService = Depends(get_preferences_service),
    auth: AuthService = Depends(get_auth_service),
):
    """Import all Emby users as Musicseerr accounts (requires an Emby API key)."""
    _require_admin(request)
    settings = preferences.get_emby_auth_settings()
    if not settings.enabled or not settings.emby_url:
        raise HTTPException(status_code=400, detail="Emby authentication is not configured")
    if not settings.emby_api_key:
        raise HTTPException(status_code=400, detail="An Emby API key is required to sync users")

    emby_users = await emby_get_all_users(settings.emby_url, settings.emby_api_key)
    if not emby_users:
        raise HTTPException(status_code=502, detail="Could not fetch users from Emby — check the API key and server URL")

    existing_usernames = {
        u["username"].lower()
        for u in auth.get_all_users()
        if u.get("auth_provider") == "emby"
    }

    created: list[str] = []
    skipped: list[str] = []
    for eu in emby_users:
        name: str = eu.get("Name", "").strip()
        if not name:
            continue
        if name.lower() in existing_usernames:
            skipped.append(name)
        else:
            is_admin = bool(eu.get("Policy", {}).get("IsAdministrator", False))
            auth.create_or_get_emby_user(name, is_sso_admin=is_admin)
            created.append(name)

    return EmbySyncResult(created=created, skipped=skipped)
