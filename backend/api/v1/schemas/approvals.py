from datetime import datetime

from infrastructure.msgspec_fastapi import AppStruct


class PendingApproval(AppStruct):
    musicbrainz_id: str
    artist_name: str
    album_title: str
    requested_at: datetime
    artist_mbid: str | None = None
    year: int | None = None
    cover_url: str | None = None
    requested_by: str | None = None
    monitor_artist: bool = False
    auto_download_artist: bool = False


class PendingApprovalsResponse(AppStruct):
    items: list[PendingApproval]
    count: int


class PendingApprovalCountResponse(AppStruct):
    count: int


class ApprovalActionResponse(AppStruct):
    success: bool
    message: str
