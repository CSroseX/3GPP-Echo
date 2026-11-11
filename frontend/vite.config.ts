import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		// SvelteKit 3 takes its options here (no svelte.config.js).
		// Static build for Cloudflare Pages: one prerendered page, no server.
		sveltekit({
			adapter: adapter({ pages: 'build', assets: 'build', strict: true }),
			// '#lib/...' resolves to src/lib for both Vite and TypeScript.
			alias: { '#lib': 'src/lib' }
		})
	],
	server: { port: 5173, strictPort: true }
});
