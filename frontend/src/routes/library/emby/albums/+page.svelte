<script lang="ts">
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import { launchEmbyPlayback } from '$lib/player/launchEmbyPlayback';
	import type { EmbyPaginatedResponse, EmbyAlbumSummary, EmbyAlbumDetail } from '$lib/types';
	import { onMount } from 'svelte';

	const PAGE_SIZE = 50;

	let albums = $state<EmbyAlbumSummary[]>([]);
	let total = $state(0);
	let offset = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);
	let error = $state('');
	let search = $state('');
	let searchDebounce: ReturnType<typeof setTimeout> | null = null;

	let selectedAlbum = $state<EmbyAlbumDetail | null>(null);
	let modalOpen = $state(false);
	let albumLoading = $state(false);

	async function loadAlbums(reset = false) {
		if (reset) {
			offset = 0;
			albums = [];
		}
		if (reset) loading = true;
		else loadingMore = true;
		error = '';
		try {
			let url = API.embyLibrary.albums(PAGE_SIZE, offset);
			if (search) url += `&search=${encodeURIComponent(search)}`;
			const data = await api.get<EmbyPaginatedResponse>(url);
			albums = reset ? data.items : [...albums, ...data.items];
			total = data.total;
			offset = albums.length;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load albums';
		} finally {
			loading = false;
			loadingMore = false;
		}
	}

	function handleSearch(value: string) {
		search = value;
		if (searchDebounce) clearTimeout(searchDebounce);
		searchDebounce = setTimeout(() => loadAlbums(true), 300);
	}

	async function openAlbum(album: EmbyAlbumSummary) {
		modalOpen = true;
		albumLoading = true;
		selectedAlbum = null;
		try {
			selectedAlbum = await api.get<EmbyAlbumDetail>(API.embyLibrary.albumDetail(album.emby_id));
		} catch {
			modalOpen = false;
		} finally {
			albumLoading = false;
		}
	}

	function playAlbum(album: EmbyAlbumDetail, startIndex = 0) {
		launchEmbyPlayback(album.tracks, startIndex, false, {
			albumId: album.emby_id,
			albumName: album.name,
			artistName: album.artist_name,
			coverUrl: album.image_url ?? null,
			artistId: undefined
		});
		modalOpen = false;
	}

	onMount(() => {
		loadAlbums(true);
	});
</script>

<div class="container mx-auto p-4 max-w-7xl">
	<div class="flex items-center gap-3 mb-6">
		<a href="/library/emby" class="btn btn-ghost btn-sm">← Emby</a>
		<h1 class="text-2xl font-bold">Albums</h1>
		{#if total > 0}
			<span class="text-base-content/50 text-sm">({total.toLocaleString()})</span>
		{/if}
	</div>

	<div class="mb-4">
		<input
			type="search"
			placeholder="Search albums..."
			class="input input-bordered w-full max-w-sm"
			oninput={(e) => handleSearch((e.target as HTMLInputElement).value)}
		/>
	</div>

	{#if loading}
		<div class="flex justify-center py-20">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if error}
		<div class="alert alert-error">{error}</div>
	{:else if albums.length === 0}
		<p class="text-center text-base-content/50 py-20">No albums found</p>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each albums as album (album.emby_id)}
				<button class="group text-left" onclick={() => openAlbum(album)}>
					<div class="aspect-square rounded-lg overflow-hidden bg-base-300 mb-2">
						<img
							src={album.image_url ?? API.embyLibrary.image(album.emby_id)}
							alt={album.name}
							class="w-full h-full object-cover group-hover:scale-105 transition-transform"
							onerror={(e) => {
								(e.target as HTMLImageElement).style.display = 'none';
							}}
						/>
					</div>
					<p class="font-medium text-sm truncate">{album.name}</p>
					<p class="text-xs text-base-content/60 truncate">{album.artist_name}</p>
					{#if album.year}
						<p class="text-xs text-base-content/40">{album.year}</p>
					{/if}
				</button>
			{/each}
		</div>

		{#if albums.length < total}
			<div class="flex justify-center mt-8">
				<button class="btn btn-outline" disabled={loadingMore} onclick={() => loadAlbums(false)}>
					{#if loadingMore}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					Load more ({total - albums.length} remaining)
				</button>
			</div>
		{/if}
	{/if}
</div>

{#if modalOpen}
	<dialog class="modal modal-open" onclose={() => (modalOpen = false)}>
		<div class="modal-box w-11/12 max-w-2xl">
			{#if albumLoading}
				<div class="flex justify-center py-12">
					<span class="loading loading-spinner loading-lg"></span>
				</div>
			{:else if selectedAlbum}
				<div class="flex gap-4 mb-4">
					<img
						src={selectedAlbum.image_url ?? API.embyLibrary.image(selectedAlbum.emby_id)}
						alt={selectedAlbum.name}
						class="w-24 h-24 rounded-lg object-cover flex-shrink-0"
						onerror={(e) => {
							(e.target as HTMLImageElement).style.display = 'none';
						}}
					/>
					<div>
						<h3 class="text-xl font-bold">{selectedAlbum.name}</h3>
						<p class="text-base-content/60">{selectedAlbum.artist_name}</p>
						{#if selectedAlbum.year}<p class="text-sm text-base-content/40">
								{selectedAlbum.year}
							</p>{/if}
						<p class="text-sm text-base-content/50 mt-1">{selectedAlbum.track_count} tracks</p>
					</div>
				</div>

				{#if selectedAlbum.tracks.length > 0}
					<button class="btn btn-primary btn-sm mb-4" onclick={() => playAlbum(selectedAlbum!)}>
						Play Album
					</button>
					<div class="divide-y divide-base-300 max-h-80 overflow-y-auto">
						{#each selectedAlbum.tracks as track, i (track.emby_id)}
							<button
								class="w-full flex items-center gap-3 py-2 px-1 hover:bg-base-200 rounded text-left"
								onclick={() => playAlbum(selectedAlbum!, i)}
							>
								<span class="text-xs text-base-content/40 w-6 text-right">{track.track_number}</span
								>
								<span class="flex-1 truncate text-sm">{track.title}</span>
								<span class="text-xs text-base-content/40">
									{Math.floor(track.duration_seconds / 60)}:{String(
										Math.floor(track.duration_seconds % 60)
									).padStart(2, '0')}
								</span>
							</button>
						{/each}
					</div>
				{/if}
			{/if}
			<div class="modal-action">
				<button class="btn" onclick={() => (modalOpen = false)}>Close</button>
			</div>
		</div>
		<form method="dialog" class="modal-backdrop">
			<button onclick={() => (modalOpen = false)}>close</button>
		</form>
	</dialog>
{/if}
