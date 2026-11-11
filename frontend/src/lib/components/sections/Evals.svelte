<script lang="ts">
	import Section from '#lib/components/ui/Section.svelte';
	import { evals } from '#lib/content/evals';

	const statusClass = { met: 'ok', tight: 'warn', missed: 'stop' } as const;
</script>

<Section id="evals" eyebrow={evals.eyebrow} title={evals.title} intro={evals.intro}>
	<div class="block">
		<h3>{evals.testSet.title} <span class="muted">· {evals.testSet.total} questions</span></h3>
		<div class="groups">
			{#each evals.testSet.groups as g (g.label)}
				<div class="group">
					<p class="count">{g.count}</p>
					<p class="glabel">{g.label}</p>
					<p class="example">“{g.example}”</p>
				</div>
			{/each}
		</div>
	</div>

	<div class="block" data-tour="evals-criteria">
		<h3>{evals.criteria.title}</h3>
		<p class="caption">{evals.criteria.caption}</p>
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th scope="col">Rule</th>
						<th scope="col">Target</th>
						<th scope="col">Run 1</th>
						<th scope="col">Run 2</th>
						<th scope="col">Result</th>
					</tr>
				</thead>
				<tbody>
					{#each evals.criteria.rows as row, i (row.label)}
						<tr class:missed={row.status === 'missed'} data-tour={row.status === 'tight' && i === evals.criteria.rows.findIndex((r) => r.status === 'tight') ? 'evals-tight' : undefined}>
							<th scope="row">{row.label}</th>
							<td class="mono" data-label="Target">{row.target}</td>
							<td class="mono" data-label="Run 1">{row.run1}</td>
							<td class="mono" data-label="Run 2">{row.run2}</td>
							<td data-label="Result"><span class="pill {statusClass[row.status]}">{evals.criteria.statusLabels[row.status]}</span></td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="note">{evals.criteria.note}</p>
	</div>

	<div class="grid">
		<div class="block card">
			<h3>{evals.progress.title}</h3>
			<p class="caption">{evals.progress.caption}</p>
			<ol class="bars">
				{#each evals.progress.steps as step, i (step.label)}
					<li style="--w: {(step.value / evals.progress.max) * 100}%; --i: {i}">
						<span class="bar-label">{step.label}</span>
						<span class="track"><span class="bar"></span></span>
						<span class="bar-value mono">{step.value}/{evals.progress.max}</span>
					</li>
				{/each}
			</ol>
		</div>

		<div class="block card">
			<h3>{evals.limits.title}</h3>
			<ul class="plain">
				{#each evals.limits.items as item (item)}
					<li>{item}</li>
				{/each}
			</ul>
		</div>
	</div>

	<div class="block card">
		<h3>{evals.dropped.title}</h3>
		<ul class="dropped">
			{#each evals.dropped.items as d (d.what)}
				<li><strong>{d.what}</strong><span>{d.why}</span></li>
			{/each}
		</ul>
	</div>
</Section>

<style>
	.block {
		margin-bottom: var(--space-6);
	}
	h3 {
		font-size: var(--text-lg);
		margin-bottom: var(--space-3);
	}
	.muted,
	.caption {
		color: var(--text-muted);
		font-weight: 400;
	}
	.caption {
		font-size: var(--text-sm);
		margin: -0.25rem 0 var(--space-4);
	}
	.card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: var(--space-5) var(--space-6);
	}

	.groups {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: var(--space-4);
	}
	.group {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: var(--space-5);
	}
	.count {
		font-size: var(--text-2xl);
		font-weight: 700;
		color: var(--accent);
	}
	.glabel {
		font-weight: 600;
	}
	.example {
		margin-top: var(--space-2);
		font-size: var(--text-sm);
		color: var(--text-muted);
		font-style: italic;
	}

	.note {
		margin-top: var(--space-2);
		font-size: var(--text-xs);
		color: var(--text-muted);
	}
	.table-wrap {
		overflow-x: auto;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-sm);
	}
	th,
	td {
		padding: var(--space-3) var(--space-4);
		text-align: left;
		border-bottom: 1px solid var(--border);
		vertical-align: middle;
	}
	thead th {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--text-muted);
		background: var(--bg);
	}
	tbody th {
		font-weight: 500;
	}
	tbody tr:last-child > * {
		border-bottom: 0;
	}
	tr.missed {
		background: var(--stop-soft);
	}
	td.mono {
		white-space: nowrap;
	}
	.pill {
		display: inline-block;
		padding: 2px 10px;
		border-radius: 999px;
		font-size: var(--text-xs);
		font-weight: 600;
		white-space: nowrap;
	}
	.pill.ok {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.pill.warn {
		background: var(--warn-soft);
		color: var(--warn);
	}
	.pill.stop {
		background: var(--stop);
		color: #fff;
	}

	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--space-4);
	}
	.bars {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
	.bars li {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: var(--space-1) var(--space-3);
		align-items: center;
	}
	.bar-label {
		grid-column: 1 / -1;
		font-size: var(--text-sm);
		color: var(--text-muted);
	}
	.track {
		height: 12px;
		background: var(--bg-alt);
		border-radius: 999px;
		overflow: hidden;
	}
	.bar {
		display: block;
		height: 100%;
		width: var(--w);
		background: var(--accent);
		border-radius: 999px;
		opacity: calc(0.55 + var(--i) * 0.2);
		animation: grow 900ms var(--ease) both;
		animation-delay: calc(var(--i) * 150ms);
	}
	.bar-value {
		font-weight: 600;
		font-size: var(--text-sm);
	}
	.plain {
		margin: 0;
		padding-left: var(--space-5);
		color: var(--text-muted);
	}
	.plain li {
		margin-bottom: var(--space-2);
	}
	.dropped {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.dropped li {
		display: grid;
		grid-template-columns: 18rem 1fr;
		gap: var(--space-4);
		padding: var(--space-3) 0;
		border-bottom: 1px solid var(--border);
	}
	.dropped li:last-child {
		border-bottom: 0;
	}
	.dropped strong {
		font-weight: 600;
		text-decoration: line-through;
		text-decoration-color: var(--text-faint);
	}
	.dropped span {
		color: var(--text-muted);
	}
	@keyframes grow {
		from {
			width: 0;
		}
	}
	/* Phones: each rule becomes a small card instead of a wide table row. */
	@media (max-width: 640px) {
		thead {
			display: none;
		}
		table,
		tbody,
		tr,
		th,
		td {
			display: block;
		}
		tr {
			padding: var(--space-3) var(--space-4);
			border-bottom: 1px solid var(--border);
		}
		tbody th,
		td {
			border: 0;
			padding: 2px 0;
		}
		tbody th {
			font-weight: 600;
			margin-bottom: var(--space-1);
		}
		td {
			display: flex;
			justify-content: space-between;
		}
		td::before {
			content: attr(data-label);
			color: var(--text-muted);
			font-family: var(--font-sans);
		}
	}
	@media (max-width: 820px) {
		.groups,
		.grid {
			grid-template-columns: 1fr;
		}
		.dropped li {
			grid-template-columns: 1fr;
			gap: var(--space-1);
		}
	}
</style>
