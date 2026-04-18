<script lang="ts">
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import { launchEmbyPlayback } from '$lib/player/launchEmbyPlayback';
	import type { EmbyHubResponse, EmbyAlbumSummary, EmbyAlbumDetail } from '$lib/types';
	import { onMount } from 'svelte';

	let hub = $state<EmbyHubResponse | null>(null);
	let loading = $state(true);
	let error = $state('');

	let selectedAlbum = $state<EmbyAlbumDetail | null>(null);
	let modalOpen = $state(false);
	let albumLoading = $state(false);

	async function loadHub() {
		loading = true;
		error = '';
		try {
			hub = await api.get<EmbyHubResponse>(API.embyLibrary.hub());
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load Emby library';
		} finally {
			loading = false;
		}
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

	function getImageUrl(album: EmbyAlbumSummary): string {
		return album.image_url ?? API.embyLibrary.image(album.emby_id);
	}

	onMount(() => {
		loadHub();
	});
</script>

<div class="container mx-auto p-4 max-w-7xl">
	<div class="flex items-center gap-3 mb-6">
		<svg class="h-8 w-8" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" style="color: rgb(82 186 82)">
			<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/>
		</svg>
		<h1 class="text-3xl font-bold">Emby Library</h1>
	</div>

	{#if loading}
		<div class="flex justify-center py-20">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if error}
		<div class="alert alert-error">{error}</div>
	{:else if hub}
		{#if hub.stats}
			<div class="stats shadow mb-6 w-full">
				<div class="stat">
					<div class="stat-title">Artists</div>
					<div class="stat-value text-2xl">{hub.stats.total_artists.toLocaleString()}</div>
				</div>
				<div class="stat">
					<div class="stat-title">Albums</div>
					<div class="stat-value text-2xl">{hub.stats.total_albums.toLocaleString()}</div>
				</div>
				<div class="stat">
					<div class="stat-title">Tracks</div>
					<div class="stat-value text-2xl">{hub.stats.total_tracks.toLocaleString()}</div>
				</div>
			</div>
		{/if}

		<div class="flex items-center justify-between mb-4">
			<h2 class="text-xl font-semibold">Recently Added</h2>
			<a href="/library/emby/albums" class="btn btn-sm btn-ghost">Browse all albums</a>
		</div>

		{#if hub.recently_added.length === 0}
			<p class="text-base-content/50 py-8 text-center">No albums found</p>
		{:else}
			<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
				{#each hub.recently_added as album (album.emby_id)}
					<button
						class="group text-left"
						onclick={() => openAlbum(album)}
					>
						<div class="aspect-square rounded-lg overflow-hidden bg-base-300 mb-2 relative">
							<img
								src={getImageUrl(album)}
								alt={album.name}
								class="w-full h-full object-cover group-hover:scale-105 transition-transform"
								onerror={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
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
		{/if}

		<div class="flex gap-4 mt-8">
			<a href="/library/emby/albums" class="btn btn-outline">Browse Albums</a>
			<a href="/library/emby/artists" class="btn btn-outline">Browse Artists</a>
		</div>
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
						onerror={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
					/>
					<div>
						<h3 class="text-xl font-bold">{selectedAlbum.name}</h3>
						<p class="text-base-content/60">{selectedAlbum.artist_name}</p>
						{#if selectedAlbum.year}
							<p class="text-sm text-base-content/40">{selectedAlbum.year}</p>
						{/if}
						<p class="text-sm text-base-content/50 mt-1">{selectedAlbum.track_count} tracks</p>
					</div>
				</div>

				{#if selectedAlbum.tracks.length > 0}
					<button
						class="btn btn-primary btn-sm mb-4"
						onclick={() => playAlbum(selectedAlbum!)}
					>
						Play Album
					</button>
					<div class="divide-y divide-base-300 max-h-80 overflow-y-auto">
						{#each selectedAlbum.tracks as track, i (track.emby_id)}
							<button
								class="w-full flex items-center gap-3 py-2 px-1 hover:bg-base-200 rounded text-left"
								onclick={() => playAlbum(selectedAlbum!, i)}
							>
								<span class="text-xs text-base-content/40 w-6 text-right">{track.track_number}</span>
								<span class="flex-1 truncate text-sm">{track.title}</span>
								<span class="text-xs text-base-content/40">
									{Math.floor(track.duration_seconds / 60)}:{String(Math.floor(track.duration_seconds % 60)).padStart(2, '0')}
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
