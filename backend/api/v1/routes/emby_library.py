import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from api.v1.schemas.emby import (
    EmbyAlbumDetail,
    EmbyArtistDetail,
    EmbyArtistPaginatedResponse,
    EmbyHubResponse,
    EmbyPaginatedResponse,
)
from core.exceptions import ExternalServiceError, ResourceNotFoundError
from infrastructure.msgspec_fastapi import MsgSpecRoute
from repositories.emby_repository import EmbyRepository
from services.emby_library_service import EmbyLibraryService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/emby", tags=["emby-library"])


def _get_emby_repository() -> EmbyRepository:
    from core.dependencies import get_emby_repository
    return get_emby_repository()


def _get_emby_library_service() -> EmbyLibraryService:
    from core.dependencies import get_emby_library_service
    return get_emby_library_service()


@router.get("/hub", response_model=EmbyHubResponse)
async def get_emby_hub(
    service: EmbyLibraryService = Depends(_get_emby_library_service),
) -> EmbyHubResponse:
    try:
        return await service.get_hub_data()
    except ExternalServiceError as exc:
        logger.error("Emby hub error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to communicate with Emby")


@router.get("/image/{item_id}")
async def get_emby_image(
    item_id: str,
    size: int = Query(default=500, ge=32, le=1200),
    repo: EmbyRepository = Depends(_get_emby_repository),
) -> Response:
    try:
        image_bytes, content_type = await repo.proxy_image(item_id, size)
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    except ExternalServiceError as exc:
        logger.warning("Emby image failed for %s: %s", item_id, exc)
        raise HTTPException(status_code=502, detail="Failed to fetch image")


@router.get("/albums", response_model=EmbyPaginatedResponse)
async def get_emby_albums(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="SortName"),
    sort_order: str = Query(default="Ascending"),
    genre: str | None = Query(default=None),
    year: int | None = Query(default=None),
    service: EmbyLibraryService = Depends(_get_emby_library_service),
) -> EmbyPaginatedResponse:
    try:
        return await service.get_albums(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
            genre=genre, year=year,
        )
    except ExternalServiceError as exc:
        logger.error("Emby albums error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to communicate with Emby")


@router.get("/albums/{album_id}", response_model=EmbyAlbumDetail)
async def get_emby_album_detail(
    album_id: str,
    service: EmbyLibraryService = Depends(_get_emby_library_service),
) -> EmbyAlbumDetail:
    try:
        return await service.get_album_detail(album_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Album not found")
    except ExternalServiceError as exc:
        logger.error("Emby album detail error for %s: %s", album_id, exc)
        raise HTTPException(status_code=502, detail="Failed to communicate with Emby")


@router.get("/artists", response_model=EmbyArtistPaginatedResponse)
async def get_emby_artists(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="SortName"),
    sort_order: str = Query(default="Ascending"),
    search: str = Query(default=""),
    service: EmbyLibraryService = Depends(_get_emby_library_service),
) -> EmbyArtistPaginatedResponse:
    try:
        return await service.get_artists(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=search
        )
    except ExternalServiceError as exc:
        logger.error("Emby artists error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to communicate with Emby")


@router.get("/artists/{artist_id}", response_model=EmbyArtistDetail)
async def get_emby_artist_detail(
    artist_id: str,
    service: EmbyLibraryService = Depends(_get_emby_library_service),
) -> EmbyArtistDetail:
    try:
        return await service.get_artist_detail(artist_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Artist not found")
    except ExternalServiceError as exc:
        logger.error("Emby artist detail error for %s: %s", artist_id, exc)
        raise HTTPException(status_code=502, detail="Failed to communicate with Emby")
