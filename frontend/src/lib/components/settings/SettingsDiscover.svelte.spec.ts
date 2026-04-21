import { page } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render } from 'vitest-browser-svelte';

vi.mock('$env/dynamic/public', () => ({
	env: { PUBLIC_API_URL: '' }
}));

import SettingsDiscover from './SettingsDiscover.svelte';

function mockHomeSettings(overrides: { show_globally_trending?: boolean } = {}) {
	return {
		show_whats_hot: true,
		show_globally_trending: true,
		cache_ttl_trending: 3600,
		cache_ttl_personal: 300,
		...overrides
	};
}

function mockJsonResponse(data: ReturnType<typeof mockHomeSettings>) {
	return vi.fn().mockResolvedValue(
		new Response(JSON.stringify(data), {
			status: 200,
			headers: { 'content-type': 'application/json' }
		})
	);
}

function mockErrorResponse() {
	return vi.fn().mockResolvedValue(
		new Response(JSON.stringify({ error: { message: 'Failed to load settings' } }), {
			status: 500,
			headers: { 'content-type': 'application/json' }
		})
	);
}

describe('SettingsDiscover.svelte', () => {
	let originalFetch: typeof globalThis.fetch;

	beforeEach(() => {
		originalFetch = globalThis.fetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it('renders heading', async () => {
		globalThis.fetch = mockJsonResponse(mockHomeSettings());
		render(SettingsDiscover);

		const heading = page.getByRole('heading', { name: 'Discover' });
		await expect.element(heading).toBeInTheDocument();
	});

	it('shows loading spinner initially', async () => {
		globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
		const { container } = render(SettingsDiscover);

		await vi.waitFor(() => {
			const spinners = container.querySelectorAll('.loading');
			expect(spinners.length).toBeGreaterThan(0);
		});
	});

	it('renders toggle after load', async () => {
		globalThis.fetch = mockJsonResponse(mockHomeSettings());
		render(SettingsDiscover);

		const label = page.getByText('Show Globally Trending');
		await expect.element(label).toBeInTheDocument();
	});

	it('renders save button', async () => {
		globalThis.fetch = mockJsonResponse(mockHomeSettings());
		render(SettingsDiscover);

		const saveBtn = page.getByRole('button', { name: 'Save Settings' });
		await expect.element(saveBtn).toBeInTheDocument();
	});

	it('shows error message when load fails', async () => {
		globalThis.fetch = mockErrorResponse();
		render(SettingsDiscover);

		const errorAlert = page.getByText("Couldn't load your settings");
		await expect.element(errorAlert).toBeInTheDocument();
	});

	it('toggle reflects loaded state when disabled', async () => {
		globalThis.fetch = mockJsonResponse(mockHomeSettings({ show_globally_trending: false }));
		render(SettingsDiscover);

		await vi.waitFor(() => {
			const toggle = document.querySelector('input[type="checkbox"].toggle') as HTMLInputElement;
			expect(toggle).not.toBeNull();
			expect(toggle.checked).toBe(false);
		});
	});

	it('toggle reflects loaded state when enabled', async () => {
		globalThis.fetch = mockJsonResponse(mockHomeSettings({ show_globally_trending: true }));
		render(SettingsDiscover);

		await vi.waitFor(() => {
			const toggle = document.querySelector('input[type="checkbox"].toggle') as HTMLInputElement;
			expect(toggle).not.toBeNull();
			expect(toggle.checked).toBe(true);
		});
	});
});
