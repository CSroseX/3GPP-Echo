/**
 * Record each example question's live run once, so the demo can replay it
 * for free with its original timing (src/lib/content/recordings.json).
 *
 *   node scripts/record-examples.ts [apiBase]        (default http://localhost:8000)
 *
 * Spends real LLM tokens: one call per in-scope example (off-topic ones are free).
 * Re-run after changing the examples in src/lib/content/demo.ts.
 */

import { writeFileSync } from 'node:fs';
import { demo, exampleQuestion } from '../src/lib/content/demo.ts';

const apiBase = (process.argv[2] ?? 'http://localhost:8000').replace(/\/$/, '');
const out = new URL('../src/lib/content/recordings.json', import.meta.url);

type Recorded = { at: number; event: { type: string; data?: unknown } };

async function record(question: string): Promise<Recorded[]> {
	const r = await fetch(`${apiBase}/api/ask/stream`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ question })
	});
	if (!r.ok || !r.body) throw new Error(`HTTP ${r.status} for: ${question}`);
	const t0 = Date.now();
	const events: Recorded[] = [];
	const decoder = new TextDecoder();
	let buffer = '';
	for await (const chunk of r.body) {
		buffer += decoder.decode(chunk, { stream: true });
		let cut: number;
		while ((cut = buffer.indexOf('\n\n')) !== -1) {
			const block = buffer.slice(0, cut);
			buffer = buffer.slice(cut + 2);
			const type = /^event: (.+)$/m.exec(block)?.[1];
			const data = /^data: (.+)$/m.exec(block)?.[1];
			if (!type) continue;
			const event = type === 'start' ? { type } : { type, data: JSON.parse(data ?? '{}') };
			events.push({ at: Date.now() - t0, event });
		}
	}
	const last = events.at(-1)?.event.type;
	if (last !== 'done') throw new Error(`Run did not finish (${last}) for: ${question}`);
	return events;
}

const recordings: Record<string, { events: Recorded[] }> = {};
for (const ex of demo.examples) {
	const q = exampleQuestion(ex);
	process.stdout.write(`Recording: ${q} … `);
	recordings[q] = { events: await record(q) };
	const done = recordings[q].events.at(-1)!.event.data as { status: string };
	console.log(done.status);
}
writeFileSync(out, JSON.stringify(recordings, null, '\t') + '\n');
console.log(`Wrote ${Object.keys(recordings).length} recordings to ${out.pathname}`);
