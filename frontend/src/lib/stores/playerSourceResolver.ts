import { browser } from '$app/environment';
import { API } from '$lib/constants';
import type { NowPlaying, QueueItem, SourceType } from '$lib/player/types';

/**
 * Append the stored JWT as ?token= so the browser <audio> element can authenticate.
 * The audio element cannot set custom headers, so the backend also accepts the token
 * as a query parameter on /api/v1/stream/ paths.
 */
function withAuthToken(url: string): string {
	if (!browser) return url;
	const token = localStorage.getItem('musicseerr_token');
	if (!token) return url;
	const sep = url.includes('?') ? '&' : '?';
	return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export function resolveSourceUrl(item: QueueItem): string | undefined {
	switch (item.sourceType) {
		case 'youtube':
			return item.streamUrl;
		case 'local':
			return withAuthToken(item.streamUrl ?? API.stream.local(item.trackSourceId));
		case 'navidrome':
			return withAuthToken(item.streamUrl ?? API.stream.navidrome(item.trackSourceId));
		case 'jellyfin':
			return withAuthToken(API.stream.jellyfin(item.trackSourceId));
		case 'plex':
			return withAuthToken(item.streamUrl ?? API.stream.plex(item.trackSourceId));
	}
}

export function buildPrefetchUrl(item: QueueItem): string | null {
	switch (item.sourceType) {
		case 'youtube':
			return null;
		case 'jellyfin':
			return withAuthToken(API.stream.jellyfin(item.trackSourceId));
		case 'navidrome':
			return withAuthToken(API.stream.navidrome(item.trackSourceId));
		case 'plex':
			return withAuthToken(API.stream.plex(item.trackSourceId));
		case 'local':
			return withAuthToken(API.stream.local(item.trackSourceId));
		default:
			return item.streamUrl ?? null;
	}
}

export function buildStreamUrlForSource(
	sourceType: SourceType,
	trackSourceId: string
): string | undefined {
	switch (sourceType) {
		case 'local':
			return withAuthToken(API.stream.local(trackSourceId));
		case 'navidrome':
			return withAuthToken(API.stream.navidrome(trackSourceId));
		case 'jellyfin':
			return withAuthToken(API.stream.jellyfin(trackSourceId));
		case 'plex':
			return withAuthToken(API.stream.plex(trackSourceId));
		default:
			return undefined;
	}
}

export function buildNowPlayingMetadata(item: QueueItem): NowPlaying {
	return {
		albumId: item.albumId,
		albumName: item.albumName,
		artistName: item.artistName,
		coverUrl: item.coverUrl,
		sourceType: item.sourceType,
		discNumber: item.discNumber,
		trackSourceId: item.trackSourceId,
		trackName: item.trackName,
		artistId: item.artistId,
		streamUrl: item.streamUrl,
		format: item.format,
		playlistTrackId: item.playlistTrackId
	};
}
