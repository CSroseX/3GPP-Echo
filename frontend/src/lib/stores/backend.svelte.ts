/** Backend reachability and the demo budget, shared across the page. */

import { health, quota } from '#lib/api/client';

export type ServerStatus = 'unknown' | 'waking' | 'ready' | 'offline';

class ServerState {
	status = $state<ServerStatus>('unknown');
	budgetUsd = $state<number | null>(null);
	budgetExhausted = $state(false);
	#waking: Promise<boolean> | null = null;

	/** Ping the backend until it answers (a cold start takes ~20–26 s). */
	wake(): Promise<boolean> {
		if (this.status === 'ready') return Promise.resolve(true);
		if (this.#waking) return this.#waking;
		this.status = 'waking';
		this.#waking = (async () => {
			const ok = await health(60_000);
			this.status = ok ? 'ready' : 'offline';
			this.#waking = null;
			if (ok) void this.refreshQuota();
			return ok;
		})();
		return this.#waking;
	}

	async refreshQuota() {
		const q = await quota();
		if (!q) return;
		this.budgetUsd = q.budget_remaining_usd;
		this.budgetExhausted = q.budget_exhausted;
	}
}

export const server = new ServerState();
