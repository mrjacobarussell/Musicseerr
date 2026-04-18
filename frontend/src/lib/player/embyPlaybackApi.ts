import { API } from '$lib/constants';
import { api, ApiError } from '$lib/api/client';

type PlaybackSessionResult = {
	play_session_id: string;
	item_id: string;
};

type StartSessionPayload = {
	play_session_id?: string;
};

export async function startSession(itemId: string, playSessionId?: string): Promise<string> {
	const payload: StartSessionPayload | undefined = playSessionId
		? { play_session_id: playSessionId }
		: undefined;

	try {
		const data = await api.global.post<PlaybackSessionResult>(
			API.stream.embyStart(itemId),
			payload
		);
		return data.play_session_id;
	} catch (e) {
		if (e instanceof ApiError) {
			throw new Error(`Failed to start Emby playback session: ${e.status} ${e.message}`);
		}
		throw e;
	}
}

export async function reportProgress(
	itemId: string,
	playSessionId: string,
	positionSeconds: number,
	isPaused: boolean
): Promise<boolean> {
	try {
		await api.global.post(API.stream.embyProgress(itemId), {
			play_session_id: playSessionId,
			position_seconds: positionSeconds,
			is_paused: isPaused
		});
		return true;
	} catch {
		return false;
	}
}

export async function reportStop(
	itemId: string,
	playSessionId: string,
	positionSeconds: number
): Promise<boolean> {
	try {
		await api.global.post(API.stream.embyStop(itemId), {
			play_session_id: playSessionId,
			position_seconds: positionSeconds
		});
		return true;
	} catch {
		return false;
	}
}
