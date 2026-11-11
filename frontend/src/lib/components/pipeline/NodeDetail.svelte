<!-- The panel under the diagram describing the selected step. -->
<script lang="ts">
	import type { MapNode } from '#lib/content/pipeline';

	let { node, color, laneTitle }: { node: MapNode; color: string; laneTitle: string } = $props();
	const d = $derived(node.detail!);
</script>

<article class="detail" style="--c: {color}" data-tour="pipeline-detail" aria-live="polite">
	{#key node.id}
		<div class="body">
			<div class="main">
				<p class="lane">{laneTitle}</p>
				<h3>{node.title}</h3>
				<dl>
					<dt>What it does</dt>
					<dd>{d.what}</dd>
					<dt>Why it exists</dt>
					<dd>{d.why}</dd>
				</dl>
				{#if d.points?.length}
					<ul>
						{#each d.points as point (point)}
							<li>{point}</li>
						{/each}
					</ul>
				{/if}
			</div>
			{#if d.stat}
				<aside class="stat">
					<p class="value">{d.stat.value}</p>
					<p class="label">{d.stat.label}</p>
				</aside>
			{/if}
		</div>
	{/key}
</article>

<style>
	.detail {
		margin-top: var(--space-6);
		background: var(--surface);
		border: 1px solid var(--border);
		border-top: 4px solid var(--c);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-sm);
		overflow: hidden;
	}
	.body {
		display: grid;
		grid-template-columns: 1fr 220px;
		gap: var(--space-6);
		padding: var(--space-6);
		animation: fade 260ms var(--ease);
	}
	.lane {
		font-size: var(--text-xs);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--c);
	}
	h3 {
		font-size: var(--text-xl);
		margin: var(--space-1) 0 var(--space-4);
	}
	dl {
		display: grid;
		grid-template-columns: 9rem 1fr;
		gap: var(--space-2) var(--space-4);
		margin: 0;
	}
	dt {
		font-weight: 600;
		font-size: var(--text-sm);
		color: var(--text-muted);
		padding-top: 2px;
	}
	dd {
		margin: 0;
	}
	ul {
		margin: var(--space-4) 0 0;
		padding-left: var(--space-5);
		color: var(--text-muted);
	}
	li {
		margin: var(--space-1) 0;
	}
	.stat {
		align-self: start;
		background: var(--bg);
		border-radius: var(--radius);
		padding: var(--space-5);
		text-align: center;
	}
	.value {
		font-size: var(--text-2xl);
		font-weight: 700;
		color: var(--c);
		letter-spacing: -0.02em;
	}
	.label {
		font-size: var(--text-sm);
		color: var(--text-muted);
		line-height: 1.45;
		margin-top: var(--space-1);
	}
	@keyframes fade {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}
	@media (max-width: 760px) {
		.body {
			grid-template-columns: 1fr;
			padding: var(--space-5);
		}
		dl {
			grid-template-columns: 1fr;
			gap: 0;
		}
		dd {
			margin-bottom: var(--space-3);
		}
	}
</style>
