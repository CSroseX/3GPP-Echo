/** Section 1: the pitch. Every visible word of the section lives here. */

export const pitch = {
	eyebrow: 'Grounded answers for 3GPP NAS and 5G core',
	headline: 'Ask the 3GPP specs. Get the clause, not a guess.',
	subline:
		'Answers questions on 5G architecture (TS 23.501), 5G NAS (TS 24.501) and 4G NAS (TS 24.301), straight from the spec text, with clause references.',
	primaryCta: { label: 'Try it', href: '#demo' },
	secondaryCta: { label: 'See how it works', href: '#pipeline' },

	problem: {
		title: 'The problem',
		body: 'The three specs share vocabulary but not meaning. General chatbots blend them; this one is built to keep them apart.',
		pairs: [
			{ a: 'GUTI', b: '5G-GUTI' },
			{ a: 'Attach', b: 'Registration' },
			{ a: 'MME', b: 'AMF' }
		]
	},

	audience: {
		title: 'Built for',
		items: [
			'Protocol and test engineers',
			'Core-network developers',
			'Engineers learning 4G/5G NAS'
		]
	},

	/** Number tiles. Keep every claim exactly as measured (see the Evals section). */
	tiles: [
		{ value: '0', unit: 'of 11', label: 'made-up answers on questions the specs don’t cover' },
		{ value: '5/5', unit: '', label: 'off-topic questions refused before any LLM call' },
		{ value: '1', unit: 'LLM call', label: 'per question, nothing more' },
		{ value: '5–7', unit: 's', label: 'median time to an answer' }
	],
	tilesNote: { label: 'How we measured this', href: '#evals' }
};
