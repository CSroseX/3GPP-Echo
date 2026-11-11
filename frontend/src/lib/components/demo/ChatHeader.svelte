<!-- Top bar of the chat window: name, server state, budget, new chat. -->
<script lang="ts">
	import { demo } from '#lib/content/demo';
	import { chat } from '#lib/stores/chat.svelte';
	import { server } from '#lib/stores/backend.svelte';

	const statusText = $derived(
		server.status === 'ready' ? demo.server.ready : server.status === 'offline' ? demo.server.offline : demo.server.waking
	);
</script>

<header class="bar">
	<div class="who">
		<span class="avatar" aria-hidden="true"></span>
		<div>
			<p class="name">{demo.chat.title}</p>
			<p class="status {server.status}">
				<span class="dot" aria-hidden="true"></span>{statusText}
				{#if server.status === 'offline'}<button class="link" onclick={() => server.wake()}>Retry</button>{/if}
			</p>
		</div>
	</div>
	<div class="right">
		{#if server.budgetExhausted}
			<span class="budget out">{demo.errors.budget_exhausted}</span>
		{:else}
			{#if server.questionsLeft !== null && server.questionsPerDay}
				<span class="quota" class:out={server.questionsLeft === 0} data-tour="demo-quota">
					{server.questionsLeft === 0 ? demo.quota.exhausted : demo.quota.questions(server.questionsLeft, server.questionsPerDay)}
				</span>
			{/if}
			{#if server.budgetUsd !== null}
				<span class="budget mono">{demo.quota.budget(server.budgetUsd)}</span>
			{/if}
		{/if}
		<button class="new" onclick={() => chat.clear()} disabled={chat.busy || chat.messages.length === 0}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
			{demo.chat.newChat}
		</button>
	</div>
</header>

<style>
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
		padding: var(--space-3) var(--space-5);
		border-bottom: 1px solid var(--border);
		background: var(--surface-2);
	}
	.who {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}
	.avatar {
		width: 34px;
		height: 34px;
		border-radius: 10px;
		background: linear-gradient(135deg, var(--accent), #a57bff);
		flex: none;
	}
	.name {
		font-weight: 600;
		font-size: var(--text-sm);
	}
	.status {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: var(--text-xs);
		color: var(--text-muted);
	}
	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--warn);
		animation: blink 1.2s ease-in-out infinite;
	}
	.ready .dot {
		background: var(--ok);
		animation: none;
	}
	.offline .dot {
		background: var(--stop);
		animation: none;
	}
	.right {
		display: flex;
		align-items: center;
		gap: var(--space-4);
	}
	.budget {
		font-size: var(--text-xs);
		color: var(--text-muted);
	}
	.quota {
		font-size: var(--text-xs);
		font-weight: 600;
		padding: 3px 10px;
		border-radius: 999px;
		background: var(--accent-soft);
		color: var(--accent);
	}
	.quota.out {
		background: var(--stop-soft);
		color: var(--stop);
	}
	.budget.out {
		color: var(--stop);
		font-weight: 600;
	}
	.new {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: transparent;
		color: var(--text);
		border: 1px solid var(--border-strong);
		border-radius: 999px;
		padding: 5px 12px;
		font-size: var(--text-xs);
		cursor: pointer;
	}
	.new:hover:not(:disabled) {
		border-color: var(--accent);
	}
	.new:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.new svg {
		width: 14px;
		height: 14px;
		stroke: currentColor;
		stroke-width: 2;
		fill: none;
	}
	.link {
		background: none;
		border: 0;
		color: var(--accent);
		cursor: pointer;
		font-size: inherit;
		padding: 0;
	}
	@keyframes blink {
		50% {
			opacity: 0.35;
		}
	}
	@media (max-width: 560px) {
		.budget {
			display: none;
		}
	}
</style>
