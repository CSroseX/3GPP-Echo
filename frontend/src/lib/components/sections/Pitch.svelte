<script lang="ts">
	import { author } from '#lib/config/site';
	import { pitch } from '#lib/content/pitch';
</script>

<section id="pitch" class="pitch">
	<div class="inner">
		<div class="hero">
			<p class="eyebrow">{pitch.eyebrow}</p>
			<h1>{pitch.headline}</h1>
			<p class="subline">{pitch.subline}</p>
			<div class="ctas">
				<a class="btn primary" href={pitch.primaryCta.href}>{pitch.primaryCta.label}</a>
				<a class="btn ghost" href={pitch.secondaryCta.href}>{pitch.secondaryCta.label} →</a>
			</div>
			<p class="byline">
				{author.role} <strong>{author.name}</strong>
				{#if author.github}· <a href={author.github} target="_blank" rel="noopener">GitHub</a>{/if}
				{#if author.linkedin}· <a href={author.linkedin} target="_blank" rel="noopener">LinkedIn</a>{/if}
			</p>
		</div>

		<div class="tiles">
			{#each pitch.tiles as tile, i (tile.label)}
				<div class="tile" style="--i: {i}">
					<p class="value">{tile.value}{#if tile.unit}<span class="unit"> {tile.unit}</span>{/if}</p>
					<p class="label">{tile.label}</p>
				</div>
			{/each}
		</div>
		<a class="note" href={pitch.tilesNote.href}>{pitch.tilesNote.label} →</a>

		<div class="cards">
			<div class="card">
				<h3>{pitch.problem.title}</h3>
				<p>{pitch.problem.body}</p>
				<ul class="pairs">
					{#each pitch.problem.pairs as pair (pair.a)}
						<li><code>{pair.a}</code><span class="ne" aria-label="is not">≠</span><code>{pair.b}</code></li>
					{/each}
				</ul>
			</div>
			<div class="card">
				<h3>{pitch.audience.title}</h3>
				<ul class="audience">
					{#each pitch.audience.items as item (item)}
						<li>{item}</li>
					{/each}
				</ul>
			</div>
		</div>
	</div>
</section>

<style>
	.pitch {
		padding: var(--space-8) var(--gutter) var(--space-7);
		background:
			radial-gradient(1200px 400px at 80% -10%, var(--accent-soft), transparent 70%),
			var(--bg);
	}
	.inner {
		max-width: var(--content-width);
		margin: 0 auto;
	}
	.hero {
		max-width: 52rem;
	}
	.eyebrow {
		color: var(--accent);
		font-weight: 600;
		font-size: var(--text-sm);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	h1 {
		font-size: var(--text-hero);
		margin: var(--space-3) 0 var(--space-4);
		letter-spacing: -0.025em;
	}
	.subline {
		font-size: var(--text-lg);
		color: var(--text-muted);
		max-width: var(--prose-width);
	}
	.ctas {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		margin-top: var(--space-6);
	}
	.byline {
		margin-top: var(--space-4);
		font-size: var(--text-sm);
		color: var(--text-muted);
	}
	.byline strong {
		color: var(--text);
	}
	.btn {
		display: inline-flex;
		align-items: center;
		padding: var(--space-3) var(--space-5);
		border-radius: 999px;
		font-weight: 600;
		text-decoration: none;
		transition:
			background var(--dur) var(--ease),
			transform var(--dur) var(--ease);
	}
	.btn:hover {
		text-decoration: none;
		transform: translateY(-1px);
	}
	.primary {
		background: var(--accent);
		color: var(--accent-text);
	}
	.primary:hover {
		background: var(--accent-hover);
	}
	.ghost {
		color: var(--text);
		border: 1px solid var(--border-strong);
		background: var(--surface);
	}

	.tiles {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: var(--space-4);
		margin-top: var(--space-8);
	}
	.tile {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: var(--space-5);
		box-shadow: var(--shadow-sm);
		animation: rise 600ms var(--ease) both;
		animation-delay: calc(var(--i) * 90ms);
	}
	.value {
		font-size: var(--text-2xl);
		font-weight: 700;
		color: var(--accent);
		letter-spacing: -0.02em;
	}
	.unit {
		margin-left: 0.3em;
		font-size: var(--text-base);
		font-weight: 600;
		color: var(--text-muted);
	}
	.label {
		margin-top: var(--space-1);
		font-size: var(--text-sm);
		color: var(--text-muted);
		line-height: 1.45;
	}
	.note {
		display: inline-block;
		margin-top: var(--space-3);
		font-size: var(--text-sm);
		font-weight: 500;
	}

	.cards {
		display: grid;
		grid-template-columns: 3fr 2fr;
		gap: var(--space-4);
		margin-top: var(--space-7);
	}
	.card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: var(--space-5) var(--space-6);
	}
	.card h3 {
		font-size: var(--text-lg);
		margin-bottom: var(--space-2);
	}
	.card p {
		color: var(--text-muted);
	}
	.pairs {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		list-style: none;
		padding: 0;
		margin: var(--space-4) 0 0;
	}
	.pairs li {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--space-2) var(--space-3);
	}
	.pairs code {
		font-weight: 500;
	}
	.ne {
		color: var(--stop);
		font-weight: 700;
	}
	.audience {
		margin: var(--space-2) 0 0;
		padding: 0;
		list-style: none;
	}
	.audience li {
		padding: var(--space-2) 0 var(--space-2) var(--space-5);
		position: relative;
		border-bottom: 1px solid var(--border);
	}
	.audience li:last-child {
		border-bottom: 0;
	}
	.audience li::before {
		content: '';
		position: absolute;
		left: 0;
		top: 50%;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--accent);
		transform: translateY(-50%);
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}
	@media (max-width: 900px) {
		.tiles {
			grid-template-columns: repeat(2, 1fr);
		}
		.cards {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 480px) {
		.tiles {
			grid-template-columns: 1fr;
		}
	}
</style>
