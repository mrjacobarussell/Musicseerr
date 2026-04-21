import { api } from '$lib/api/client';
import { API, CACHE_TTL } from '$lib/constants';
import type { MusicSource } from '$lib/stores/musicSource';
import type { HomeResponse } from '$lib/types';
import { createQuery } from '@tanstack/svelte-query';
import type { Getter } from 'runed';
import { HomeQueryKeyFactory } from './HomeQueryKeyFactory';

export const getHomeQuery = (getSource: Getter<MusicSource>) =>
	createQuery(() => ({
		staleTime: CACHE_TTL.HOME,
		queryKey: HomeQueryKeyFactory.home(getSource()),
		queryFn: ({ signal }) =>
			api.global.get<HomeResponse>(API.home(getSource()), {
				signal
			})
	}));
