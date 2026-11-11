<script lang="ts">
	import Section from '#lib/components/ui/Section.svelte';
	import SystemMap from '#lib/components/pipeline/SystemMap.svelte';
	import NodeDetail from '#lib/components/pipeline/NodeDetail.svelte';
	import { pipeline } from '#lib/content/pipeline';

	const groupTitle = { offline: 'Ingestion', query: 'Serving', neutral: 'Serving', warn: 'Serving' } as const;
	const colorOf = { offline: 'var(--lane-offline)', query: 'var(--lane-query)', neutral: 'var(--lane-query)', warn: 'var(--stop)' } as const;

	let selectedId = $state(pipeline.initial);
	const selected = $derived(pipeline.nodes.find((n) => n.id === selectedId && n.detail) ?? pipeline.nodes.find((n) => n.detail)!);
</script>

<Section id="pipeline" eyebrow={pipeline.eyebrow} title={pipeline.title} intro={pipeline.intro} tone="alt" wide>
	<SystemMap {selectedId} onselect={(id) => (selectedId = id)} />
	<NodeDetail
		node={selected}
		color={colorOf[selected.tone ?? 'query']}
		laneTitle={groupTitle[selected.tone ?? 'query']}
	/>
</Section>
