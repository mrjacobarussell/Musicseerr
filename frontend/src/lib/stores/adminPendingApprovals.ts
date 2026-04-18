import { get, writable } from 'svelte/store';
import { API } from '$lib/constants';
import { api } from '$lib/api/client';

interface State {
	count: number;
	loaded: boolean;
}

function createStore() {
	const { subscribe, set, update } = writable<State>({ count: 0, loaded: false });
	let loadPromise: Promise<void> | null = null;

	async function fetchCount(): Promise<void> {
		try {
			const res = await api.global.get<{ count: number }>(API.adminRequestsPendingCount());
			update((s) => ({ ...s, count: res?.count ?? 0, loaded: true }));
		} catch {
			update((s) => ({ ...s, loaded: true }));
		}
	}

	return {
		subscribe,
		ensureLoaded: async () => {
			const current = get({ subscribe });
			if (current.loaded) return;
			if (loadPromise) return loadPromise;
			loadPromise = fetchCount().finally(() => {
				loadPromise = null;
			});
			return loadPromise;
		},
		refresh: async () => fetchCount(),
		reset: () => set({ count: 0, loaded: false })
	};
}

export const adminPendingApprovalsStore = createStore();
