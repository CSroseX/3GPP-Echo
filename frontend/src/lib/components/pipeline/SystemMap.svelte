<!--
	The system map: groups, boxes and right-angled arrows drawn on a fixed
	canvas from content/pipeline.ts, scaled to fit. Hover traces a box's
	connections; click selects it.
-->
<script lang="ts">
	import { pipeline, type MapNode } from '#lib/content/pipeline';
	import { route } from '#lib/map';

	let { selectedId, onselect }: { selectedId: string; onselect: (id: string) => void } = $props();

	const { width: W, height: H } = pipeline.canvas;
	const byId = new Map(pipeline.nodes.map((n) => [n.id, n]));
	const routes = pipeline.edges
		.map((e, i) => ({ e, i, r: route(e, byId) }))
		.filter((x): x is typeof x & { r: NonNullable<typeof x.r> } => x.r !== null);

	let hoverId = $state<string | null>(null);
	const focusId = $derived(hoverId);
	const linked = $derived.by(() => {
		if (!focusId) return null;
		const ids = new Set([focusId]);
		for (const { e } of routes) {
			if (e.from === focusId) ids.add(e.to);
			if (e.to === focusId) ids.add(e.from);
		}
		return ids;
	});
	const edgeOn = (from: string, to: string) => !focusId || from === focusId || to === focusId;

	// Scale the fixed canvas to the container; below a minimum, scroll sideways instead.
	let boxWidth = $state(W);
	const MIN = 0.62;
	const scale = $derived(Math.max(MIN, Math.min(1, (boxWidth - 2) / W)));

	const toneClass = (n: MapNode) => (n.tone ? `t-${n.tone}` : '');
</script>

<div class="frame" bind:clientWidth={boxWidth}>
	<div class="scroller">
		<div class="sizer" style="width: {W * scale}px; height: {H * scale}px">
			<div class="canvas" style="width: {W}px; height: {H}px; transform: scale({scale})">
				{#each pipeline.groups as g (g.id)}
					<div
						class="group g-{g.tone}"
						style="left: {g.x}px; top: {g.y}px; width: {g.w}px; height: {g.h}px"
						data-tour="group-{g.id}"
					>
						<span class="group-title">{g.title}</span>
					</div>
				{/each}

				<svg class="edges" width={W} height={H} viewBox="0 0 {W} {H}" aria-hidden="true">
					<defs>
						{#each ['main', 'branch', 'data'] as k (k)}
							<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
								<path d="M0 0 L10 5 L0 10 z" class="head-{k}" />
							</marker>
						{/each}
					</defs>
					{#each routes as { e, r, i } (i)}
						<path d={r.d} class="edge e-{e.kind}" class:dim={!edgeOn(e.from, e.to)} class:hot={focusId && edgeOn(e.from, e.to)} marker-end="url(#arrow-{e.kind})" />
						{#if e.kind === 'main'}
							<path d={r.d} class="flow" class:dim={!edgeOn(e.from, e.to)} />
						{/if}
					{/each}
				</svg>

				{#each routes as { e, r, i } (i)}
					{#if r.label}
						<span class="elabel l-{e.kind}" class:dim={!edgeOn(e.from, e.to)} style="left: {r.label[0]}px; top: {r.label[1]}px">{e.label}</span>
					{/if}
				{/each}

				{#each pipeline.nodes as n (n.id)}
					<button
						class="node k-{n.kind} {toneClass(n)}"
						class:selected={selectedId === n.id}
						class:clickable={!!n.detail}
						class:dim={linked && !linked.has(n.id)}
						style="left: {n.x}px; top: {n.y}px; width: {n.w}px; height: {n.h}px"
						data-tour="node-{n.id}"
						onmouseenter={() => (hoverId = n.id)}
						onmouseleave={() => (hoverId = null)}
						onfocus={() => (hoverId = n.id)}
						onblur={() => (hoverId = null)}
						onclick={() => n.detail && onselect(n.id)}
						tabindex={n.detail ? 0 : -1}
					>
						{#if n.kind === 'decision'}
							<svg class="diamond" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
								<polygon points="50,2 98,50 50,98 2,50" />
							</svg>
							<span class="dtext">{n.title}</span>
						{:else}
							<span class="title">{n.title}</span>
							{#if n.sub}<span class="sub">{n.sub}</span>{/if}
							{#if n.lines}
								<ul class="lines">
									{#each n.lines as l (l)}<li>{l}</li>{/each}
								</ul>
							{/if}
							{#if n.tech?.length}
								<span class="tech">
									{#each n.tech as t (t)}<span class="chip">{t}</span>{/each}
								</span>
							{/if}
							{#if n.detail}<span class="more" aria-hidden="true">i</span>{/if}
						{/if}
					</button>
				{/each}

			</div>
		</div>
	</div>
	<div class="legend">
		{#each pipeline.legend as item (item.kind)}
			<span class="lg"><svg width="34" height="10" aria-hidden="true"><path d="M1 5 H33" class="edge e-{item.kind}" /></svg>{item.label}</span>
		{/each}
		<span class="lg"><span class="lg-end">end</span>Run ends here</span>
		<span class="lg"><span class="lg-i">i</span>Click for details</span>
	</div>
</div>

<style>
	.frame {
		width: 100%;
	}
	.scroller {
		overflow-x: auto;
		overflow-y: hidden;
		border-radius: var(--radius-lg);
		background:
			radial-gradient(circle, color-mix(in srgb, var(--text) 9%, transparent) 1px, transparent 1.2px) 0 0 / 22px 22px,
			var(--surface);
		border: 1px solid var(--border);
	}
	.sizer {
		position: relative;
		overflow: hidden;
	}
	.canvas {
		position: absolute;
		top: 0;
		left: 0;
		transform-origin: 0 0;
		font-size: 13px;
	}

	/* Groups */
	.group {
		position: absolute;
		border: 1.5px dashed var(--gc);
		border-radius: 14px;
		background: color-mix(in srgb, var(--gc) 4%, transparent);
	}
	.g-offline {
		--gc: var(--lane-offline);
	}
	.g-query {
		--gc: var(--lane-query);
	}
	.g-neutral {
		--gc: var(--border-strong);
		background: color-mix(in srgb, var(--surface) 70%, transparent);
		border-style: solid;
	}
	.group-title {
		position: absolute;
		top: -11px;
		left: 16px;
		padding: 0 8px;
		background: var(--surface);
		color: var(--gc);
		font-weight: 700;
		font-size: 13px;
		letter-spacing: 0.02em;
	}
	.g-neutral .group-title {
		color: var(--text-muted);
	}

	/* Edges */
	.edges {
		position: absolute;
		inset: 0;
		overflow: visible;
		pointer-events: none;
	}
	.edge {
		fill: none;
		stroke-width: 1.6;
		transition: opacity var(--dur) var(--ease), stroke-width var(--dur);
	}
	.e-main {
		stroke: var(--lane-query);
	}
	.e-branch {
		stroke: var(--text-faint);
		stroke-dasharray: 6 4;
	}
	.e-data {
		stroke: var(--lane-offline);
		stroke-dasharray: 2 4;
		stroke-linecap: round;
	}
	.head-main {
		fill: var(--lane-query);
	}
	.head-branch {
		fill: var(--text-faint);
	}
	.head-data {
		fill: var(--lane-offline);
	}
	.edge.hot {
		stroke-width: 2.6;
	}
	.flow {
		fill: none;
		stroke: #fff;
		stroke-width: 1.6;
		stroke-dasharray: 3 21;
		opacity: 0.85;
		animation: flow 1.4s linear infinite;
	}
	.dim {
		opacity: 0.15;
	}
	@keyframes flow {
		to {
			stroke-dashoffset: -24;
		}
	}
	.elabel {
		position: absolute;
		transform: translate(-50%, -50%);
		padding: 1px 6px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 600;
		background: var(--surface);
		border: 1px solid var(--border);
		color: var(--text-muted);
		white-space: nowrap;
		pointer-events: none;
		transition: opacity var(--dur);
	}
	.l-main {
		color: var(--lane-query);
	}
	.l-data {
		color: var(--lane-offline);
	}

	/* Nodes */
	.node {
		position: absolute;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 3px;
		padding: 10px 12px;
		text-align: left;
		font: inherit;
		color: var(--text);
		background: var(--surface);
		border: 1.5px solid var(--nc, var(--border-strong));
		border-radius: 10px;
		box-shadow: var(--shadow-sm);
		cursor: default;
		transition:
			opacity var(--dur) var(--ease),
			box-shadow var(--dur) var(--ease),
			transform var(--dur) var(--ease);
		overflow: hidden;
	}
	.node.clickable {
		cursor: pointer;
	}
	.node.clickable:hover {
		transform: translateY(-2px);
		box-shadow: var(--shadow);
	}
	.node.selected {
		box-shadow: 0 0 0 4px color-mix(in srgb, var(--nc, var(--accent)) 25%, transparent);
		background: color-mix(in srgb, var(--nc, var(--accent)) 7%, var(--surface));
	}
	.t-offline {
		--nc: var(--lane-offline);
	}
	.t-query {
		--nc: var(--lane-query);
	}
	.t-warn {
		--nc: var(--stop);
	}
	.title {
		font-weight: 700;
		font-size: 13.5px;
		line-height: 1.25;
	}
	.sub {
		font-size: 11.5px;
		line-height: 1.4;
		color: var(--text-muted);
	}
	.lines {
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: 11.5px;
		line-height: 1.45;
		color: var(--text-muted);
	}
	.tech {
		margin-top: auto;
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}
	.chip {
		font-size: 10.5px;
		font-weight: 600;
		padding: 1px 7px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--nc, var(--text-muted)) 12%, transparent);
		color: var(--nc, var(--text-muted));
		white-space: nowrap;
	}
	.more {
		position: absolute;
		top: 8px;
		right: 8px;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 1px solid var(--nc, var(--border-strong));
		color: var(--nc, var(--text-muted));
		font-size: 10px;
		font-weight: 700;
		font-style: italic;
		display: grid;
		place-items: center;
		font-family: Georgia, serif;
	}

	/* Database-style boxes */
	.k-store {
		border-radius: 50% / 14px;
		padding-top: 18px;
	}
	/* Start / finish boxes */
	.k-io {
		border-radius: 999px;
		padding-left: 22px;
		padding-right: 22px;
		justify-content: center;
		background: color-mix(in srgb, var(--nc, var(--accent)) 8%, var(--surface));
	}
	/* Decision diamonds */
	.k-decision {
		background: transparent;
		border: 0;
		box-shadow: none;
		padding: 0;
		align-items: center;
		justify-content: center;
		overflow: visible;
	}
	.diamond {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}
	.diamond polygon {
		fill: var(--warn-soft);
		stroke: var(--warn);
		stroke-width: 2;
		vector-effect: non-scaling-stroke;
	}
	.dtext {
		position: relative;
		font-size: 11.5px;
		font-weight: 700;
		text-align: center;
		line-height: 1.2;
		padding: 0 14px;
	}
	/* Ends */
	.k-end {
		border-radius: 999px;
		align-items: center;
		justify-content: center;
		padding: 0 8px;
		background: var(--text);
		border-color: var(--text);
		color: var(--surface);
	}
	.k-end .title {
		font-size: 11.5px;
		font-weight: 600;
	}
	/* Sticky notes */
	.k-note {
		background: #fff8db;
		border: 1px solid #f0dc8a;
		border-radius: 4px;
		box-shadow: 2px 3px 0 rgba(0, 0, 0, 0.06);
		transform: rotate(-0.6deg);
	}
	.k-note .title {
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #8a6d00;
	}
	.k-note .lines {
		color: #5c4a00;
	}
	.k-note .lines li::before {
		content: '• ';
	}
	/* Small observability boxes */
	.k-mini {
		flex-direction: row;
		align-items: center;
		gap: 8px;
		padding: 0 12px;
		border-style: dashed;
		box-shadow: none;
	}
	.k-mini .sub {
		white-space: nowrap;
	}

	/* Legend */
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-5);
		margin-top: var(--space-3);
		font-size: var(--text-xs);
		color: var(--text-muted);
	}
	.lg-i {
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 1px solid var(--lane-query);
		color: var(--lane-query);
		font: italic 700 10px Georgia, serif;
		display: grid;
		place-items: center;
	}
	.lg {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.lg-end {
		display: inline-block;
		width: 34px;
		text-align: center;
		font-size: 10px;
		border-radius: 999px;
		background: var(--text);
		color: var(--surface);
	}
	@media (prefers-reduced-motion: reduce) {
		.flow {
			display: none;
		}
	}
</style>
