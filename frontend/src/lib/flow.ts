/**
 * Turns a message's node events into the live flow panel's steps, using the
 * step definitions in content/demo.ts.
 */

import type { NodeFacts } from '#lib/api/types';
import type { FlowStepConfig } from '#lib/content/demo';
import type { Message } from '#lib/stores/chat.svelte';

export type StepState = 'pending' | 'active' | 'done';

export interface FlowStep {
	id: string;
	title: string;
	state: StepState;
	fact: string | null;
	ms: number | null;
}

export function flowSteps(msg: Message, config: FlowStepConfig[]): FlowStep[] {
	const facts: Record<string, NodeFacts> = {};
	for (const [node, ev] of Object.entries(msg.nodes)) facts[node] = ev.facts;

	const visible = config.filter((s) => (s.when ? s.when(facts) : true));
	const running = msg.phase === 'queued' || msg.phase === 'running';
	let activeAssigned = false;

	return visible.map((s) => {
		const evs = s.nodes.map((n) => msg.nodes[n]);
		const complete = evs.every(Boolean);
		if (complete) {
			// A step fed by several nodes uses the last node's facts.
			const last = evs[evs.length - 1]!;
			const ms = evs.reduce((sum, e) => sum + (e?.ms ?? 0), 0);
			return { id: s.id, title: s.title, state: 'done', fact: s.fact(last.facts, ms), ms };
		}
		let state: StepState = 'pending';
		if (running && !activeAssigned) {
			state = 'active';
			activeAssigned = true;
		}
		return { id: s.id, title: s.title, state, fact: null, ms: null };
	});
}

/** "14 ms" under a second, "5.8 s" above. */
export function formatMs(ms: number): string {
	return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** Total time of a run so far, from its node events. */
export function totalMs(msg: Message): number {
	return Object.values(msg.nodes).reduce((sum, e) => sum + e.ms, 0);
}
