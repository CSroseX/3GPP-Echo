<!-- One cited passage: spec, clause and an expandable excerpt. -->
<script lang="ts">
	import type { Source } from '#lib/api/types';

	let { source }: { source: Source } = $props();
	let open = $state(false);
</script>

<li class="source">
	<button class="head" aria-expanded={open} onclick={() => (open = !open)}>
		<span class="ref mono">TS {source.spec_id} §{source.clause_id}</span>
		<span class="title">{source.clause_title ?? ''}</span>
		{#if source.chunk_type === 'table'}<span class="kind">table</span>{/if}
		<span class="chev" class:open aria-hidden="true">›</span>
	</button>
	{#if open}
		<pre class="excerpt">{source.excerpt}{source.excerpt.length >= 600 ? '…' : ''}</pre>
	{/if}
</li>

<style>
	.source {
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--surface);
		overflow: hidden;
	}
	.head {
		width: 100%;
		display: flex;
		align-items: center;
		gap: var(--space-3);
		padding: var(--space-2) var(--space-3);
		background: none;
		border: 0;
		text-align: left;
		cursor: pointer;
		color: var(--text);
	}
	.head:hover {
		background: var(--bg);
	}
	.ref {
		color: var(--accent);
		font-weight: 500;
		white-space: nowrap;
		font-size: var(--text-xs);
	}
	.title {
		flex: 1;
		font-size: var(--text-sm);
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.kind {
		font-size: 0.7rem;
		padding: 0 6px;
		border-radius: 4px;
		background: var(--bg-alt);
		color: var(--text-muted);
	}
	.chev {
		color: var(--text-faint);
		transition: transform var(--dur) var(--ease);
	}
	.chev.open {
		transform: rotate(90deg);
	}
	.excerpt {
		margin: 0;
		padding: var(--space-3);
		border-top: 1px solid var(--border);
		background: var(--bg);
		font-family: var(--font-mono);
		font-size: 0.78rem;
		line-height: 1.55;
		white-space: pre-wrap;
		word-break: break-word;
		max-height: 220px;
		overflow: auto;
	}
</style>
