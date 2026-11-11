<!-- Shared frame for a page section: anchor id, heading block, width. -->
<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		id,
		eyebrow = '',
		title = '',
		intro = '',
		tone = 'plain',
		wide = false,
		children
	}: {
		id: string;
		eyebrow?: string;
		title?: string;
		intro?: string;
		tone?: 'plain' | 'alt' | 'dark';
		wide?: boolean;
		children: Snippet;
	} = $props();
</script>

<section {id} class="section {tone}">
	<div class="inner" class:wide>
		{#if title}
			<header>
				{#if eyebrow}<p class="eyebrow">{eyebrow}</p>{/if}
				<h2>{title}</h2>
				{#if intro}<p class="intro">{intro}</p>{/if}
			</header>
		{/if}
		{@render children()}
	</div>
</section>

<style>
	.section {
		padding: var(--space-8) var(--gutter);
	}
	.alt {
		background: var(--bg-alt);
		border-block: 1px solid var(--border);
	}
	/* Dark tone: re-points the tokens, so every component inside follows. */
	.dark {
		--bg: #0e1014;
		--bg-alt: #14171d;
		--surface: #181b22;
		--surface-2: #20242d;
		--border: #2a2f3a;
		--border-strong: #3a404d;
		--text: #e7e9ee;
		--text-muted: #a0a8b6;
		--text-faint: #6f7786;
		--accent: #7b96ff;
		--accent-hover: #93a9ff;
		--accent-soft: rgba(123, 150, 255, 0.16);
		--accent-text: #0e1014;
		--ok-soft: rgba(52, 199, 120, 0.16);
		--ok: #4ad295;
		--warn-soft: rgba(240, 180, 70, 0.16);
		--warn: #f0b446;
		--neutral-soft: rgba(160, 168, 182, 0.14);
		--neutral: #a0a8b6;
		--stop-soft: rgba(240, 110, 110, 0.16);
		--stop: #f07a7a;
		--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
		background: var(--bg);
		color: var(--text);
	}
	.inner {
		max-width: var(--content-width);
		margin: 0 auto;
	}
	.inner.wide {
		max-width: 1280px;
	}
	header {
		margin-bottom: var(--space-6);
		max-width: var(--prose-width);
	}
	.eyebrow {
		color: var(--accent);
		font-weight: 600;
		font-size: var(--text-sm);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin-bottom: var(--space-2);
	}
	h2 {
		font-size: var(--text-2xl);
	}
	.intro {
		margin-top: var(--space-3);
		color: var(--text-muted);
		font-size: var(--text-lg);
	}
</style>
