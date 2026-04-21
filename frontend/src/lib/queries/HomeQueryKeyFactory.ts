import type { MusicSource } from '$lib/stores/musicSource';

export const HomeQueryKeyFactory = {
	prefix: ['home'] as const,
	home: (source: MusicSource) => [...HomeQueryKeyFactory.prefix, source] as const
};
