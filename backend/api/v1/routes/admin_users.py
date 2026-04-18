import logging
from datetime import datetime

import msgspec
from fastapi import APIRouter, Depends, HTTPException, Request

from api.v1.schemas.advanced_settings import PlaybackServiceToggles
from api.v1.schemas.approvals import (
    ApprovalActionResponse,
    PendingApproval,
    PendingApprovalCountResponse,
    PendingApprovalsResponse,
)
from api.v1.schemas.auth import (
    DefaultRequestSettings,
    UpdateUserRequest,
    UserSummary,
)
from core.dependencies import (
    get_auth_service,
    get_preferences_service,
    get_request_history_store,
    get_request_service,
    get_settings_service,
)
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from infrastructure.persistence.request_history import RequestHistoryStore
from services.auth_service import AuthService
from services.preferences_service import PreferencesService
from services.request_service import RequestService
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/admin", tags=["admin"])


def _require_admin(request: Request) -> dict:
    current_user = getattr(request.state, "current_user", None)
    if current_user is None or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/users", response_model=list[UserSummary])
async def list_users(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    _require_admin(request)
    return [UserSummary(**u) for u in auth.get_all_users()]


@router.put("/users/{username}", response_model=UserSummary)
async def update_user(
    username: str,
    request: Request,
    body: UpdateUserRequest = MsgSpecBody(UpdateUserRequest),
    auth: AuthService = Depends(get_auth_service),
):
    current = _require_admin(request)
    # Prevent demoting yourself
    if username.lower() == current["username"].lower() and body.role and body.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote your own account")
    updated = auth.update_user(
        username,
        role=body.role,
        can_request=body.can_request,
        request_quota=body.request_quota,
        quota_days=body.quota_days,
        clear_quota=body.clear_quota,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    users = auth.get_all_users()
    for u in users:
        if u["username"].lower() == username.lower():
            return UserSummary(**u)
    raise HTTPException(status_code=404, detail="User not found")


@router.delete("/users/{username}", status_code=204)
async def delete_user(
    username: str,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    current = _require_admin(request)
    if username.lower() == current["username"].lower():
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    deleted = auth.delete_user(username)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/settings/requests", response_model=DefaultRequestSettings)
async def get_request_settings(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    _require_admin(request)
    s = auth.get_default_request_settings()
    return DefaultRequestSettings(
        quota=s.get("quota"),
        quota_days=s.get("quota_days", 7),
        can_request=s.get("can_request", True),
    )


@router.put("/settings/requests", response_model=DefaultRequestSettings)
async def update_request_settings(
    request: Request,
    body: DefaultRequestSettings = MsgSpecBody(DefaultRequestSettings),
    auth: AuthService = Depends(get_auth_service),
):
    _require_admin(request)
    auth.set_default_request_settings(
        quota=body.quota,
        quota_days=body.quota_days,
        can_request=body.can_request,
    )
    return body


@router.get("/playback-services", response_model=PlaybackServiceToggles)
async def get_playback_services(
    request: Request,
    preferences_service: PreferencesService = Depends(get_preferences_service),
):
    _require_admin(request)
    return preferences_service.get_advanced_settings().playback_services


@router.put("/playback-services", response_model=PlaybackServiceToggles)
async def update_playback_services(
    request: Request,
    body: PlaybackServiceToggles = MsgSpecBody(PlaybackServiceToggles),
    preferences_service: PreferencesService = Depends(get_preferences_service),
    settings_service: SettingsService = Depends(get_settings_service),
):
    _require_admin(request)
    current = preferences_service.get_advanced_settings()
    updated = msgspec.structs.replace(current, playback_services=body)
    preferences_service.save_advanced_settings(updated)
    await settings_service.on_coverart_settings_changed()
    return preferences_service.get_advanced_settings().playback_services


@router.get("/requests/pending", response_model=PendingApprovalsResponse)
async def list_pending_approvals(
    request: Request,
    request_history: RequestHistoryStore = Depends(get_request_history_store),
):
    _require_admin(request)
    records = await request_history.async_get_pending_approvals()
    items = [
        PendingApproval(
            musicbrainz_id=r.musicbrainz_id,
            artist_name=r.artist_name,
            album_title=r.album_title,
            requested_at=datetime.fromisoformat(r.requested_at),
            artist_mbid=r.artist_mbid,
            year=r.year,
            cover_url=r.cover_url,
            requested_by=r.requested_by,
            monitor_artist=r.monitor_artist,
            auto_download_artist=r.auto_download_artist,
        )
        for r in records
    ]
    return PendingApprovalsResponse(items=items, count=len(items))


@router.get("/requests/pending/count", response_model=PendingApprovalCountResponse)
async def pending_approval_count(
    request: Request,
    request_history: RequestHistoryStore = Depends(get_request_history_store),
):
    _require_admin(request)
    count = await request_history.async_get_pending_approval_count()
    return PendingApprovalCountResponse(count=count)


@router.post("/requests/{musicbrainz_id}/approve", response_model=ApprovalActionResponse)
async def approve_request(
    musicbrainz_id: str,
    request: Request,
    request_history: RequestHistoryStore = Depends(get_request_history_store),
    request_service: RequestService = Depends(get_request_service),
):
    _require_admin(request)
    record = await request_history.async_get_record(musicbrainz_id)
    if not record or record.approval_status != "pending_approval":
        raise HTTPException(status_code=404, detail="Pending approval not found")

    # request_album will overwrite the row with approval_status='approved' (default)
    # and hand the album to Lidarr via the normal flow.
    await request_service.request_album(
        record.musicbrainz_id,
        artist=record.artist_name,
        album=record.album_title,
        year=record.year,
        artist_mbid=record.artist_mbid,
        monitor_artist=record.monitor_artist,
        auto_download_artist=record.auto_download_artist,
        requested_by=record.requested_by,
    )
    return ApprovalActionResponse(
        success=True,
        message=f"Approved request for {record.album_title}",
    )


@router.post("/requests/{musicbrainz_id}/reject", response_model=ApprovalActionResponse)
async def reject_request(
    musicbrainz_id: str,
    request: Request,
    request_history: RequestHistoryStore = Depends(get_request_history_store),
):
    _require_admin(request)
    record = await request_history.async_get_record(musicbrainz_id)
    if not record or record.approval_status != "pending_approval":
        raise HTTPException(status_code=404, detail="Pending approval not found")
    await request_history.async_set_approval_status(musicbrainz_id, "rejected")
    return ApprovalActionResponse(
        success=True,
        message=f"Rejected request for {record.album_title}",
    )
