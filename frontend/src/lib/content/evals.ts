/**
 * Section 3: evals. Numbers come from docs/release-criteria.md (two full runs
 * on 2026-11-09) and DECISIONS.md; update them here after a new run.
 */

export type CriterionStatus = 'met' | 'tight' | 'missed';

export interface Criterion {
	label: string;
	target: string;
	run1: string;
	run2: string;
	status: CriterionStatus;
}

export const evals = {
	eyebrow: 'Evals',
	title: 'Measured, not claimed',
	intro:
		'Every change was measured against a fixed set of questions with known answers, in two full runs.',

	testSet: {
		title: 'The test set',
		total: 40,
		groups: [
			{ count: 21, label: 'normal questions', example: 'What is the role of the AMF in the 5G system architecture?' },
			{ count: 8, label: '4G/5G traps', example: 'When an MME receives an Attach Request, does it communicate with the UDM?' },
			{ count: 11, label: 'questions the specs don’t cover', example: 'How many HARQ processes does the NR MAC support in the downlink?' }
		]
	},

	criteria: {
		title: 'Release criteria',
		caption: 'Two full runs, same code and settings. The demo ships when every rule holds in both.',
		/** Shown under the table. */
		note: '“At the limit” means the result equals the target exactly: one more miss would fail the rule.',
		statusLabels: { met: 'Met', tight: 'Met · at the limit', missed: 'Not met' } as Record<CriterionStatus, string>,
		rows: [
			{ label: 'Original 6 normal questions answered correctly', target: '≥ 4/6', run1: '5/6', run2: '4/6', status: 'tight' },
			{ label: 'All 21 normal questions answered correctly', target: '≥ 15/21', run1: '15/21', run2: '15/21', status: 'tight' },
			{ label: '4G/5G traps answered correctly', target: '≥ 4/8', run1: '4/8', run2: '4/8', status: 'tight' },
			{ label: 'Obvious off-topic questions refused, no LLM call', target: '5/5', run1: '5/5', run2: '5/5', status: 'met' },
			{ label: 'Made-up answers to questions the specs don’t cover', target: '0/11', run1: '0/11', run2: '0/11', status: 'met' },
			{ label: 'Empty answers', target: '≤ 1', run1: '0', run2: '0', status: 'met' },
			{ label: 'Answer time, median / 95th percentile', target: '< 15 s / < 40 s', run1: '5.2 / 7.2 s', run2: '7.1 / 11.6 s', status: 'met' },
			{ label: 'Tokens per question that reaches the LLM', target: '< 3,000', run1: '~2,270', run2: '~2,290', status: 'met' }
		] as Criterion[]
	},

	progress: {
		title: 'Search quality over time',
		caption: 'Questions with the answer passage in the top 5 results (of 29).',
		max: 29,
		steps: [
			{ value: 15, label: 'Question searched as typed' },
			{ value: 17, label: '+ 4G/5G split searches' },
			{ value: 20, label: '+ stronger reranker model' }
		]
	},

	limits: {
		title: 'Known limits',
		items: [
			'8 of the 9 missed answers never reach the top 20 search results; a stronger search model is the next step.',
			'The answer label is the model’s own judgement, backed by the identifier check, not an independent review.',
			'Three rules pass at the limit: one changed answer would break them.'
		]
	},

	dropped: {
		title: 'Tried and dropped',
		items: [
			{ what: 'A second LLM to verify each answer', why: 'It read the same passages, cost a second call and rejected correct answers on the 4G/5G traps.' },
			{ what: 'Keyword search mixed with meaning search', why: 'With the current reranker it lowered results.' },
			{ what: 'Doubling the reranker shortlist to 40', why: 'No better, twice as slow.' }
		]
	}
};
