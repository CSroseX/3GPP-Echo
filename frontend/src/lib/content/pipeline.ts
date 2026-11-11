/**
 * Section 2: the system map. The diagram is drawn entirely from this data on
 * a fixed 1600 × 1300 canvas (scaled to the screen). Move a box by changing
 * its x/y; add an arrow by adding an edge. Sides: r(ight) l(eft) t(op) b(ottom).
 */

export type NodeKind = 'step' | 'store' | 'decision' | 'io' | 'end' | 'note' | 'mini';
export type Side = 'r' | 'l' | 't' | 'b';

export interface NodeDetail {
	what: string;
	why: string;
	points?: string[];
	stat?: { value: string; label: string };
}

export interface MapNode {
	id: string;
	kind: NodeKind;
	x: number;
	y: number;
	w: number;
	h: number;
	title: string;
	sub?: string;
	lines?: string[];
	tech?: string[];
	/** Colour family: a group id. */
	tone?: 'offline' | 'query' | 'neutral' | 'warn';
	detail?: NodeDetail;
}

export interface MapGroup {
	id: string;
	title: string;
	x: number;
	y: number;
	w: number;
	h: number;
	tone: 'offline' | 'query' | 'neutral';
}

export interface MapEdge {
	from: string;
	to: string;
	kind: 'main' | 'branch' | 'data';
	label?: string;
	fromSide?: Side;
	toSide?: Side;
	fromOffset?: number;
	toOffset?: number;
	/** Explicit corner points, for routes the automatic elbow can't draw cleanly. */
	via?: [number, number][];
}

const groups: MapGroup[] = [
	{ id: 'ingest', title: '① Ingestion · built once, offline', x: 20, y: 20, w: 1560, h: 350, tone: 'offline' },
	{ id: 'serve', title: '② Serving · every question', x: 20, y: 400, w: 1560, h: 880, tone: 'query' },
	{ id: 'graph', title: 'LangGraph state machine', x: 270, y: 440, w: 1290, h: 752, tone: 'neutral' },
	{ id: 'obs', title: 'Observability', x: 270, y: 1210, w: 1290, h: 62, tone: 'neutral' }
];

const nodes: MapNode[] = [
	// ── Ingestion ────────────────────────────────────────────────
	{
		id: 'pdfs', kind: 'io', tone: 'offline', x: 50, y: 75, w: 180, h: 100,
		title: '3GPP spec PDFs', sub: 'TS 23.501 v17.11 · 24.501 v17.12 · 24.301 v17.9'
	},
	{
		id: 'parse', kind: 'step', tone: 'offline', x: 280, y: 75, w: 200, h: 100,
		title: 'Parse', sub: 'PDF → layout blocks: headings, text, lists, tables', tech: ['Docling'],
		detail: {
			what: 'Docling reads each PDF and returns its blocks in reading order: headings, paragraphs, bulleted lists and tables.',
			why: 'Spec PDFs are layout-heavy. A plain text dump loses tables and list structure, and the clause headings needed for citations.',
			points: [
				'Bulleted lists come back as groups and are expanded recursively, in reading order.',
				'Before that fix, about 37% of the spec text was silently dropped.',
				'Output is cached as JSON, so later stages re-run without re-parsing.'
			],
			stat: { value: '~37%', label: 'of the text recovered by expanding list groups' }
		}
	},
	{
		id: 'tree', kind: 'step', tone: 'offline', x: 530, y: 75, w: 210, h: 100,
		title: 'Tree builder', sub: 'depth stack → each clause’s full lineage', tech: ['Python'],
		detail: {
			what: 'Rebuilds the clause hierarchy from the flat block list with a depth stack: clause depth = number of dots (5.3.4 → 3).',
			why: 'Every passage must know its place (5.5 → 5.5.1 → 5.5.1.2) so it can be filtered by clause and cited correctly.',
			points: [
				'Letter-suffixed clauses (4.2.5a, 4.2.8.1A) are recognised; an earlier numeric-only rule buried 37 real clauses.',
				'IE bit-diagram rows ("8 7 6 5 4 3 2 1") are kept as text, not parsed as clause 8.'
			],
			stat: { value: '37', label: 'real clauses recovered by the letter-suffix fix' }
		}
	},
	{
		id: 'chunk', kind: 'step', tone: 'offline', x: 790, y: 75, w: 210, h: 100,
		title: 'Chunker', sub: 'soft 400 / hard 800 tokens · tables never split',
		detail: {
			what: 'Cuts each clause into passages of about 400 tokens (hard cap 800). A table becomes exactly one passage holding its full grid.',
			why: 'Passages must be small enough to rank well but never cut a table or mix two clauses.',
			points: ['A table flushes the pending text first, so reading order is kept.', 'Every passage carries spec, version, clause id, title and lineage.'],
			stat: { value: '6,124', label: 'passages: 1,568 · 2,725 · 1,831 per spec' }
		}
	},
	{
		id: 'ids', kind: 'step', tone: 'offline', x: 1050, y: 75, w: 200, h: 100,
		title: 'Chunk IDs', sub: 'sha1(spec | clause | ordinal) · deterministic'
	},
	{
		id: 'embed', kind: 'step', tone: 'offline', x: 1050, y: 225, w: 200, h: 110,
		title: 'Embed', sub: 'lineage header + text → 384-dim vector', tech: ['FastEmbed', 'BGE-small-en-v1.5'],
		detail: {
			what: 'Prefixes each passage with "Spec 24.501 17.12.0 Clause 5.5.1 Registration procedure" and embeds it into a 384-number vector.',
			why: 'The header lets a question that names a procedure find its clause even when the passage body never repeats the name.',
			points: ['Tables are embedded from a markdown rendering; the stored record keeps the original grid.'],
			stat: { value: '384', label: 'dimensions per vector, cosine distance' }
		}
	},
	{
		id: 'qdrant', kind: 'store', tone: 'offline', x: 1300, y: 215, w: 250, h: 130,
		title: 'Qdrant · 3gpp_specs', sub: '6,124 points · payload = full passage · keyword indexes on spec_id, clause_id',
		tech: ['Qdrant Cloud'],
		detail: {
			what: 'Stores one point per passage: its vector plus the whole passage as payload.',
			why: 'Filters (spec, clause) and citations read straight from the payload; no second database.',
			points: [
				'Spec and clause filters need keyword indexes on Qdrant Cloud.',
				'Version labels were fixed in place with a payload update, not a 25-minute re-index.',
				'Cloud results match local exactly (answer passage in top 5: 20/29).'
			],
			stat: { value: '6,124', label: 'points, re-indexing gives identical ids' }
		}
	},
	{
		id: 'lexicon', kind: 'step', tone: 'offline', x: 280, y: 225, w: 200, h: 110,
		title: 'Lexicon', sub: 'acronyms, long forms, clause-title bigrams, 4G/5G affinity · from the corpus'
	},
	{
		id: 'centroids', kind: 'store', tone: 'offline', x: 530, y: 225, w: 210, h: 110,
		title: 'Domain centroids', sub: 'per-spec clause centroids · .npz, rebuilt when stale'
	},
	{
		id: 'clauses', kind: 'step', tone: 'offline', x: 790, y: 225, w: 210, h: 110,
		title: 'Clause index', sub: 'every valid clause id, for prefix filters'
	},
	{
		id: 'note-ingest', kind: 'note', x: 50, y: 215, w: 180, h: 130,
		title: 'Edge cases',
		lines: ['Lists in groups → expanded', 'Clause 4.2.5a → recognised', 'Bit rows “8 7 6…” → text', 'Tables → one passage']
	},

	// ── Serving: edge ───────────────────────────────────────────
	{
		id: 'browser', kind: 'io', tone: 'query', x: 50, y: 460, w: 190, h: 100,
		title: 'Browser', sub: 'this page', tech: ['SvelteKit', 'Cloudflare Pages']
	},
	{
		id: 'api', kind: 'step', tone: 'query', x: 50, y: 640, w: 190, h: 130,
		title: 'FastAPI', sub: 'POST /api/ask/stream · Server-Sent Events · one question at a time',
		tech: ['Modal', '2 vCPU'],
		detail: {
			what: 'Turns a question into one graph run and streams an event as each step finishes.',
			why: 'The live route panel shows real progress, not a fake spinner. One run at a time fits a free 2-vCPU host.',
			points: ['Scales to zero when idle; the page wakes it on load to hide the ~20 s cold start.', 'Out of OpenRouter credit (HTTP 402) → a clear "budget used up" message.'],
			stat: { value: '0', label: 'extra LLM calls for streaming' }
		}
	},
	{
		id: 'note-edge', kind: 'note', x: 50, y: 850, w: 190, h: 150,
		title: 'At the edge',
		lines: ['Out of credit → “budget used up”', 'Cold start ~20 s → woken on page load', 'Over 500 chars → rejected', 'Provider error → clear message']
	},

	// ── LangGraph: guardrail ─────────────────────────────────────
	{
		id: 'cache', kind: 'store', tone: 'query', x: 300, y: 485, w: 200, h: 110,
		title: 'Answer cache', sub: 'same text, or cosine ≥ 0.95 and the same 3GPP terms', tech: ['SQLite'],
		detail: {
			what: 'Returns a stored answer when the same question, or a near-identical one naming exactly the same 3GPP terms, was answered before.',
			why: 'Repeats cost nothing. The term check stops "What timer does the AMF use…" from returning an MME answer.',
			points: ['Only answers labelled "answered" are stored.', 'Off in benchmarks, so every eval run exercises the full pipeline.'],
			stat: { value: '0', label: 'LLM calls on a hit' }
		}
	},
	{ id: 'd-hit', kind: 'decision', x: 545, y: 500, w: 100, h: 80, title: 'hit?' },
	{ id: 'end-hit', kind: 'end', x: 535, y: 620, w: 120, h: 36, title: 'instant answer' },
	{
		id: 'triage', kind: 'step', tone: 'query', x: 690, y: 470, w: 270, h: 140,
		title: 'Triage · 3 tiers, cheapest first',
		lines: ['① lexicon match → in scope', '② centroid cosine: < 0.595 refuse, ≥ 0.72 accept', '③ in between: one LLM yes/no · fail-open'],
		tech: ['BGE', 'thresholds swept on the eval set'],
		detail: {
			what: 'Decides whether the question is about these specs at all, using the cheapest check that can decide.',
			why: 'Off-topic questions should be refused for free, not answered with confident nonsense.',
			points: [
				'First, words: spec numbers, clause references or 3GPP terms taken from the specs themselves.',
				'Then, meaning: similarity to per-spec clause centroids; both thresholds come from a sweep over the eval set.',
				'Only if still unsure: one tiny yes/no LLM call. If anything is unavailable it fails open to retrieval.'
			],
			stat: { value: '5/5', label: 'off-topic questions refused with no LLM call' }
		}
	},
	{ id: 'd-scope', kind: 'decision', x: 1000, y: 500, w: 110, h: 80, title: 'in scope?' },
	{
		id: 'refuse', kind: 'step', tone: 'warn', x: 1150, y: 485, w: 190, h: 110,
		title: 'Refuse', sub: 'fixed reply · 0 LLM calls · ends the run'
	},
	{ id: 'd-mixed', kind: 'decision', x: 1000, y: 650, w: 110, h: 90, title: '4G + 5G terms?' },
	{
		id: 'split', kind: 'step', tone: 'query', x: 1150, y: 645, w: 210, h: 110,
		title: '4G/5G split', sub: '4G part pinned to TS 24.301 + 5G part · answer told to explain the mismatch',
		detail: {
			what: 'Spots questions that mix 4G and 5G terms (say, MME with UDM) and searches each generation separately.',
			why: 'Mixing generations is exactly where general chatbots go wrong.',
			points: [
				'Which terms are 4G or 5G is measured from the corpus: acronyms and two-word phrases like "attach request".',
				'The 4G half is searched in TS 24.301 only; results are merged round-robin.'
			],
			stat: { value: '1/8 → 3/8', label: 'traps with the answer passage in the top 5' }
		}
	},

	// ── LangGraph: retrieval ─────────────────────────────────────
	{
		id: 'parseq', kind: 'step', tone: 'query', x: 1150, y: 820, w: 210, h: 100,
		title: 'Parse query', sub: 'regex: spec number (TS 23.501), clause ref (clause 5.5.1)'
	},
	{
		id: 'filter', kind: 'step', tone: 'query', x: 900, y: 820, w: 210, h: 100,
		title: 'Clause filter', sub: 'prefix-expanded: 5.5 → 5.5 and every sub-clause'
	},
	{
		id: 'dense', kind: 'step', tone: 'query', x: 650, y: 820, w: 210, h: 100,
		title: 'Dense search', sub: 'shortlist 20 by cosine', tech: ['Qdrant']
	},
	{
		id: 'rerank', kind: 'step', tone: 'query', x: 400, y: 820, w: 210, h: 100,
		title: 'Rerank', sub: 'reads question + passage together', tech: ['Ettin 32M cross-encoder'],
		detail: {
			what: 'A cross-encoder reads the question and each shortlisted passage together and reorders the 20.',
			why: 'Vector search finds the neighbourhood; the reranker picks the passage that actually answers.',
			points: ['Replaced MiniLM-L6 after an A/B on the eval set.', 'A 40-passage shortlist was no better and twice as slow.'],
			stat: { value: '17 → 20', label: 'of 29 with the answer passage in the top 5' }
		}
	},
	{
		id: 'boost', kind: 'step', tone: 'query', x: 300, y: 975, w: 200, h: 110,
		title: 'Lineage boost', sub: '+2.0 when the question names the clause title · keep top 5'
	},
	{ id: 'd-chunks', kind: 'decision', x: 545, y: 990, w: 100, h: 80, title: 'passages?' },
	{ id: 'end-nc', kind: 'end', x: 545, y: 1105, w: 100, h: 36, title: 'not covered' },

	// ── LangGraph: answer ────────────────────────────────────────
	{
		id: 'generate', kind: 'step', tone: 'query', x: 690, y: 958, w: 270, h: 144,
		title: 'Generate · the only LLM call',
		lines: ['spec text only, exact 3GPP terms', '≤ 2,400 chars per passage · 5k-token cap', 'ends with STATUS: answered | partial | not_covered'],
		tech: ['OpenRouter', 'gpt-oss-20b', 'reasoning: low'],
		detail: {
			what: 'Writes a 3–5 sentence answer from the five passages only, and labels it.',
			why: 'One focused call keeps answers fast, cheap and tied to the text.',
			points: ['Told to say plainly what the sources don’t cover.', 'Low reasoning effort and a 5,000-token cap ended empty replies (2 of 29 before).'],
			stat: { value: '~2,300', label: 'tokens per question' }
		}
	},
	{ id: 'd-empty', kind: 'decision', x: 1000, y: 990, w: 110, h: 80, title: 'empty reply?' },
	{ id: 'end-na', kind: 'end', x: 1005, y: 1105, w: 100, h: 36, title: 'no answer' },
	{
		id: 'checks', kind: 'step', tone: 'query', x: 1150, y: 960, w: 210, h: 140,
		title: 'Answer checks · no LLM',
		lines: ['banned-phrase gate: hides retrieval jargon, 1 rephrase', 'STATUS line → label (missing → partial)', 'T3510 · #22 · ATTACH REQUEST must be in the sources'],
		detail: {
			what: 'Plain-text checks on the answer: every timer, cause code and message name must appear in the passages the model read.',
			why: 'A wrong timer is the most convincing kind of wrong answer.',
			points: ['Any unsupported identifier downgrades "answered" to "partial".', 'Word-boundary matching, so legitimate spec prose isn’t flagged.'],
			stat: { value: '0', label: 'extra LLM calls' }
		}
	},
	{
		id: 'store', kind: 'store', tone: 'query', x: 1150, y: 1120, w: 210, h: 60,
		title: 'Cache store', sub: 'only “answered”'
	},
	{
		id: 'answer', kind: 'io', tone: 'query', x: 300, y: 1120, w: 200, h: 60,
		title: 'Labelled answer', sub: 'text · label · cited clauses'
	},

	// ── Observability ────────────────────────────────────────────
	{ id: 'obs-log', kind: 'mini', x: 300, y: 1222, w: 260, h: 40, title: 'structlog', sub: 'JSON lines per node' },
	{ id: 'obs-trace', kind: 'mini', x: 580, y: 1222, w: 380, h: 40, title: 'Langfuse', sub: 'one span per node, one trace per question' },
	{ id: 'obs-run', kind: 'mini', x: 980, y: 1222, w: 400, h: 40, title: 'RunRecorder', sub: 'latency · tokens · cost per node, per eval run' }
];

const edges: MapEdge[] = [
	// Ingestion
	{ from: 'pdfs', to: 'parse', kind: 'main' },
	{ from: 'parse', to: 'tree', kind: 'main', label: 'blocks' },
	{ from: 'tree', to: 'chunk', kind: 'main', label: 'clauses' },
	{ from: 'chunk', to: 'ids', kind: 'main' },
	{ from: 'ids', to: 'embed', kind: 'main', fromSide: 'b', toSide: 't' },
	{ from: 'embed', to: 'qdrant', kind: 'main', label: 'upsert' },
	{ from: 'chunk', to: 'lexicon', kind: 'data', fromSide: 'b', toSide: 't' },
	{ from: 'chunk', to: 'centroids', kind: 'data', fromSide: 'b', toSide: 't' },
	{ from: 'chunk', to: 'clauses', kind: 'data', fromSide: 'b', toSide: 't' },

	// Ingestion → serving (data used at query time)
	{ from: 'lexicon', to: 'triage', kind: 'data', fromSide: 'b', toSide: 't', toOffset: -70, via: [[380, 382], [755, 382]] },
	{ from: 'centroids', to: 'triage', kind: 'data', fromSide: 'b', toSide: 't', toOffset: 40, via: [[635, 392], [865, 392]] },
	{ from: 'clauses', to: 'filter', kind: 'data', fromSide: 'b', toSide: 't', toOffset: -5, via: [[895, 387], [980, 387], [980, 808], [1000, 808]] },
	{ from: 'qdrant', to: 'dense', kind: 'data', fromSide: 'b', toSide: 't', label: 'vectors', via: [[1425, 790], [755, 790]] },

	// Edge
	{ from: 'browser', to: 'api', kind: 'main', fromSide: 'b', toSide: 't', fromOffset: -40, toOffset: -40, label: 'question' },
	{ from: 'api', to: 'browser', kind: 'branch', fromSide: 't', toSide: 'b', fromOffset: 40, toOffset: 40, label: 'SSE events' },
	{ from: 'api', to: 'cache', kind: 'main', fromSide: 'r', toSide: 'l', fromOffset: -30, via: [[262, 675], [262, 540]] },

	// Guardrail
	{ from: 'cache', to: 'd-hit', kind: 'main' },
	{ from: 'd-hit', to: 'triage', kind: 'main', label: 'miss', toOffset: 0 },
	{ from: 'd-hit', to: 'end-hit', kind: 'branch', fromSide: 'b', toSide: 't', label: 'hit' },
	{ from: 'triage', to: 'd-scope', kind: 'main' },
	{ from: 'd-scope', to: 'refuse', kind: 'branch', label: 'no' },
	{ from: 'd-scope', to: 'd-mixed', kind: 'main', fromSide: 'b', toSide: 't', label: 'yes' },
	{ from: 'd-mixed', to: 'split', kind: 'branch', label: 'yes' },
	{ from: 'split', to: 'parseq', kind: 'branch', fromSide: 'b', toSide: 't', fromOffset: 40, toOffset: 40, label: '2 queries' },
	{ from: 'd-mixed', to: 'parseq', kind: 'main', fromSide: 'b', toSide: 't', toOffset: -40, label: 'no' },

	// Retrieval
	{ from: 'parseq', to: 'filter', kind: 'main', fromSide: 'l', toSide: 'r' },
	{ from: 'filter', to: 'dense', kind: 'main', fromSide: 'l', toSide: 'r' },
	{ from: 'dense', to: 'rerank', kind: 'main', fromSide: 'l', toSide: 'r', label: '20' },
	{ from: 'rerank', to: 'boost', kind: 'main', fromSide: 'b', toSide: 't' },
	{ from: 'boost', to: 'd-chunks', kind: 'main', label: 'top 5' },
	{ from: 'd-chunks', to: 'generate', kind: 'main', label: 'yes' },
	{ from: 'd-chunks', to: 'end-nc', kind: 'branch', fromSide: 'b', toSide: 't', label: 'none' },

	// Answer
	{ from: 'generate', to: 'd-empty', kind: 'main' },
	{ from: 'd-empty', to: 'checks', kind: 'main', label: 'no' },
	{ from: 'd-empty', to: 'end-na', kind: 'branch', fromSide: 'b', toSide: 't', label: 'yes' },
	{ from: 'checks', to: 'store', kind: 'main', fromSide: 'b', toSide: 't' },
	{ from: 'store', to: 'answer', kind: 'main', fromSide: 'l', toSide: 'r' },
	{ from: 'answer', to: 'api', kind: 'main', fromSide: 'l', toSide: 'r', toOffset: 40, via: [[250, 1150], [250, 745]] }
];

export const pipeline = {
	eyebrow: 'How it works',
	title: 'The whole system, end to end',
	intro:
		'Ingestion builds the index once; every question then runs the serving lane. Hover to trace a path, click a box for what it does, why it exists and a measured number.',
	canvas: { width: 1600, height: 1300 },
	legend: [
		{ kind: 'main', label: 'Main path' },
		{ kind: 'branch', label: 'Branch / early exit' },
		{ kind: 'data', label: 'Data used at query time' }
	],
	/** Box shown in the detail panel before anything is clicked. */
	initial: 'triage',
	groups,
	nodes,
	edges
};
