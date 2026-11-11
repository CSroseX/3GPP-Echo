/**
 * Section 4: the demo. Example questions, the live flow panel's steps, answer
 * labels and every message the demo shows.
 */

import type { NodeFacts } from '#lib/api/types';

// Kept local (no runtime #lib imports) so scripts/record-examples.ts can load this file in plain Node.
const seconds = (ms: number) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);

export interface Example {
	/** Bold first line of the suggestion card. */
	lead: string;
	/** Muted second line. The question sent is `${lead} ${rest}`. */
	rest: string;
}

export const exampleQuestion = (e: Example) => `${e.lead} ${e.rest}`;

/**
 * One step in the live flow panel. `nodes` are the backend graph nodes that
 * complete it; `fact` turns their facts into the one line shown under it.
 * Return null from `when` to hide the step for this question.
 */
export interface FlowStepConfig {
	id: string;
	title: string;
	nodes: string[];
	fact: (f: NodeFacts, ms: number) => string;
	when?: (all: Record<string, NodeFacts>) => boolean;
}

const list = (xs: string[] | undefined, n = 3) => (xs ?? []).slice(0, n).map((x) => `“${x}”`).join(', ');

export const demo = {
	eyebrow: 'Try it',
	title: 'Ask the specs',
	intro: 'Ask anything about the three specs. The Live route panel shows the path your question takes through the pipeline, step by step.',

	chat: {
		title: '3GPP Echo',
		greeting: 'What would you like to know about the specs?',
		newChat: 'New chat',
		disclaimer: 'Answers come only from TS 23.501, 24.501 and 24.301. Check the cited clauses.'
	},

	examples: [
		{ lead: 'What is the role of the AMF', rest: 'in the 5G system architecture?' },
		{ lead: 'When an MME receives an Attach Request,', rest: 'does it communicate with the UDM?' },
		{ lead: 'Who won the World Cup', rest: 'in 2022?' },
		{ lead: 'Per TS 24.501 clause 5.5.1.2.2,', rest: 'how does the UE initiate initial registration?' }
	] satisfies Example[],

	composer: {
		placeholder: 'Ask about 5G architecture, 5G NAS or 4G NAS…',
		send: 'Send',
		maxChars: 500
	},

	flow: {
		title: 'Live route',
		empty: 'Ask a question to see its route through the pipeline.',
		recorded: 'Recorded run',
		steps: [
			{
				id: 'cache',
				title: 'Answer cache',
				nodes: ['cache_lookup'],
				fact: (f) => (f.hit ? `Hit (${f.hit} match), answered instantly` : 'Miss: not asked before')
			},
			{
				id: 'triage',
				title: 'Triage',
				nodes: ['triage'],
				fact: (f) => {
					if (f.decision === 'out_of_domain') return 'Off-topic: refused, no LLM call';
					if (f.matched?.length) return `In scope: matched ${list(f.matched)}`;
					return `In scope (${f.tier === 'llm' ? 'LLM check' : 'meaning check'})`;
				}
			},
			{
				id: 'split',
				title: '4G/5G split',
				nodes: ['triage'],
				when: (all) => Boolean(all.triage?.mixed_generation),
				fact: (f) => `4G ${list(f.terms_4g, 2)} and 5G ${list(f.terms_5g, 2)}: searched separately`
			},
			{
				id: 'refuse',
				title: 'Refused',
				nodes: ['refuse'],
				when: (all) => all.triage?.decision === 'out_of_domain',
				fact: () => 'Fixed reply: outside these specs'
			},
			{
				id: 'retrieve',
				title: 'Retrieve',
				nodes: ['retrieve'],
				when: (all) => all.triage?.decision !== 'out_of_domain' && !all.cache_lookup?.hit,
				fact: (f, ms) => {
					const specs = Object.entries(f.specs ?? {})
						.map(([s, n]) => `${n} from TS ${s}`)
						.join(', ');
					return `${f.count ?? 0} passages${specs ? `: ${specs}` : ''} · ${seconds(ms)}`;
				}
			},
			{
				id: 'generate',
				title: 'Generate',
				nodes: ['generate'],
				when: (all) => all.triage?.decision !== 'out_of_domain' && !all.cache_lookup?.hit,
				fact: (f, ms) => `One LLM call · ${seconds(ms)}`
			},
			{
				id: 'check',
				title: 'Identifier check',
				nodes: ['generate'],
				when: (all) => all.triage?.decision !== 'out_of_domain' && !all.cache_lookup?.hit,
				fact: (f) =>
					f.unsupported_identifiers?.length
						? `Not in sources: ${list(f.unsupported_identifiers)} → label lowered`
						: 'All identifiers found in the sources'
			}
		] satisfies FlowStepConfig[]
	},

	/** Answer labels: text and colour variables from theme/tokens.css. */
	status: {
		answered: { label: 'Answered', color: 'var(--ok)', soft: 'var(--ok-soft)', hint: 'The sources cover the whole question.' },
		partial: { label: 'Partial', color: 'var(--warn)', soft: 'var(--warn-soft)', hint: 'The sources cover part of the question.' },
		not_covered: { label: 'Not covered', color: 'var(--neutral)', soft: 'var(--neutral-soft)', hint: 'The sources don’t cover this.' },
		no_answer: { label: 'No answer', color: 'var(--neutral)', soft: 'var(--neutral-soft)', hint: 'The model returned no text. Try again.' },
		out_of_domain: { label: 'Refused', color: 'var(--stop)', soft: 'var(--stop-soft)', hint: 'Outside TS 23.501, 24.501 and 24.301.' }
	} as Record<string, { label: string; color: string; soft: string; hint: string }>,

	sources: { title: 'Sources', excerptLines: 4 },

	server: {
		waking: 'Waking the server up (about 20 seconds, only after it has been idle)…',
		ready: 'Server ready',
		offline: 'The server can’t be reached right now. Please try again in a minute.'
	},

	errors: {
		budget_exhausted: 'The demo’s question budget is used up. Thanks for trying it!',
		llm_error: 'The language model is unavailable right now. Please try again shortly.',
		network: 'Lost the connection to the server. Please try again.',
		default: 'Something went wrong. Please try again.'
	} as Record<string, string>,

	quota: {
		budget: (usd: number) => `Demo budget left: $${usd.toFixed(2)}`
	}
};
