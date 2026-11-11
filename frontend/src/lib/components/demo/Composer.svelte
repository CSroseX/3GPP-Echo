<!-- Message input: a rounded bar with a round send button. -->
<script lang="ts">
	import { demo } from '#lib/content/demo';

	let { disabled, onask }: { disabled: boolean; onask: (q: string) => void } = $props();
	let text = $state('');
	let box: HTMLTextAreaElement | undefined = $state();

	function submit(e?: SubmitEvent) {
		e?.preventDefault();
		const q = text.trim();
		if (!q || disabled) return;
		onask(q);
		text = '';
		if (box) box.style.height = '';
	}

	function grow() {
		if (!box) return;
		box.style.height = 'auto';
		box.style.height = `${Math.min(box.scrollHeight, 160)}px`;
	}
</script>

<form class="composer" onsubmit={submit} data-tour="demo-composer">
	<textarea
		bind:this={box}
		bind:value={text}
		rows="1"
		maxlength={demo.composer.maxChars}
		placeholder={demo.composer.placeholder}
		aria-label="Your question"
		oninput={grow}
		onkeydown={(e) => {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault();
				submit();
			}
		}}
	></textarea>
	<button type="submit" aria-label={demo.composer.send} disabled={disabled || !text.trim()}>
		<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
	</button>
</form>

<style>
	.composer {
		display: flex;
		align-items: flex-end;
		gap: var(--space-2);
		background: var(--surface-2);
		border: 1px solid var(--border-strong);
		border-radius: 26px;
		padding: var(--space-2) var(--space-2) var(--space-2) var(--space-5);
		transition: border-color var(--dur) var(--ease);
	}
	.composer:focus-within {
		border-color: var(--accent);
	}
	textarea {
		flex: 1;
		border: 0;
		resize: none;
		font: inherit;
		font-size: var(--text-sm);
		line-height: 1.5;
		color: var(--text);
		background: transparent;
		outline: none;
		padding: 9px 0;
		max-height: 160px;
	}
	textarea::placeholder {
		color: var(--text-faint);
	}
	button {
		flex: none;
		width: 38px;
		height: 38px;
		border-radius: 50%;
		border: 0;
		background: var(--text);
		color: var(--surface);
		display: grid;
		place-items: center;
		cursor: pointer;
		transition: opacity var(--dur) var(--ease);
	}
	button:disabled {
		opacity: 0.25;
		cursor: not-allowed;
	}
	svg {
		width: 18px;
		height: 18px;
		stroke: currentColor;
		stroke-width: 2.4;
		fill: none;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
