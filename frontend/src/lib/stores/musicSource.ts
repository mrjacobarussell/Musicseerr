import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { PAGE_SOURCE_KEYS } from '$lib/constants';
import { api } from '$lib/api/client';

export type MusicSource = 'listenbrainz' | 'lastfm';
export type MusicSourcePage = keyof typeof PAGE_SOURCE_KEYS;

const CACHED_SOURCE_KEY = 'musicseerr_primary_source';
export const DEFAULT_SOURCE: MusicSource = 'listenbrainz';

interface MusicSourceState {
	source: MusicSource;
	loaded: boolean;
}

export function isMusicSource(value: unknown): value is MusicSource {
	return value === 'listenbrainz' || value === 'lastfm';
}

/**
 * Migrate old raw-string localStorage source values to JSON format.
 * Before v1.3.0, setPageSource() stored raw strings (e.g. `listenbrainz`).
 * PersistedState expects JSON (e.g. `"listenbrainz"`). Must run before
 * any PersistedState constructor reads these keys.
 */
export function migratePageSourceKeys(): void {
	if (!browser) return;
	for (const key of Object.values(PAGE_SOURCE_KEYS)) {
		const raw = localStorage.getItem(key);
		if (raw === null) continue;
		if (isMusicSource(raw)) {
			localStorage.setItem(key, JSON.stringify(raw));
		}
	}
}

function readCachedSource(): MusicSource {
	if (!browser) return DEFAULT_SOURCE;
	const stored = localStorage.getItem(CACHED_SOURCE_KEY);
	return isMusicSource(stored) ? stored : DEFAULT_SOURCE;
}

function createMusicSourceStore() {
	const { subscribe, set, update } = writable<MusicSourceState>({
		source: readCachedSource(),
		loaded: false
	});

	let loadPromise: Promise<void> | null = null;
	let mutationVersion = 0;

	function getPageStorageKey(page: MusicSourcePage): string {
		return PAGE_SOURCE_KEYS[page];
	}

	function persistSource(source: MusicSource): void {
		if (browser) {
			localStorage.setItem(CACHED_SOURCE_KEY, source);
		}
	}

	function getCachedSource(): MusicSource {
		return readCachedSource();
	}

	async function load(): Promise<void> {
		const current = get({ subscribe });
		if (current.loaded) return;
		if (loadPromise) return loadPromise;
		const loadStartedAtVersion = mutationVersion;

		loadPromise = (async () => {
			try {
				if (browser) {
					localStorage.removeItem('home_source');
					localStorage.removeItem('discover_source');
					localStorage.removeItem('artist-discovery_source');
				}
				const data = await api.global.get<{ source: unknown }>('/api/v1/settings/primary-source');
				const fetchedSource = isMusicSource(data.source) ? data.source : DEFAULT_SOURCE;
				if (mutationVersion === loadStartedAtVersion) {
					persistSource(fetchedSource);
					set({ source: fetchedSource, loaded: true });
				} else {
					update((s) => ({ ...s, loaded: true }));
				}
			} catch {
				update((s) => ({ ...s, loaded: true }));
			} finally {
				loadPromise = null;
			}
		})();

		return loadPromise;
	}

	async function save(source: MusicSource): Promise<boolean> {
		const saveVersion = ++mutationVersion;
		try {
			await api.global.put('/api/v1/settings/primary-source', { source });
			persistSource(source);
			if (mutationVersion === saveVersion) {
				set({ source, loaded: true });
			}
			return true;
		} catch {
			return false;
		}
	}

	function setSource(source: MusicSource): void {
		mutationVersion += 1;
		persistSource(source);
		set({ source, loaded: true });
	}

	function getSource(): MusicSource {
		return get({ subscribe }).source;
	}

	function getPageSource(page: MusicSourcePage): MusicSource {
		const fallbackSource = getSource();
		if (!browser) return fallbackSource;
		const raw = localStorage.getItem(getPageStorageKey(page));
		if (raw === null) return fallbackSource;
		// Handle JSON-encoded values (new format)
		try {
			const parsed: unknown = JSON.parse(raw);
			if (isMusicSource(parsed)) return parsed;
		} catch {
			// Fall through to raw check
		}
		// Handle raw string values (old format)
		if (isMusicSource(raw)) return raw;
		return fallbackSource;
	}

	function setPageSource(page: MusicSourcePage, source: MusicSource): void {
		if (!browser) return;
		localStorage.setItem(getPageStorageKey(page), JSON.stringify(source));
	}

	return {
		subscribe,
		load,
		save,
		setSource,
		getSource,
		getCachedSource,
		getPageSource,
		setPageSource
	};
}

export const musicSourceStore = createMusicSourceStore();
