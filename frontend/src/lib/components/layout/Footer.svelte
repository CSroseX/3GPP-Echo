<script lang="ts">
	import { author, footer, site } from '#lib/config/site';
	import { resetTours } from '#lib/tours/tour';

	function replayTours() {
		resetTours();
		location.reload();
	}
</script>

<footer>
	<div class="inner">
		<div class="brand">
			<p class="name"><span class="logo" aria-hidden="true"></span>{site.name}</p>
			<p class="tagline">{footer.tagline}</p>
			<div class="author">
				<p class="by">{author.role} <strong>{author.name}</strong></p>
				<div class="social">
					{#if author.github}
						<a href={author.github} target="_blank" rel="noopener" aria-label="GitHub">
							<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.42-2.7 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z"/></svg>
							GitHub
						</a>
					{/if}
					{#if author.linkedin}
						<a href={author.linkedin} target="_blank" rel="noopener" aria-label="LinkedIn">
							<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13ZM7.12 20.45H3.56V9h3.56v11.45ZM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0Z"/></svg>
							LinkedIn
						</a>
					{/if}
				</div>
			</div>
		</div>

		{#each footer.columns as col (col.title)}
			<nav class="col" aria-label={col.title}>
				<p class="col-title">{col.title}</p>
				<ul>
					{#each col.links as link (link.href + link.label)}
						<li><a href={link.href} target="_blank" rel="noopener">{link.label}</a></li>
					{/each}
				</ul>
			</nav>
		{/each}
	</div>
	<div class="bottom">
		<span>© {new Date().getFullYear()} {author.name}</span>
		<button onclick={replayTours}>Replay the guided tours</button>
	</div>
</footer>

<style>
	footer {
		background: var(--surface);
		border-top: 1px solid var(--border);
		padding: var(--space-7) var(--gutter) var(--space-5);
		font-size: var(--text-sm);
		color: var(--text-muted);
	}
	.inner {
		max-width: var(--content-width);
		margin: 0 auto;
		display: grid;
		grid-template-columns: 2fr 1fr 1fr 1fr;
		gap: var(--space-6);
	}
	.name {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		font-weight: 700;
		font-size: var(--text-base);
		color: var(--text);
	}
	.logo {
		width: 20px;
		height: 20px;
		border-radius: 6px;
		background: var(--accent);
	}
	.tagline {
		margin-top: var(--space-2);
		max-width: 36ch;
	}
	.author {
		margin-top: var(--space-5);
	}
	.by strong {
		color: var(--text);
	}
	.social {
		display: flex;
		gap: var(--space-3);
		margin-top: var(--space-2);
	}
	.social a {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 6px 12px;
		border: 1px solid var(--border);
		border-radius: 999px;
		color: var(--text);
		font-weight: 500;
	}
	.social a:hover {
		border-color: var(--accent);
		text-decoration: none;
	}
	.social svg {
		width: 16px;
		height: 16px;
		fill: currentColor;
	}
	.col-title {
		font-weight: 600;
		color: var(--text);
		margin-bottom: var(--space-3);
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}
	.col a {
		color: var(--text-muted);
	}
	.col a:hover {
		color: var(--accent);
	}
	.bottom {
		max-width: var(--content-width);
		margin: var(--space-6) auto 0;
		padding-top: var(--space-4);
		border-top: 1px solid var(--border);
		display: flex;
		justify-content: space-between;
		font-size: var(--text-xs);
	}
	button {
		background: none;
		border: 0;
		padding: 0;
		color: var(--accent);
		cursor: pointer;
		font-size: inherit;
	}
	@media (max-width: 820px) {
		.inner {
			grid-template-columns: 1fr 1fr;
		}
		.brand {
			grid-column: 1 / -1;
		}
	}
</style>
