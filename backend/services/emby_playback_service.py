import logging

import httpx
from fastapi.responses import Response, StreamingResponse

from core.exceptions import ExternalServiceError, PlaybackNotAllowedError
from infrastructure.constants import JELLYFIN_TICKS_PER_SECOND
from repositories.emby_repository import EmbyRepository
from repositories.navidrome_models import StreamProxyResult

logger = logging.getLogger(__name__)


class EmbyPlaybackService:
    def __init__(self, emby_repo: EmbyRepository):
        self._emby = emby_repo

    async def start_playback(self, item_id: str, play_session_id: str | None = None) -> str:
        resolved_session_id = play_session_id

        if not resolved_session_id:
            info = await self._emby.get_playback_info(item_id)

            error_code = info.get("ErrorCode")
            if error_code:
                raise PlaybackNotAllowedError(f"Emby playback not allowed: {error_code}")

            resolved_session_id = info.get("PlaySessionId")
            if not resolved_session_id:
                logger.warning(
                    "Emby returned null PlaySessionId for item %s, streaming without session reporting",
                    item_id,
                )
                return ""

        try:
            await self._emby.report_playback_start(item_id, resolved_session_id)
        except (httpx.HTTPError, ExternalServiceError) as exc:
            logger.error("Failed to report Emby playback start for %s: %s", item_id, exc)

        return resolved_session_id

    async def report_progress(
        self,
        item_id: str,
        play_session_id: str,
        position_seconds: float,
        is_paused: bool,
    ) -> None:
        if not play_session_id:
            return
        position_ticks = int(position_seconds * JELLYFIN_TICKS_PER_SECOND)
        try:
            await self._emby.report_playback_progress(
                item_id, play_session_id, position_ticks, is_paused
            )
        except (httpx.HTTPError, ExternalServiceError) as exc:
            logger.warning("Emby progress report failed for %s: %s", item_id, exc)

    async def stop_playback(
        self,
        item_id: str,
        play_session_id: str,
        position_seconds: float,
    ) -> None:
        if not play_session_id:
            return
        position_ticks = int(position_seconds * JELLYFIN_TICKS_PER_SECOND)
        try:
            await self._emby.report_playback_stopped(item_id, play_session_id, position_ticks)
        except (httpx.HTTPError, ExternalServiceError) as exc:
            logger.warning("Emby stop report failed for %s: %s", item_id, exc)

    async def proxy_head(self, item_id: str) -> Response:
        result: StreamProxyResult = await self._emby.proxy_head_stream(item_id)
        return Response(status_code=200, headers=result.headers)

    async def proxy_stream(
        self, item_id: str, range_header: str | None = None
    ) -> StreamingResponse:
        result: StreamProxyResult = await self._emby.proxy_get_stream(
            item_id, range_header=range_header
        )
        return StreamingResponse(
            content=result.body_chunks,
            status_code=result.status_code,
            headers=result.headers,
            media_type=result.media_type,
        )
