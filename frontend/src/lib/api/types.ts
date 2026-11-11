/** Shapes of the backend API (src/api/main.py, src/api/events.py). */

export interface Source {
	spec_id: string | null;
	version: string | null;
	clause_id: string | null;
	clause_title: string | null;
	chunk_type: string | null;
	excerpt: string;
}

export interface AskResponse {
	answer: string;
	/** answered | partial | not_covered | no_answer | out_of_domain */
	status: string | null;
	cached: boolean;
	sources: Source[];
}

/** Facts one node reports; which keys appear depends on the node. */
export interface NodeFacts {
	hit?: string | null;
	decision?: string;
	tier?: string;
	matched?: string[];
	mixed_generation?: boolean;
	terms_4g?: string[];
	terms_5g?: string[];
	count?: number;
	specs?: Record<string, number>;
	clauses?: string[];
	status?: string | null;
	unsupported_identifiers?: string[];
}

export interface NodeEvent {
	node: string;
	ms: number;
	facts: NodeFacts;
}

export interface ApiError {
	code: string;
	message: string;
}

export type StreamEvent =
	| { type: 'start' }
	| { type: 'node'; data: NodeEvent }
	| { type: 'done'; data: AskResponse }
	| { type: 'error'; data: ApiError };

export interface Quota {
	budget_remaining_usd: number | null;
	budget_exhausted: boolean;
}
