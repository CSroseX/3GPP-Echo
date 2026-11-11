<script lang="ts">
	import { demo } from '#lib/content/demo';

	let { status, tour = false }: { status: string | null; tour?: boolean } = $props();
	const s = $derived(demo.status[status ?? ''] ?? demo.status.partial);
</script>

<span
	class="badge"
	style="--c: {s.color}; --soft: {s.soft}"
	title={s.hint}
	data-tour={tour ? 'answer-status' : undefined}
>
	<span class="dot" aria-hidden="true"></span>{s.label}
</span>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 2px 10px;
		border-radius: 999px;
		background: var(--soft);
		color: var(--c);
		font-size: var(--text-xs);
		font-weight: 600;
		cursor: help;
	}
	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--c);
	}
</style>
