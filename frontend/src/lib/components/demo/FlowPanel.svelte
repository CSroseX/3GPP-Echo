<!-- Side panel: the selected question's route, animating live. -->
<script lang="ts">
	import { demo } from '#lib/content/demo';
	import { flowSteps, formatMs, totalMs } from '#lib/flow';
	import type { Message } from '#lib/stores/chat.svelte';
	import StatusBadge from './StatusBadge.svelte';

	let { msg }: { msg: Message | null } = $props();

	const steps = $derived(msg ? flowSteps(msg, demo.flow.steps) : []);
	const running = $derived(msg?.phase === 'queued' || msg?.phase === 'running');

	// Live elapsed timer while a run is in progress.
	let now = $state(Date.now());
	$effect(() => {
		if (!running) return;
		const t = setInterval(() => (now = Date.now()), 100);
		return () => clearInterval(t);
	});
	const elapsed = $derived(
		msg ? (running ? Math.max(0, now - msg.startedAt) : totalMs(msg)) : 0
	);
</script>

<aside class="panel" data-tour="demo-flow" aria-live="polite">
	<header>
		<h3>{demo.flow.title}</h3>
		{#if msg}
			<span class="clock mono" class:live={running}>{running ? `${(elapsed / 1000).toFixed(1)} s` : formatMs(elapsed)}</span>
		{/if}
	</header>

	{#if !msg}
		<p class="empty">{demo.flow.empty}</p>
	{:else}
		<p class="q" title={msg.question}>{msg.question}</p>
		<ol class="steps">
			{#each steps as step (step.id)}
				<li class="step {step.state}">
					<span class="marker" aria-hidden="true">
						{#if step.state === 'done'}✓{/if}
					</span>
					<div class="content">
						<p class="title">{step.title}</p>
						{#if step.fact}
							<p class="fact">{step.fact}</p>
						{:else if step.state === 'active'}
							<p class="fact working">working…</p>
						{/if}
					</div>
				</li>
			{/each}
			<li class="step end" class:done={msg.phase === 'done'} class:failed={msg.phase === 'error'}>
				<span class="marker" aria-hidden="true">{msg.phase === 'done' ? '✓' : msg.phase === 'error' ? '!' : ''}</span>
				<div class="content">
					<p class="title">Answer</p>
					{#if msg.phase === 'done' && msg.response}
						<p class="fact"><StatusBadge status={msg.response.status} /></p>
					{:else if msg.phase === 'error'}
						<p class="fact">Stopped</p>
					{/if}
				</div>
			</li>
		</ol>
		{#if msg.recorded}<p class="note">{demo.flow.recorded}: replayed with its original timing.</p>{/if}
	{/if}
</aside>

<style>
	.panel {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: var(--space-5);
		box-shadow: var(--shadow-sm);
	}
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: var(--space-3);
	}
	h3 {
		font-size: var(--text-base);
	}
	.clock {
		font-size: var(--text-xs);
		color: var(--text-faint);
	}
	.clock.live {
		color: var(--accent);
	}
	.empty {
		color: var(--text-muted);
		font-size: var(--text-sm);
	}
	.q {
		font-size: var(--text-sm);
		color: var(--text-muted);
		margin-bottom: var(--space-4);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.steps {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.step {
		position: relative;
		display: flex;
		gap: var(--space-3);
		padding-bottom: var(--space-4);
		animation: appear 300ms var(--ease) both;
	}
	/* Connector line between markers. */
	.step:not(:last-child)::before {
		content: '';
		position: absolute;
		left: 11px;
		top: 26px;
		bottom: 2px;
		width: 2px;
		background: var(--border);
		transition: background var(--dur) var(--ease);
	}
	.step.done:not(:last-child)::before {
		background: var(--accent);
	}
	.marker {
		flex: none;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		border: 2px solid var(--border-strong);
		background: var(--surface);
		display: grid;
		place-items: center;
		font-size: 0.75rem;
		font-weight: 700;
		color: #fff;
		transition:
			background var(--dur) var(--ease),
			border-color var(--dur) var(--ease);
	}
	.done .marker {
		background: var(--accent);
		border-color: var(--accent);
	}
	.active .marker {
		border-color: var(--accent);
		animation: pulse 1.1s var(--ease) infinite;
	}
	.failed .marker {
		background: var(--stop);
		border-color: var(--stop);
	}
	.title {
		font-weight: 600;
		font-size: var(--text-sm);
		line-height: 24px;
	}
	.pending .title {
		color: var(--text-faint);
	}
	.fact {
		font-size: var(--text-xs);
		color: var(--text-muted);
		line-height: 1.5;
		animation: appear 300ms var(--ease) both;
	}
	.fact.working {
		color: var(--accent);
	}
	.note {
		margin-top: var(--space-2);
		font-size: var(--text-xs);
		color: var(--text-faint);
	}
	@keyframes pulse {
		0%,
		100% {
			box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 45%, transparent);
		}
		50% {
			box-shadow: 0 0 0 7px color-mix(in srgb, var(--accent) 0%, transparent);
		}
	}
	@keyframes appear {
		from {
			opacity: 0;
			transform: translateY(3px);
		}
	}
</style>
