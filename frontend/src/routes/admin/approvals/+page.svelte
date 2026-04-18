<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Check, X, Inbox, RotateCcw } from 'lucide-svelte';
	import { api, ApiError } from '$lib/api/client';
	import { API } from '$lib/constants';
	import { authStore } from '$lib/stores/auth.svelte';
	import { adminPendingApprovalsStore } from '$lib/stores/adminPendingApprovals';
	import { errorModal } from '$lib/stores/errorModal';
	import AlbumImage from '$lib/components/AlbumImage.svelte';

	type PendingApproval = {
		musicbrainz_id: string;
		artist_name: string;
		album_title: string;
		requested_at: string;
		artist_mbid?: string | null;
		year?: number | null;
		cover_url?: string | null;
		requested_by?: string | null;
		monitor_artist?: boolean;
		auto_download_artist?: boolean;
	};

	type PendingApprovalsResponse = {
		items: PendingApproval[];
		count: number;
	};

	let items = $state<PendingApproval[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busyMbid = $state<string | null>(null);

	async function load() {
		loading = true;
		error = null;
		try {
			const res = await api.global.get<PendingApprovalsResponse>(API.adminRequestsPending());
			items = res?.items ?? [];
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Failed to load pending approvals';
		} finally {
			loading = false;
		}
	}

	async function approve(mbid: string, label: string) {
		busyMbid = mbid;
		try {
			await api.global.post(API.adminApproveRequest(mbid), {});
			items = items.filter((i) => i.musicbrainz_id !== mbid);
			void adminPendingApprovalsStore.refresh();
		} catch (e) {
			const msg = e instanceof ApiError ? e.message : 'Network error';
			errorModal.show(`Approval failed for ${label}`, msg, '');
		} finally {
			busyMbid = null;
		}
	}

	async function reject(mbid: string, label: string) {
		busyMbid = mbid;
		try {
			await api.global.post(API.adminRejectRequest(mbid), {});
			items = items.filter((i) => i.musicbrainz_id !== mbid);
			void adminPendingApprovalsStore.refresh();
		} catch (e) {
			const msg = e instanceof ApiError ? e.message : 'Network error';
			errorModal.show(`Reject failed for ${label}`, msg, '');
		} finally {
			busyMbid = null;
		}
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleString(undefined, {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		});
	}

	onMount(() => {
		if (authStore.authEnabled && authStore.role !== 'admin') {
			void goto('/');
			return;
		}
		void load();
	});
</script>

<svelte:head>
	<title>Pending approvals · Musicseerr</title>
</svelte:head>

<div class="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
	<div class="flex items-center justify-between gap-3">
		<div class="flex items-center gap-3">
			<div class="p-2 rounded-lg bg-primary/10 text-primary">
				<Inbox class="h-6 w-6" />
			</div>
			<div>
				<h1 class="text-2xl font-bold">Pending approvals</h1>
				<p class="text-base-content/60 text-sm">
					Requests from users who don't have permission to submit directly.
				</p>
			</div>
		</div>
		<button class="btn btn-ghost btn-sm gap-1" onclick={() => void load()} disabled={loading}>
			<RotateCcw class="h-4 w-4" />
			Refresh
		</button>
	</div>

	{#if loading}
		<div class="flex justify-center py-16">
			<span class="loading loading-spinner loading-lg text-primary"></span>
		</div>
	{:else if error}
		<div class="alert alert-error">{error}</div>
	{:else if items.length === 0}
		<div class="card bg-base-200">
			<div class="card-body items-center text-center py-12">
				<Inbox class="h-10 w-10 text-base-content/30" />
				<p class="text-base-content/60">No pending approvals.</p>
			</div>
		</div>
	{:else}
		<div class="overflow-x-auto card bg-base-200">
			<table class="table table-sm">
				<thead>
					<tr>
						<th>Album</th>
						<th>Artist</th>
						<th>Requested by</th>
						<th>Requested</th>
						<th class="text-right">Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each items as item (item.musicbrainz_id)}
						<tr>
							<td>
								<div class="flex items-center gap-3">
									<div class="w-10 h-10 shrink-0 rounded overflow-hidden">
										<AlbumImage
											mbid={item.musicbrainz_id}
											customUrl={item.cover_url ?? null}
											alt={item.album_title}
											size="sm"
											rounded="md"
											className="w-full h-full"
										/>
									</div>
									<div class="flex flex-col min-w-0">
										<span class="font-medium line-clamp-1">{item.album_title}</span>
										{#if item.year}
											<span class="text-xs text-base-content/50">{item.year}</span>
										{/if}
									</div>
								</div>
							</td>
							<td class="text-sm">{item.artist_name}</td>
							<td class="text-sm text-base-content/70">{item.requested_by ?? '—'}</td>
							<td class="text-xs text-base-content/60 whitespace-nowrap">
								{formatDate(item.requested_at)}
							</td>
							<td>
								<div class="flex justify-end gap-1">
									<button
										class="btn btn-success btn-xs gap-1"
										disabled={busyMbid === item.musicbrainz_id}
										onclick={() => void approve(item.musicbrainz_id, item.album_title)}
									>
										<Check class="h-3.5 w-3.5" />
										Approve
									</button>
									<button
										class="btn btn-ghost btn-xs gap-1 text-error"
										disabled={busyMbid === item.musicbrainz_id}
										onclick={() => void reject(item.musicbrainz_id, item.album_title)}
									>
										<X class="h-3.5 w-3.5" />
										Reject
									</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
