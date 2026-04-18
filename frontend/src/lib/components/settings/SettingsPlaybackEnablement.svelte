<script lang="ts">
	import { onDestroy } from 'svelte';
	import { CircleCheck, CircleAlert, RotateCcw, Save } from 'lucide-svelte';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { API } from '$lib/constants';

	type PlaybackServiceToggles = {
		jellyfin: boolean;
		plex: boolean;
		navidrome: boolean;
		emby: boolean;
		youtube: boolean;
		local_files: boolean;
	};

	const form = createSettingsForm<PlaybackServiceToggles>({
		loadEndpoint: API.adminPlaybackServices(),
		saveEndpoint: API.adminPlaybackServices(),
		refreshIntegration: true,
		defaultValue: {
			jellyfin: true,
			plex: true,
			navidrome: true,
			emby: true,
			youtube: true,
			local_files: true
		}
	});

	$effect(() => {
		void form.load();
	});

	onDestroy(() => form.cleanup());

	const services: Array<{ key: keyof PlaybackServiceToggles; label: string; hint: string }> = [
		{ key: 'jellyfin', label: 'Jellyfin', hint: 'Allow playback and sidebar entry for Jellyfin' },
		{ key: 'plex', label: 'Plex', hint: 'Allow playback and sidebar entry for Plex' },
		{
			key: 'navidrome',
			label: 'Navidrome',
			hint: 'Allow playback and sidebar entry for Navidrome'
		},
		{ key: 'emby', label: 'Emby', hint: 'Allow playback and sidebar entry for Emby' },
		{ key: 'youtube', label: 'YouTube', hint: 'Allow YouTube playback' },
		{ key: 'local_files', label: 'Local Files', hint: 'Allow playback of the local music library' }
	];
</script>

<div class="alert alert-info alert-soft mb-4">
	<span class="text-sm">
		Turn streaming services on or off for Musicseerr. Disabled services are hidden from the sidebar
		and their stream endpoints return 403.
	</span>
</div>

{#if form.message}
	<div
		class="alert {form.messageType === 'success' ? 'alert-success' : 'alert-error'} alert-soft mb-4"
	>
		{#if form.messageType === 'success'}
			<CircleCheck class="w-5 h-5 shrink-0" />
		{:else}
			<CircleAlert class="w-5 h-5 shrink-0" />
		{/if}
		<span>{form.message}</span>
	</div>
{/if}

{#if form.loading}
	<div class="flex justify-center items-center py-10">
		<span class="loading loading-spinner loading-lg text-primary"></span>
	</div>
{:else if form.data}
	<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
		{#each services as svc (svc.key)}
			<fieldset class="fieldset">
				<legend class="fieldset-legend">{svc.label}</legend>
				<label class="label cursor-pointer gap-3">
					<span class="text-sm">{svc.hint}</span>
					<input type="checkbox" bind:checked={form.data[svc.key]} class="toggle toggle-primary" />
				</label>
			</fieldset>
		{/each}
	</div>

	<div class="flex justify-end gap-3 pt-4">
		<button class="btn btn-ghost" onclick={() => form.load()} disabled={form.saving}>
			<RotateCcw class="w-4 h-4" />
			Reset
		</button>
		<button class="btn btn-primary" onclick={() => form.save()} disabled={form.saving}>
			{#if form.saving}
				<span class="loading loading-spinner loading-sm"></span>
				Saving…
			{:else}
				<Save class="w-4 h-4" />
				Save
			{/if}
		</button>
	</div>
{/if}
