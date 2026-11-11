<!-- Empty-chat state: a greeting and suggestion cards, ChatGPT style. -->
<script lang="ts">
	import { demo, exampleQuestion } from '#lib/content/demo';

	let { disabled, onpick }: { disabled: boolean; onpick: (q: string) => void } = $props();
</script>

<div class="empty">
	<span class="mark" aria-hidden="true"></span>
	<h3>{demo.chat.greeting}</h3>
	<div class="grid" data-tour="demo-examples">
		{#each demo.examples as ex (ex.lead)}
			<button class="card" {disabled} onclick={() => onpick(exampleQuestion(ex))}>
				<span class="lead">{ex.lead}</span>
				<span class="rest">{ex.rest}</span>
			</button>
		{/each}
	</div>
</div>

<style>
	.empty {
		margin: auto 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: var(--space-5);
	}
	.mark {
		width: 48px;
		height: 48px;
		border-radius: 14px;
		background: linear-gradient(135deg, var(--accent), #a57bff);
		box-shadow: 0 8px 30px rgba(123, 150, 255, 0.35);
	}
	h3 {
		font-size: var(--text-xl);
		font-weight: 600;
	}
	.grid {
		width: 100%;
		max-width: 720px;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-3);
		margin-top: var(--space-4);
	}
	.card {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
		text-align: left;
		padding: var(--space-3) var(--space-4);
		background: transparent;
		border: 1px solid var(--border-strong);
		border-radius: var(--radius-lg);
		color: var(--text);
		cursor: pointer;
		transition:
			background var(--dur) var(--ease),
			border-color var(--dur) var(--ease);
	}
	.card:hover:not(:disabled) {
		background: var(--surface-2);
	}
	.card:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.lead {
		font-weight: 600;
		font-size: var(--text-sm);
	}
	.rest {
		font-size: var(--text-sm);
		color: var(--text-muted);
	}
	@media (max-width: 560px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
