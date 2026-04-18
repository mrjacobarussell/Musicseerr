"""Emby repository — authentication helpers and full media-source repository."""
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from infrastructure.resilience.retry import with_retry, CircuitBreaker
from core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_DEVICE_AUTH = (
    'MediaBrowser Client="Musicseerr", Device="Server", '
    'DeviceId="musicseerr-server", Version="1.0"'
)


async def emby_authenticate(url: str, username: str, password: str) -> dict | None:
    """Validate Emby credentials and return user info, or None on failure.

    Returns dict with keys: username, user_id, is_admin.
    """
    base = url.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            response = await client.post(
                f"{base}/Users/AuthenticateByName",
                json={"Username": username, "Pw": password},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Emby-Authorization": _DEVICE_AUTH,
                },
            )
            if response.status_code in (401, 403):
                return None
            if response.status_code != 200:
                logger.warning("Emby auth returned status %d", response.status_code)
                return None
            data = response.json()
            user_obj = data.get("User", {})
            return {
                "username": user_obj.get("Name", username),
                "user_id": user_obj.get("Id", ""),
                "is_admin": user_obj.get("Policy", {}).get("IsAdministrator", False),
            }
        except httpx.TimeoutException:
            logger.warning("Emby auth timed out for user %s", username)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Emby auth error: %s", exc)
            return None


async def emby_get_all_users(url: str, api_key: str) -> list[dict]:
    """Fetch all users from the Emby server using an admin API key.

    Returns a list of Emby user objects, each with at least 'Name' and 'Policy'.
    Returns an empty list on error.
    """
    base = url.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            response = await client.get(
                f"{base}/Users",
                headers={
                    "Accept": "application/json",
                    "X-Emby-Token": api_key,
                },
            )
            if response.status_code == 200:
                return response.json()
            logger.warning("Emby get users returned status %d", response.status_code)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Emby get users error: %s", exc)
            return []


async def emby_verify_server(url: str) -> tuple[bool, str]:
    """Check whether the Emby server at *url* is reachable.

    Returns (True, server_name) or (False, error_message).
    """
    base = url.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            response = await client.get(
                f"{base}/System/Info/Public",
                headers={"Accept": "application/json"},
            )
            if response.status_code == 200:
                data = response.json()
                name = data.get("ServerName") or data.get("ProductName") or "Emby"
                return True, name
            return False, f"Server returned status {response.status_code}"
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except Exception as exc:  # noqa: BLE001
            return False, f"Could not reach server: {exc}"


# ---------------------------------------------------------------------------
# Class-based repository for library access (music source integration)
# ---------------------------------------------------------------------------

_emby_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="emby",
)

_PROXY_FORWARD_HEADERS = {"Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"}
_STREAM_CHUNK_SIZE = 64 * 1024
_RANGE_RE = re.compile(r"^bytes=\d*-\d*(,\s*\d*-\d*)*$")


class EmbyRepository:
    """Full media-source repository for Emby library access and streaming."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str = "",
        api_key: str = "",
        user_id: str = "",
    ):
        self._client = http_client
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._user_id = user_id

    def configure(self, base_url: str, api_key: str, user_id: str = "") -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._user_id = user_id

    def is_configured(self) -> bool:
        return bool(self._base_url and self._api_key)

    def _get_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Emby-Token": self._api_key,
        }

    @with_retry(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        circuit_breaker=_emby_circuit_breaker,
        retriable_exceptions=(httpx.HTTPError, ExternalServiceError),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        if not self._base_url or not self._api_key:
            raise ExternalServiceError("Emby not configured")

        url = f"{self._base_url}{endpoint}"
        try:
            response = await self._client.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
                timeout=15.0,
            )
            if response.status_code == 401:
                raise ExternalServiceError("Emby authentication failed — check API key")
            if response.status_code == 404:
                return None
            if response.status_code not in (200, 204):
                raise ExternalServiceError(
                    f"Emby {method} failed ({response.status_code})", response.text
                )
            if response.status_code == 204:
                return None
            try:
                return response.json()
            except Exception:  # noqa: BLE001
                return None
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Emby request failed: {exc}")

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", endpoint, params=params)

    async def _post(
        self, endpoint: str, json_data: dict[str, Any] | None = None
    ) -> Any:
        return await self._request("POST", endpoint, json_data=json_data)

    async def validate_connection(self) -> tuple[bool, str]:
        if not self._base_url or not self._api_key:
            return False, "Emby URL or API key not configured"
        try:
            url = f"{self._base_url}/System/Info"
            response = await self._client.request(
                "GET", url, headers=self._get_headers(), timeout=10.0
            )
            if response.status_code == 401:
                return False, "Authentication failed — check API key"
            if response.status_code != 200:
                return False, f"Connection failed (HTTP {response.status_code})"
            data = response.json()
            name = data.get("ServerName", "Unknown")
            version = data.get("Version", "Unknown")
            return True, f"Connected to {name} (v{version})"
        except httpx.TimeoutException:
            return False, "Connection timed out — check URL"
        except httpx.ConnectError:
            return False, "Could not connect — check URL and ensure server is running"
        except Exception as exc:  # noqa: BLE001
            return False, f"Connection failed: {exc}"

    async def get_recently_added(self, limit: int = 20) -> list[dict[str, Any]]:
        uid = self._user_id
        if not uid:
            return []
        params: dict[str, Any] = {
            "userId": uid,
            "includeItemTypes": "MusicAlbum",
            "limit": limit,
            "enableUserData": "true",
        }
        try:
            result = await self._get("/Items/Latest", params=params)
            return result if isinstance(result, list) else []
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby get_recently_added failed: %s", exc)
            return []

    async def get_albums(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "SortName",
        sort_order: str = "Ascending",
        genre: str | None = None,
        year: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        uid = self._user_id
        params: dict[str, Any] = {
            "includeItemTypes": "MusicAlbum",
            "recursive": "true",
            "sortBy": sort_by,
            "sortOrder": sort_order,
            "limit": limit,
            "startIndex": offset,
            "enableUserData": "true",
            "Fields": "ProviderIds,ChildCount",
        }
        if uid:
            params["userId"] = uid
        if genre:
            params["genres"] = genre
        if year:
            params["years"] = str(year)
        try:
            result = await self._get("/Items", params=params)
            if not result:
                return [], 0
            items = result.get("Items", [])
            total = result.get("TotalRecordCount", len(items))
            return items, total
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby get_albums failed: %s", exc)
            return [], 0

    async def get_album_detail(self, album_id: str) -> dict[str, Any] | None:
        uid = self._user_id
        params: dict[str, Any] = {"Fields": "ProviderIds,ChildCount"}
        if uid:
            params["userId"] = uid
        try:
            return await self._get(f"/Items/{album_id}", params=params)
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby get_album_detail failed for %s: %s", album_id, exc)
            return None

    async def get_album_tracks(self, album_id: str) -> list[dict[str, Any]]:
        uid = self._user_id
        params: dict[str, Any] = {
            "albumIds": album_id,
            "includeItemTypes": "Audio",
            "sortBy": "IndexNumber",
            "sortOrder": "Ascending",
            "recursive": "true",
            "enableUserData": "true",
            "Fields": "ProviderIds,MediaStreams",
        }
        if uid:
            params["userId"] = uid
        try:
            result = await self._get("/Items", params=params)
            return result.get("Items", []) if result else []
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby get_album_tracks failed for %s: %s", album_id, exc)
            return []

    async def get_artists(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "SortName",
        sort_order: str = "Ascending",
        search: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        params: dict[str, Any] = {
            "limit": limit,
            "startIndex": offset,
            "sortBy": sort_by,
            "sortOrder": sort_order,
            "enableUserData": "true",
            "Fields": "ProviderIds",
        }
        if self._user_id:
            params["userId"] = self._user_id
        if search:
            params["searchTerm"] = search
        try:
            result = await self._get("/Artists", params=params)
            if not result:
                return [], 0
            items = result.get("Items", [])
            total = result.get("TotalRecordCount", len(items))
            return items, total
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby get_artists failed: %s", exc)
            return [], 0

    async def get_artist_detail(self, artist_id: str) -> dict[str, Any] | None:
        uid = self._user_id
        params: dict[str, Any] = {"Fields": "ProviderIds"}
        if uid:
            params["userId"] = uid
        try:
            return await self._get(f"/Items/{artist_id}", params=params)
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby get_artist_detail failed for %s: %s", artist_id, exc)
            return None

    async def get_artist_albums(self, artist_id: str) -> list[dict[str, Any]]:
        uid = self._user_id
        params: dict[str, Any] = {
            "artistIds": artist_id,
            "includeItemTypes": "MusicAlbum",
            "recursive": "true",
            "sortBy": "PremiereDate",
            "sortOrder": "Descending",
            "Fields": "ProviderIds,ChildCount",
        }
        if uid:
            params["userId"] = uid
        try:
            result = await self._get("/Items", params=params)
            return result.get("Items", []) if result else []
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby get_artist_albums failed for %s: %s", artist_id, exc)
            return []

    async def get_library_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {"total_albums": 0, "total_artists": 0, "total_tracks": 0}
        uid = self._user_id
        for item_type, key in [
            ("MusicAlbum", "total_albums"),
            ("MusicArtist", "total_artists"),
            ("Audio", "total_tracks"),
        ]:
            params: dict[str, Any] = {"includeItemTypes": item_type, "recursive": "true", "limit": 0}
            if uid:
                params["userId"] = uid
            try:
                result = await self._get("/Items", params=params)
                if result:
                    stats[key] = result.get("TotalRecordCount", 0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Emby stats failed for %s: %s", item_type, exc)
        return stats

    async def search(self, query: str) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "searchTerm": query,
            "includeItemTypes": "MusicAlbum,Audio,MusicArtist",
            "limit": 50,
            "Fields": "ProviderIds",
        }
        if self._user_id:
            params["userId"] = self._user_id
        try:
            result = await self._get("/Search/Hints", params=params)
            return result.get("SearchHints", []) if result else []
        except Exception as exc:  # noqa: BLE001
            logger.error("Emby search failed for %r: %s", query, exc)
            return []

    async def proxy_image(self, item_id: str, size: int = 500) -> tuple[bytes, str]:
        if not self._base_url or not self._api_key:
            raise ExternalServiceError("Emby not configured")
        url = f"{self._base_url}/Items/{item_id}/Images/Primary"
        params: dict[str, Any] = {"maxWidth": size, "maxHeight": size, "quality": 90}
        try:
            response = await self._client.get(
                url,
                params=params,
                headers={"X-Emby-Token": self._api_key},
                timeout=15.0,
            )
        except httpx.TimeoutException:
            raise ExternalServiceError("Emby image request timed out")
        except httpx.HTTPError:
            raise ExternalServiceError("Emby image request failed")
        if response.status_code != 200:
            raise ExternalServiceError(f"Emby image request failed ({response.status_code})")
        content_type = response.headers.get("content-type", "image/jpeg")
        return response.content, content_type

    async def get_playback_info(self, item_id: str) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self._user_id:
            params["userId"] = self._user_id
        result = await self._get(f"/Items/{item_id}/PlaybackInfo", params=params)
        if not result:
            from core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Playback info not found for {item_id}")
        return result

    async def get_playback_url(self, item_id: str) -> tuple[str, str]:
        """Return (stream_url, play_session_id). Prefers direct play."""
        from infrastructure.constants import BROWSER_AUDIO_DEVICE_PROFILE
        params: dict[str, Any] = {}
        if self._user_id:
            params["userId"] = self._user_id

        result = await self._request(
            "POST",
            f"/Items/{item_id}/PlaybackInfo",
            params=params,
            json_data={"DeviceProfile": BROWSER_AUDIO_DEVICE_PROFILE},
        )
        if not result:
            from core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Playback info not found for {item_id}")

        error_code = result.get("ErrorCode")
        if error_code:
            from core.exceptions import PlaybackNotAllowedError
            raise PlaybackNotAllowedError(f"Emby playback not allowed: {error_code}")

        play_session_id = result.get("PlaySessionId", "")
        media_sources = result.get("MediaSources") or []
        if not media_sources:
            raise ExternalServiceError(f"Playback info missing media sources for {item_id}")

        primary = media_sources[0]
        if primary.get("SupportsDirectPlay") or primary.get("SupportsDirectStream"):
            url = f"{self._base_url}/Audio/{item_id}/stream?static=true"
        else:
            transcoding_url = primary.get("TranscodingUrl", "")
            if not transcoding_url:
                raise ExternalServiceError(f"No playable stream for {item_id}")
            url = (
                transcoding_url
                if transcoding_url.startswith(("http://", "https://"))
                else f"{self._base_url}{transcoding_url}"
            )
        return url, play_session_id

    async def report_playback_start(self, item_id: str, play_session_id: str) -> None:
        body: dict[str, Any] = {
            "ItemId": item_id,
            "PlaySessionId": play_session_id,
            "CanSeek": True,
            "PlayMethod": "DirectPlay",
        }
        await self._post("/Sessions/Playing", json_data=body)

    async def report_playback_progress(
        self, item_id: str, play_session_id: str, position_ticks: int, is_paused: bool
    ) -> None:
        body: dict[str, Any] = {
            "ItemId": item_id,
            "PlaySessionId": play_session_id,
            "PositionTicks": position_ticks,
            "IsPaused": is_paused,
            "CanSeek": True,
        }
        await self._post("/Sessions/Playing/Progress", json_data=body)

    async def report_playback_stopped(
        self, item_id: str, play_session_id: str, position_ticks: int
    ) -> None:
        body: dict[str, Any] = {
            "ItemId": item_id,
            "PlaySessionId": play_session_id,
            "PositionTicks": position_ticks,
        }
        await self._post("/Sessions/Playing/Stopped", json_data=body)

    def _validate_stream_url(self, url: str) -> None:
        from urllib.parse import urlparse
        expected = urlparse(self._base_url)
        actual = urlparse(url)
        if (actual.scheme, actual.hostname, actual.port) != (
            expected.scheme, expected.hostname, expected.port
        ):
            raise ExternalServiceError(
                "Resolved playback URL does not match configured Emby origin"
            )

    async def proxy_head_stream(self, item_id: str) -> "StreamProxyResult":
        from repositories.navidrome_models import StreamProxyResult
        url, _ = await self.get_playback_url(item_id)
        self._validate_stream_url(url)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=10, write=10, pool=10)
        ) as client:
            try:
                resp = await client.head(url, headers={"X-Emby-Token": self._api_key})
            except httpx.HTTPError:
                raise ExternalServiceError("Failed to reach Emby for stream")
        if resp.status_code >= 400:
            raise ExternalServiceError(f"Emby HEAD returned {resp.status_code}")
        headers: dict[str, str] = {}
        for h in _PROXY_FORWARD_HEADERS:
            v = resp.headers.get(h)
            if v:
                headers[h] = v
        return StreamProxyResult(
            status_code=resp.status_code,
            headers=headers,
            media_type=headers.get("Content-Type", "audio/mpeg"),
        )

    async def proxy_get_stream(
        self, item_id: str, range_header: str | None = None
    ) -> "StreamProxyResult":
        from repositories.navidrome_models import StreamProxyResult
        url, _ = await self.get_playback_url(item_id)
        self._validate_stream_url(url)

        upstream_headers: dict[str, str] = {"X-Emby-Token": self._api_key}
        if range_header:
            if not _RANGE_RE.match(range_header):
                raise ExternalServiceError("416 Range not satisfiable")
            upstream_headers["Range"] = range_header

        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10)
        )
        upstream_resp = None
        try:
            try:
                upstream_resp = await client.send(
                    client.build_request("GET", url, headers=upstream_headers),
                    stream=True,
                )
            except httpx.HTTPError as exc:
                raise ExternalServiceError(f"Failed to connect to Emby for stream: {exc}")

            if upstream_resp.status_code == 416:
                raise ExternalServiceError("416 Range not satisfiable")
            if upstream_resp.status_code >= 400:
                raise ExternalServiceError("Emby returned an error")

            resp_headers: dict[str, str] = {}
            for h in _PROXY_FORWARD_HEADERS:
                v = upstream_resp.headers.get(h)
                if v:
                    resp_headers[h] = v

            status_code = 206 if upstream_resp.status_code == 206 else 200

            async def _stream_body() -> AsyncIterator[bytes]:
                try:
                    async for chunk in upstream_resp.aiter_bytes(chunk_size=_STREAM_CHUNK_SIZE):
                        yield chunk
                finally:
                    await upstream_resp.aclose()
                    await client.aclose()

            return StreamProxyResult(
                status_code=status_code,
                headers=resp_headers,
                media_type=resp_headers.get("Content-Type", "audio/mpeg"),
                body_chunks=_stream_body(),
            )
        except Exception:  # noqa: BLE001
            if upstream_resp:
                await upstream_resp.aclose()
            await client.aclose()
            raise
