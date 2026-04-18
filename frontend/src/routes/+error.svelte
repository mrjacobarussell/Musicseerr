<script lang="ts">
	import { AlertTriangle, Home, RotateCw } from 'lucide-svelte';
	import { page } from '$app/state';
</script>

<svelte:head>
	<title>Error - MusicSeerr</title>
</svelte:head>

<div class="w-full px-2 sm:px-4 lg:px-8 py-4 sm:py-8 max-w-7xl mx-auto">
	<div class="flex flex-col items-center justify-center py-20 gap-4 text-center">
		<AlertTriangle class="h-16 w-16 text-error/40" />
		<h1 class="text-lg font-semibold text-base-content/80">Something went wrong</h1>
		<p class="text-sm text-base-content/60">
			{page.error?.message ?? 'An unexpected error occurred'}
		</p>
		<div class="flex items-center gap-2">
			<a href="/" class="btn btn-ghost btn-sm">
				<Home class="h-4 w-4" />
				Home
			</a>
			<button class="btn btn-accent btn-sm" onclick={() => location.reload()}>
				<RotateCw class="h-4 w-4" />
				Retry
			</button>
		</div>
	</div>
</div>
