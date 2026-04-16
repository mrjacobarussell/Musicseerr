import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.v1.schemas.auth import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthSetupRequest,
    AuthStatusResponse,
    AuthSettingsResponse,
    EmbyLoginRequest,
    PlexLoginRequest,
    SsoPromoteSettings,
)
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from repositories.emby_repository import emby_authenticate
from repositories.plex_repository import PlexRepository
from services.auth_service import AuthService
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    from core.dependencies import get_auth_service as _get
    return _get()


def get_plex_repository() -> PlexRepository:
    from core.dependencies import get_plex_repository as _get
    return _get()


def get_preferences_service() -> PreferencesService:
    from core.dependencies import get_preferences_service as _get
    return _get()


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    auth: AuthService = Depends(get_auth_service),
    preferences: PreferencesService = Depends(get_preferences_service),
    plex: PlexRepository = Depends(get_plex_repository),
):
    emby = preferences.get_emby_auth_settings()
    return AuthStatusResponse(
        auth_enabled=auth.is_auth_enabled(),
        setup_required=auth.setup_required(),
        emby_enabled=emby.enabled and bool(emby.emby_url),
        plex_enabled=plex.is_configured(),
    )


@router.post("/setup", response_model=AuthLoginResponse)
async def setup(
    body: AuthSetupRequest = MsgSpecBody(AuthSetupRequest),
    auth: AuthService = Depends(get_auth_service),
):
    """Create the first admin account. Only works when no users exist yet."""
    if auth.user_count() > 0:
        raise HTTPException(status_code=403, detail="Setup already complete")
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    try:
        auth.create_user(body.username, body.password, role="admin")
        # Auto-enable auth on first setup
        auth.set_auth_enabled(True)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    token = auth.create_token(body.username, "admin")
    return AuthLoginResponse(token=token, username=body.username, role="admin", is_primary=True)


@router.post("/login", response_model=AuthLoginResponse)
async def login(
    body: AuthLoginRequest = MsgSpecBody(AuthLoginRequest),
    auth: AuthService = Depends(get_auth_service),
):
    user = auth.verify_password(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = auth.create_token(user["username"], user["role"])
    return AuthLoginResponse(
        token=token,
        username=user["username"],
        role=user["role"],
        is_primary=auth.is_primary_admin(user["username"]),
    )


@router.get("/settings", response_model=AuthSettingsResponse)
async def get_auth_settings(auth: AuthService = Depends(get_auth_service)):
    return AuthSettingsResponse(enabled=auth.is_auth_enabled())


@router.put("/settings", response_model=AuthSettingsResponse)
async def update_auth_settings(
    body: AuthSettingsResponse = MsgSpecBody(AuthSettingsResponse),
    auth: AuthService = Depends(get_auth_service),
):
    if body.enabled and auth.user_count() == 0:
        raise HTTPException(
            status_code=400,
            detail="NO_USERS",
        )
    auth.set_auth_enabled(body.enabled)
    return AuthSettingsResponse(enabled=auth.is_auth_enabled())


@router.post("/emby/login", response_model=AuthLoginResponse)
async def emby_login(
    body: EmbyLoginRequest = MsgSpecBody(EmbyLoginRequest),
    auth: AuthService = Depends(get_auth_service),
    preferences: PreferencesService = Depends(get_preferences_service),
):
    """Sign in with an Emby username and password."""
    settings = preferences.get_emby_auth_settings()
    if not settings.enabled or not settings.emby_url:
        raise HTTPException(status_code=400, detail="Emby authentication is not configured")

    user_info = await emby_authenticate(settings.emby_url, body.username, body.password)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid Emby credentials")

    user = auth.create_or_get_emby_user(
        user_info["username"],
        is_sso_admin=bool(user_info.get("is_admin", False)),
    )
    token = auth.create_token(user["username"], user["role"])
    return AuthLoginResponse(token=token, username=user["username"], role=user["role"])


@router.post("/plex/login", response_model=AuthLoginResponse)
async def plex_login(
    body: PlexLoginRequest = MsgSpecBody(PlexLoginRequest),
    auth: AuthService = Depends(get_auth_service),
    plex: PlexRepository = Depends(get_plex_repository),
):
    """Exchange a Plex user token for a MusicSeerr session token."""
    user_info = await plex.get_plex_user_info(body.plex_token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid Plex token")

    plex_username = user_info.get("username") or user_info.get("friendlyName") or user_info.get("title")
    if not plex_username:
        raise HTTPException(status_code=401, detail="Could not retrieve Plex username")

    ok, message = await plex.verify_user_server_access(body.plex_token)
    if not ok:
        raise HTTPException(status_code=403, detail=message)

    is_owner = await plex.is_server_owner(body.plex_token)
    user = auth.create_or_get_plex_user(plex_username, is_sso_admin=is_owner)
    token = auth.create_token(user["username"], user["role"])
    return AuthLoginResponse(token=token, username=user["username"], role=user["role"])


@router.get("/sso-promote", response_model=SsoPromoteSettings)
async def get_sso_promote(request: Request, auth: AuthService = Depends(get_auth_service)):
    current = getattr(request.state, "current_user", None)
    if not current or not auth.is_primary_admin(current["username"]):
        raise HTTPException(status_code=403, detail="Only the primary admin can manage this setting")
    return SsoPromoteSettings(enabled=auth.get_sso_admin_promote())


@router.put("/sso-promote", response_model=SsoPromoteSettings)
async def set_sso_promote(
    body: SsoPromoteSettings = MsgSpecBody(SsoPromoteSettings),
    request: Request = None,
    auth: AuthService = Depends(get_auth_service),
):
    current = getattr(request.state, "current_user", None)
    if not current or not auth.is_primary_admin(current["username"]):
        raise HTTPException(status_code=403, detail="Only the primary admin can manage this setting")
    auth.set_sso_admin_promote(body.enabled)
    return SsoPromoteSettings(enabled=auth.get_sso_admin_promote())
