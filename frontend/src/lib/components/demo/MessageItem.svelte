<!-- One exchange: the visitor's bubble on the right, the answer on the left. -->
<script lang="ts">
	import { demo } from '#lib/content/demo';
	import { formatMs, totalMs } from '#lib/flow';
	import type { Message } from '#lib/stores/chat.svelte';
	import SourceCard from './SourceCard.svelte';
	import StatusBadge from './StatusBadge.svelte';

	let {
		msg,
		selected,
		first,
		onselect
	}: { msg: Message; selected: boolean; first: boolean; onselect: () => void } = $props();

	const errorText = $derived(msg.error ? (demo.errors[msg.error.code] ?? (msg.error.message || demo.errors.default)) : '');
	const ms = $derived(totalMs(msg));
</script>

<article class="msg" class:selected>
	<p class="question">{msg.question}</p>

	<div class="answer">
		<span class="avatar" aria-hidden="true"></span>
		<div
			class="body"
			role="button"
			tabindex="0"
			onclick={onselect}
			onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onselect()}
			aria-label="Show this answer's route"
		>
			{#if msg.phase === 'queued' || msg.phase === 'running'}
				<p class="thinking"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>Working through the pipeline</p>
			{:else if msg.phase === 'error'}
				<p class="error">{errorText}</p>
			{:else if msg.response}
				<div class="meta">
					<StatusBadge status={msg.response.status} tour={first} />
					{#if msg.response.cached}<span class="chip">from cache</span>{/if}
					{#if msg.recorded}<span class="chip">{demo.flow.recorded}</span>{/if}
					{#if ms}<span class="time mono">{formatMs(ms)}</span>{/if}
				</div>
				<p class="text">{msg.response.answer}</p>
				{#if msg.response.sources.length}
					<div class="sources" data-tour={first ? 'answer-sources' : undefined}>
						<p class="sources-title">{demo.sources.title}</p>
						<ul>
							{#each msg.response.sources as source, i (i)}
								<SourceCard {source} />
							{/each}
						</ul>
					</div>
				{/if}
			{/if}
		</div>
	</div>
</article>

<style>
	.msg {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}
	.question {
		align-self: flex-end;
		max-width: 75%;
		background: var(--surface-2);
		color: var(--text);
		padding: var(--space-3) var(--space-4);
		border-radius: 20px;
		font-size: var(--text-sm);
		line-height: 1.55;
	}
	.answer {
		display: flex;
		gap: var(--space-3);
		align-items: flex-start;
	}
	.avatar {
		flex: none;
		width: 28px;
		height: 28px;
		border-radius: 8px;
		background: linear-gradient(135deg, var(--accent), #a57bff);
		margin-top: 2px;
	}
	.body {
		flex: 1;
		min-width: 0;
		border-radius: var(--radius);
		padding: 2px var(--space-2) var(--space-2);
		margin: -2px calc(var(--space-2) * -1) 0;
		cursor: pointer;
		transition: background var(--dur) var(--ease);
	}
	.selected .body {
		background: var(--accent-soft);
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
		margin: 4px 0 var(--space-2);
	}
	.chip {
		font-size: var(--text-xs);
		padding: 1px 8px;
		border-radius: 999px;
		background: var(--surface-2);
		color: var(--text-muted);
	}
	.time {
		margin-left: auto;
		font-size: var(--text-xs);
		color: var(--text-faint);
	}
	.text {
		white-space: pre-wrap;
		font-size: var(--text-base);
		line-height: 1.7;
	}
	.sources {
		margin-top: var(--space-4);
	}
	.sources-title {
		font-size: var(--text-xs);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--text-muted);
		margin-bottom: var(--space-2);
	}
	.sources ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}
	.thinking {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		color: var(--text-muted);
		padding-top: 4px;
	}
	.dots {
		display: inline-flex;
		gap: 4px;
	}
	.dots i {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--text-muted);
		animation: bounce 1s infinite ease-in-out;
	}
	.dots i:nth-child(2) {
		animation-delay: 0.15s;
	}
	.dots i:nth-child(3) {
		animation-delay: 0.3s;
	}
	.error {
		color: var(--stop);
		padding-top: 4px;
	}
	@keyframes bounce {
		0%,
		80%,
		100% {
			transform: translateY(0);
			opacity: 0.4;
		}
		40% {
			transform: translateY(-4px);
			opacity: 1;
		}
	}
</style>
