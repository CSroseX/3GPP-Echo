<script lang="ts">
	import { onMount } from 'svelte';
	import Nav from '#lib/components/layout/Nav.svelte';
	import Footer from '#lib/components/layout/Footer.svelte';
	import { registry } from '#lib/components/sections/registry';
	import { sections, site } from '#lib/config/site';
	import { server } from '#lib/stores/backend.svelte';
	import { watchSections } from '#lib/tours/tour';

	onMount(() => {
		if (site.wakeOnLoad) void server.wake();
		return watchSections();
	});
</script>

<svelte:head>
	<title>{site.name} · grounded answers from the 3GPP specs</title>
	<meta
		name="description"
		content="Ask questions about 3GPP TS 23.501, 24.501 and 24.301 and get answers grounded in the spec text, with clause references."
	/>
</svelte:head>

<div id="top"></div>
<Nav />
<main>
	{#each sections as id (id)}
		{@const Section = registry[id]}
		{#if Section}<Section />{/if}
	{/each}
</main>
<Footer />
