/**
 * Guided tours: popups pinned to page elements. Each tour runs automatically
 * once per browser (remembered in localStorage) when its trigger fires.
 *
 * `target` is a `data-tour` attribute value on the element to point at.
 * Add a tour by adding an entry; put `data-tour="..."` on the element.
 */

export type TourTrigger =
	/** When the section with this id scrolls into view. */
	| { on: 'section'; section: string }
	/** After the visitor's first answer arrives. */
	| { on: 'first-answer' };

export interface TourStep {
	target: string;
	title: string;
	text: string;
	side?: 'top' | 'right' | 'bottom' | 'left';
}

export interface Tour {
	id: string;
	trigger: TourTrigger;
	steps: TourStep[];
}

export const tourSettings = {
	/** Bump to show every tour again to returning visitors. */
	version: 1,
	nextLabel: 'Next',
	prevLabel: 'Back',
	doneLabel: 'Got it',
	/** Delay after the trigger, so scrolling has settled. */
	delayMs: 600
};

export const tours: Tour[] = [
	{
		id: 'pipeline',
		trigger: { on: 'section', section: 'pipeline' },
		steps: [
			{
				target: 'group-ingest',
				title: 'Built once',
				text: 'Docling parses the three specs; every passage keeps its clause path, then lands in Qdrant as one of 6,124 points.',
				side: 'bottom'
			},
			{
				target: 'node-cache',
				title: 'Free when repeated',
				text: 'A question answered well before comes straight from the cache: instant, no LLM call.',
				side: 'bottom'
			},
			{
				target: 'node-triage',
				title: 'Off-topic stops here',
				text: 'Cheap checks first: spec words, then meaning, then a tiny LLM check only if still unsure.',
				side: 'bottom'
			},
			{
				target: 'node-d-mixed',
				title: 'The 4G/5G trap catcher',
				text: 'Questions mixing 4G and 5G terms are searched per generation, so the answer can explain the mismatch.',
				side: 'bottom'
			},
			{
				target: 'node-checks',
				title: 'No invented timers',
				text: 'Every timer, cause code and message name in the answer must appear in the sources.',
				side: 'top'
			},
			{
				target: 'pipeline-detail',
				title: 'Click any box with an i',
				text: 'The panel shows what it does, why it exists and a measured number. Hover any box to trace its arrows.',
				side: 'top'
			}
		]
	},
	{
		id: 'evals',
		trigger: { on: 'section', section: 'evals' },
		steps: [
			{
				target: 'evals-tight',
				title: 'Two runs, side by side',
				text: '“At the limit” means the result equals the target exactly: one more miss would fail the rule.',
				side: 'top'
			}
		]
	},
	{
		id: 'demo',
		trigger: { on: 'section', section: 'demo' },
		steps: [
			{
				target: 'demo-examples',
				title: 'Start with an example',
				text: 'Each one takes a different route: a normal question, a 4G/5G trap, an off-topic one and a clause lookup.',
				side: 'bottom'
			},
			{
				target: 'demo-composer',
				title: 'Or ask your own',
				text: 'Anything about TS 23.501, 24.501 or 24.301.',
				side: 'top'
			},
			{
				target: 'demo-flow',
				title: 'Watch the route',
				text: 'This panel lights up each step live as your question moves through the pipeline.',
				side: 'left'
			}
		]
	},
	{
		id: 'first-answer',
		trigger: { on: 'first-answer' },
		steps: [
			{
				target: 'answer-status',
				title: 'How far to trust it',
				text: 'Answered, partial or not covered: how much of the question the sources cover. Refused means the question is outside these specs.',
				side: 'bottom'
			},
			{
				target: 'answer-sources',
				title: 'Where it came from',
				text: 'The spec clauses the answer was written from. Open one to read the passage.',
				side: 'top'
			},
			{
				target: 'demo-flow',
				title: 'The route it took',
				text: 'Each step shows one real fact from this run.',
				side: 'left'
			}
		]
	}
];
