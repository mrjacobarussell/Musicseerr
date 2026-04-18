from infrastructure.msgspec_fastapi import AppStruct


class EmbyTrackInfo(AppStruct):
    emby_id: str
    title: str
    track_number: int
    duration_seconds: float
    disc_number: int = 1
    album_name: str = ""
    artist_name: str = ""
    album_id: str = ""
    codec: str | None = None
    bitrate: int | None = None
    image_url: str | None = None


class EmbyAlbumSummary(AppStruct):
    emby_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None


class EmbyAlbumDetail(AppStruct):
    emby_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None
    tracks: list[EmbyTrackInfo] = []


class EmbyArtistSummary(AppStruct):
    emby_id: str
    name: str
    image_url: str | None = None
    album_count: int = 0


class EmbyArtistDetail(AppStruct):
    emby_id: str
    name: str
    image_url: str | None = None
    albums: list[EmbyAlbumSummary] = []


class EmbyLibraryStats(AppStruct):
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0


class EmbyHubResponse(AppStruct):
    recently_added: list[EmbyAlbumSummary] = []
    stats: EmbyLibraryStats = EmbyLibraryStats()


class EmbyPaginatedResponse(AppStruct):
    items: list[EmbyAlbumSummary]
    total: int
    limit: int
    offset: int


class EmbyArtistPaginatedResponse(AppStruct):
    items: list[EmbyArtistSummary]
    total: int
    limit: int
    offset: int
