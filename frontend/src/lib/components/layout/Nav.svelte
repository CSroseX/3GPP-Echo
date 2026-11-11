<script lang="ts">
	import { nav, site } from '#lib/config/site';

	let scrolled = $state(false);
	let open = $state(false);
</script>

<svelte:window onscroll={() => (scrolled = window.scrollY > 8)} />

<nav class:scrolled>
	<div class="inner">
		<a class="brand" href="#top" onclick={() => (open = false)}>
			<span class="logo" aria-hidden="true"></span>
			{site.name}
		</a>
		<button class="menu" aria-label="Menu" aria-expanded={open} onclick={() => (open = !open)}>
			<span></span><span></span><span></span>
		</button>
		<ul class:open>
			{#each nav as link (link.href)}
				<li>
					<a
						href={link.href}
						target={link.external ? '_blank' : undefined}
						rel={link.external ? 'noopener' : undefined}
						class:cta={link.href === '#demo'}
						onclick={() => (open = false)}
					>
						{link.label}{#if link.external}<span aria-hidden="true"> ↗</span>{/if}
					</a>
				</li>
			{/each}
		</ul>
	</div>
</nav>

<style>
	nav {
		position: sticky;
		top: 0;
		z-index: 50;
		height: var(--nav-height);
		background: color-mix(in srgb, var(--bg) 85%, transparent);
		backdrop-filter: blur(10px);
		border-bottom: 1px solid transparent;
		transition: border-color var(--dur) var(--ease);
	}
	nav.scrolled {
		border-bottom-color: var(--border);
	}
	.inner {
		max-width: var(--content-width);
		height: 100%;
		margin: 0 auto;
		padding: 0 var(--gutter);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		font-weight: 700;
		color: var(--text);
		text-decoration: none;
	}
	.logo {
		width: 22px;
		height: 22px;
		border-radius: 6px;
		background: var(--accent);
		box-shadow: inset 0 -6px 0 rgba(255, 255, 255, 0.25);
	}
	ul {
		display: flex;
		gap: var(--space-5);
		list-style: none;
		margin: 0;
		padding: 0;
		align-items: center;
	}
	ul a {
		color: var(--text-muted);
		font-weight: 500;
		font-size: var(--text-sm);
	}
	ul a:hover {
		color: var(--text);
		text-decoration: none;
	}
	ul a.cta {
		color: var(--accent-text);
		background: var(--accent);
		padding: var(--space-2) var(--space-4);
		border-radius: 999px;
	}
	ul a.cta:hover {
		background: var(--accent-hover);
	}
	.menu {
		display: none;
		background: none;
		border: 0;
		padding: var(--space-2);
		cursor: pointer;
	}
	.menu span {
		display: block;
		width: 20px;
		height: 2px;
		margin: 4px 0;
		background: var(--text);
	}
	@media (max-width: 640px) {
		.menu {
			display: block;
		}
		ul {
			display: none;
			position: absolute;
			top: var(--nav-height);
			left: 0;
			right: 0;
			flex-direction: column;
			align-items: stretch;
			gap: 0;
			background: var(--surface);
			border-bottom: 1px solid var(--border);
			padding: var(--space-2) var(--gutter) var(--space-4);
		}
		ul.open {
			display: flex;
		}
		ul a {
			display: block;
			padding: var(--space-3) 0;
		}
		ul a.cta {
			text-align: center;
			margin-top: var(--space-2);
		}
	}
</style>
