/**
 * Site-wide settings. Change section order, nav links or the backend URL here;
 * no component needs editing.
 */

/** The person behind the project: shown in the hero and the footer. Empty links are hidden. */
export const author = {
	name: 'Chitransh',
	role: 'Built and measured by',
	github: 'https://github.com/CSroseX',
	linkedin: ''
};

const repo = 'https://github.com/CSroseX/3GPP-Echo';

/** Footer columns. Add, remove or reorder freely. */
export const footer = {
	tagline: 'Grounded answers from 3GPP TS 23.501, 24.501 and 24.301, with clause references. Not affiliated with 3GPP.',
	columns: [
		{
			title: 'Project',
			links: [
				{ label: 'Source code', href: repo },
				{ label: 'Design decisions', href: `${repo}/blob/main/DECISIONS.md` },
				{ label: 'Release criteria', href: `${repo}/blob/main/docs/release-criteria.md` },
				{ label: 'Hardening plan', href: `${repo}/blob/main/docs/production-hardening-plan.md` }
			]
		},
		{
			title: 'The specs',
			links: [
				{ label: 'TS 23.501 · 5G system', href: 'https://www.3gpp.org/DynaReport/23501.htm' },
				{ label: 'TS 24.501 · 5G NAS', href: 'https://www.3gpp.org/DynaReport/24501.htm' },
				{ label: 'TS 24.301 · 4G NAS', href: 'https://www.3gpp.org/DynaReport/24301.htm' }
			]
		},
		{
			title: 'Built with',
			links: [
				{ label: 'Docling · parsing', href: 'https://github.com/docling-project/docling' },
				{ label: 'Qdrant · vector search', href: 'https://qdrant.tech' },
				{ label: 'LangGraph · orchestration', href: 'https://github.com/langchain-ai/langgraph' },
				{ label: 'FastAPI · Modal · SvelteKit', href: 'https://svelte.dev/docs/kit' }
			]
		}
	]
};

export const site = {
	name: '3GPP Echo',
	/** Backend base URL; set VITE_API_BASE in frontend/.env (see .env.example). */
	apiBase: (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000',
	repoUrl: 'https://github.com/CSroseX/3GPP-Echo',
	/** Wake the backend on page load so it is warm by the time the visitor reaches the demo. */
	wakeOnLoad: true
};

/** Page sections, top to bottom. Remove or reorder entries to change the page. */
export const sections = ['pitch', 'pipeline', 'evals', 'demo'] as const;
export type SectionId = (typeof sections)[number];

/** Nav links. `href` is a section anchor (#id) or a full URL. */
export const nav: { label: string; href: string; external?: boolean }[] = [
	{ label: 'Pipeline', href: '#pipeline' },
	{ label: 'Evals', href: '#evals' },
	{ label: 'Try it', href: '#demo' },
	{ label: 'GitHub', href: 'https://github.com/CSroseX/3GPP-Echo', external: true }
];
