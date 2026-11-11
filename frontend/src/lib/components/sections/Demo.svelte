<script lang="ts">
	import { tick } from 'svelte';
	import Section from '#lib/components/ui/Section.svelte';
	import Composer from '#lib/components/demo/Composer.svelte';
	import FlowPanel from '#lib/components/demo/FlowPanel.svelte';
	import MessageItem from '#lib/components/demo/MessageItem.svelte';
	import ChatHeader from '#lib/components/demo/ChatHeader.svelte';
	import Suggestions from '#lib/components/demo/Suggestions.svelte';
	import { demo } from '#lib/content/demo';
	import { chat } from '#lib/stores/chat.svelte';
	import { server } from '#lib/stores/backend.svelte';
	import { trigger } from '#lib/tours/tour';

	let log: HTMLDivElement | undefined = $state();
	let drawerOpen = $state(true);

	const locked = $derived(chat.busy || server.budgetExhausted);
	// Typing is off once today's questions are used; recorded examples still play.
	const typingLocked = $derived(locked || server.quotaExhausted);
	const firstDoneId = $derived(chat.messages.find((m) => m.phase === 'done')?.id ?? null);

	async function ask(q: string) {
		const run = chat.ask(q);
		await tick();
		log?.scrollTo({ top: log.scrollHeight, behavior: 'smooth' });
		await run;
		await tick();
		log?.scrollTo({ top: log.scrollHeight, behavior: 'smooth' });
	}

	// First answer: point out the label, the sources and the route.
	$effect(() => {
		if (chat.answers === 1) {
			void tick().then(() => trigger((t) => t.trigger.on === 'first-answer'));
		}
	});
</script>

<Section id="demo" eyebrow={demo.eyebrow} title={demo.title} intro={demo.intro} tone="dark" wide>
	<div class="layout">
		<div class="window">
			<ChatHeader />

			<details class="drawer" bind:open={drawerOpen}>
				<summary>{demo.flow.title}</summary>
				<FlowPanel msg={chat.selected} />
			</details>

			<div class="log" bind:this={log}>
				{#if chat.messages.length === 0}
					<Suggestions disabled={locked} onpick={ask} />
				{:else}
					{#each chat.messages as msg (msg.id)}
						<MessageItem
							{msg}
							first={msg.id === firstDoneId}
							selected={chat.selected?.id === msg.id && chat.messages.length > 1}
							onselect={() => chat.select(msg.id)}
						/>
					{/each}
				{/if}
			</div>

			<div class="bottom">
				<Composer disabled={typingLocked} onask={ask} />
				<p class="disclaimer">{demo.chat.disclaimer}</p>
			</div>
		</div>

		<div class="side">
			<FlowPanel msg={chat.selected} />
		</div>
	</div>
</Section>

<style>
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 340px;
		gap: var(--space-5);
		align-items: start;
	}
	.window {
		min-width: 0;
		height: 680px;
		display: flex;
		flex-direction: column;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
		overflow: hidden;
	}
	.log {
		flex: 1;
		overflow-y: auto;
		padding: var(--space-6) clamp(var(--space-4), 5%, var(--space-7));
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
		scrollbar-color: var(--border-strong) transparent;
	}
	.bottom {
		padding: 0 clamp(var(--space-4), 5%, var(--space-7)) var(--space-3);
	}
	.disclaimer {
		text-align: center;
		font-size: var(--text-xs);
		color: var(--text-faint);
		margin-top: var(--space-2);
	}
	.side {
		position: sticky;
		top: calc(var(--nav-height) + var(--space-4));
	}
	.drawer {
		display: none;
	}
	@media (max-width: 900px) {
		.layout {
			grid-template-columns: 1fr;
		}
		.side {
			display: none;
		}
		.window {
			height: 640px;
		}
		.drawer {
			display: block;
			padding: var(--space-3) var(--space-4) 0;
		}
		.drawer summary {
			cursor: pointer;
			font-weight: 600;
			font-size: var(--text-sm);
			margin-bottom: var(--space-2);
		}
	}
</style>
