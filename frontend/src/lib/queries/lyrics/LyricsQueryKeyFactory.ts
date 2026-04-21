import type { SourceType } from '$lib/player/types';

export const LyricsQueryKeyFactory = {
	prefix: ['lyrics'] as const,
	lyrics: (
		sourceType: SourceType | undefined,
		trackSourceId: string | undefined,
		artistName: string | undefined,
		trackName: string | undefined
	) => [...LyricsQueryKeyFactory.prefix, sourceType, trackSourceId, artistName, trackName] as const
};
