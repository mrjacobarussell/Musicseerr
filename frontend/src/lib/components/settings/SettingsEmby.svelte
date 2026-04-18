<script lang="ts">
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { onDestroy } from 'svelte';

	type EmbyConnectionSettings = {
		emby_url: string;
		api_key: string;
		user_id: string;
		enabled: boolean;
	};

	const form = createSettingsForm<EmbyConnectionSettings>({
		loadEndpoint: '/api/v1/settings/emby',
		saveEndpoint: '/api/v1/settings/emby',
		testEndpoint: '/api/v1/settings/emby/verify',
		enabledField: 'enabled',
		refreshIntegration: true
	});

	let showApiKey = $state(false);

	export async function load() {
		await form.load();
	}

	async function save() {
		await form.save();
	}

	async function test() {
		await form.test();
	}

	$effect(() => {
		form.load();
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Emby Connection</h2>
		<p class="text-base-content/70 mb-4">
			Connect your Emby server to browse and stream your music library.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="emby-url">
						<span class="label-text">Emby URL</span>
					</label>
					<input
						id="emby-url"
						type="url"
						bind:value={form.data.emby_url}
						class="input input-bordered w-full"
						placeholder="http://localhost:8096"
					/>
				</div>

				<div class="form-control w-full">
					<label class="label" for="emby-api-key">
						<span class="label-text">API Key</span>
					</label>
					<div class="join w-full">
						<input
							id="emby-api-key"
							type={showApiKey ? 'text' : 'password'}
							bind:value={form.data.api_key}
							class="input input-bordered join-item flex-1"
							placeholder="Your Emby API key"
						/>
						<button type="button" class="btn join-item" onclick={() => (showApiKey = !showApiKey)}>
							{showApiKey ? 'Hide' : 'Show'}
						</button>
					</div>
					<label class="label" for="emby-api-key">
						<span class="label-text-alt text-base-content/50">
							Dashboard → API Keys → + (New API Key)
						</span>
					</label>
				</div>

				<div class="form-control w-full">
					<label class="label" for="emby-user-id">
						<span class="label-text">User ID</span>
					</label>
					<input
						id="emby-user-id"
						type="text"
						bind:value={form.data.user_id}
						class="input input-bordered w-full"
						placeholder="Your Emby user ID"
					/>
					<label class="label" for="emby-user-id">
						<span class="label-text-alt text-base-content/50">
							Dashboard → Users → click user → copy ID from the URL
						</span>
					</label>
				</div>

				{#if form.testResult}
					<div
						class="alert"
						class:alert-success={form.testResult.success}
						class:alert-error={!form.testResult.success}
					>
						<span>{form.testResult.message}</span>
					</div>
				{/if}

				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input
							type="checkbox"
							bind:checked={form.data.enabled}
							class="toggle toggle-primary"
							disabled={!form.testResult?.success && !form.wasAlreadyEnabled}
						/>
						<div>
							<span class="label-text font-medium">Enable Emby Integration</span>
							<p class="text-xs text-base-content/50">
								{#if !form.testResult?.success && !form.wasAlreadyEnabled}
									Test connection first to enable
								{:else}
									Browse and stream music from your Emby library
								{/if}
							</p>
						</div>
					</label>
				</div>

				{#if form.message}
					<div
						class="alert"
						class:alert-success={form.messageType === 'success'}
						class:alert-error={form.messageType === 'error'}
					>
						<span>{form.message}</span>
					</div>
				{/if}

				<div class="flex justify-end gap-2 pt-2">
					<button
						type="button"
						class="btn btn-ghost"
						onclick={test}
						disabled={form.testing || !form.data.emby_url || !form.data.api_key}
					>
						{#if form.testing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Test Connection
					</button>
					<button type="button" class="btn btn-primary" onclick={save} disabled={form.saving}>
						{#if form.saving}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Save Settings
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
