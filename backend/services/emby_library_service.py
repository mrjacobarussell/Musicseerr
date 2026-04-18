import logging
from typing import Any

from api.v1.schemas.emby import (
    EmbyAlbumDetail,
    EmbyAlbumSummary,
    EmbyArtistDetail,
    EmbyArtistPaginatedResponse,
    EmbyArtistSummary,
    EmbyHubResponse,
    EmbyLibraryStats,
    EmbyPaginatedResponse,
    EmbyTrackInfo,
)
from core.exceptions import ExternalServiceError
from repositories.emby_repository import EmbyRepository

logger = logging.getLogger(__name__)

_TICKS_PER_SECOND = 10_000_000


def _duration_seconds(ticks: int | None) -> float:
    if not ticks:
        return 0.0
    return ticks / _TICKS_PER_SECOND


def _image_url(item_id: str) -> str:
    return f"/api/v1/emby/image/{item_id}"


def _item_to_album_summary(item: dict[str, Any]) -> EmbyAlbumSummary:
    item_id = item.get("Id", "")
    artist_items = item.get("ArtistItems") or item.get("AlbumArtists") or []
    artist_name = ""
    if artist_items:
        artist_name = artist_items[0].get("Name", "") if isinstance(artist_items[0], dict) else ""
    if not artist_name:
        artist_name = item.get("AlbumArtist") or item.get("ArtistName") or ""

    return EmbyAlbumSummary(
        emby_id=item_id,
        name=item.get("Name", ""),
        artist_name=artist_name,
        year=item.get("ProductionYear"),
        track_count=item.get("ChildCount") or item.get("SongCount") or 0,
        image_url=_image_url(item_id) if item_id else None,
    )


def _item_to_track(item: dict[str, Any]) -> EmbyTrackInfo:
    item_id = item.get("Id", "")
    media_streams = item.get("MediaStreams") or []
    codec = None
    bitrate = None
    for stream in media_streams:
        if stream.get("Type") == "Audio":
            codec = stream.get("Codec")
            bitrate = stream.get("BitRate")
            break

    artist_items = item.get("ArtistItems") or []
    artist_name = ""
    if artist_items:
        artist_name = artist_items[0].get("Name", "") if isinstance(artist_items[0], dict) else ""
    if not artist_name:
        artist_name = item.get("ArtistName") or item.get("AlbumArtist") or ""

    return EmbyTrackInfo(
        emby_id=item_id,
        title=item.get("Name", ""),
        track_number=item.get("IndexNumber") or 0,
        disc_number=item.get("ParentIndexNumber") or 1,
        duration_seconds=_duration_seconds(item.get("RunTimeTicks")),
        album_name=item.get("Album", ""),
        artist_name=artist_name,
        album_id=item.get("AlbumId", ""),
        codec=codec,
        bitrate=bitrate,
        image_url=_image_url(item_id) if item_id else None,
    )


def _item_to_artist_summary(item: dict[str, Any]) -> EmbyArtistSummary:
    item_id = item.get("Id", "")
    return EmbyArtistSummary(
        emby_id=item_id,
        name=item.get("Name", ""),
        image_url=_image_url(item_id) if item_id else None,
        album_count=item.get("AlbumCount") or 0,
    )


class EmbyLibraryService:
    def __init__(self, repo: EmbyRepository):
        self._repo = repo

    async def get_hub_data(self) -> EmbyHubResponse:
        if not self._repo.is_configured():
            raise ExternalServiceError("Emby not configured")
        recently_added_raw, stats_raw = await _gather_two(
            self._repo.get_recently_added(limit=20),
            self._repo.get_library_stats(),
        )
        recently_added = [_item_to_album_summary(i) for i in recently_added_raw]
        stats = EmbyLibraryStats(
            total_albums=stats_raw.get("total_albums", 0),
            total_artists=stats_raw.get("total_artists", 0),
            total_tracks=stats_raw.get("total_tracks", 0),
        )
        return EmbyHubResponse(recently_added=recently_added, stats=stats)

    async def get_albums(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "SortName",
        sort_order: str = "Ascending",
        genre: str | None = None,
        year: int | None = None,
    ) -> EmbyPaginatedResponse:
        if not self._repo.is_configured():
            raise ExternalServiceError("Emby not configured")
        items_raw, total = await self._repo.get_albums(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
            genre=genre, year=year,
        )
        return EmbyPaginatedResponse(
            items=[_item_to_album_summary(i) for i in items_raw],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_album_detail(self, album_id: str) -> EmbyAlbumDetail:
        if not self._repo.is_configured():
            raise ExternalServiceError("Emby not configured")
        album_raw, tracks_raw = await _gather_two(
            self._repo.get_album_detail(album_id),
            self._repo.get_album_tracks(album_id),
        )
        if not album_raw:
            from core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Emby album not found: {album_id}")

        artist_items = album_raw.get("ArtistItems") or album_raw.get("AlbumArtists") or []
        artist_name = ""
        if artist_items:
            artist_name = (
                artist_items[0].get("Name", "") if isinstance(artist_items[0], dict) else ""
            )
        if not artist_name:
            artist_name = album_raw.get("AlbumArtist") or album_raw.get("ArtistName") or ""

        tracks = [_item_to_track(t) for t in tracks_raw]
        return EmbyAlbumDetail(
            emby_id=album_id,
            name=album_raw.get("Name", ""),
            artist_name=artist_name,
            year=album_raw.get("ProductionYear"),
            track_count=len(tracks),
            image_url=_image_url(album_id),
            tracks=tracks,
        )

    async def get_artists(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "SortName",
        sort_order: str = "Ascending",
        search: str = "",
    ) -> EmbyArtistPaginatedResponse:
        if not self._repo.is_configured():
            raise ExternalServiceError("Emby not configured")
        items_raw, total = await self._repo.get_artists(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=search
        )
        return EmbyArtistPaginatedResponse(
            items=[_item_to_artist_summary(i) for i in items_raw],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_artist_detail(self, artist_id: str) -> EmbyArtistDetail:
        if not self._repo.is_configured():
            raise ExternalServiceError("Emby not configured")
        artist_raw, albums_raw = await _gather_two(
            self._repo.get_artist_detail(artist_id),
            self._repo.get_artist_albums(artist_id),
        )
        if not artist_raw:
            from core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Emby artist not found: {artist_id}")

        albums = [_item_to_album_summary(a) for a in albums_raw]
        return EmbyArtistDetail(
            emby_id=artist_id,
            name=artist_raw.get("Name", ""),
            image_url=_image_url(artist_id),
            albums=albums,
        )


async def _gather_two(coro1, coro2):
    import asyncio
    return await asyncio.gather(coro1, coro2)
