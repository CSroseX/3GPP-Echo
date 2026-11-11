/**
 * The conversation: each message holds its question, the node events that
 * arrived for it (for the live flow panel) and the final answer.
 */

import { askStream } from '#lib/api/client';
import type { ApiError, AskResponse, NodeEvent, StreamEvent } from '#lib/api/types';
import recordings from '#lib/content/recordings.json';
import { server } from './backend.svelte';

export interface Message {
	id: number;
	question: string;
	phase: 'queued' | 'running' | 'done' | 'error';
	/** Node events by graph node name, in arrival order. */
	nodes: Record<string, NodeEvent>;
	response: AskResponse | null;
	error: ApiError | null;
	/** Replayed from a recorded run rather than run live. */
	recorded: boolean;
	startedAt: number;
}

/** A recorded run: each event with its time offset from the start (ms). */
type Recording = { events: { at: number; event: StreamEvent }[] };
const recorded = recordings as Record<string, Recording>;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

class ChatState {
	messages = $state<Message[]>([]);
	selectedId = $state<number | null>(null);
	/** Answers received so far (drives the first-answer tour). */
	answers = $state(0);
	#nextId = 1;

	get busy() {
		return this.messages.some((m) => m.phase === 'queued' || m.phase === 'running');
	}

	get selected(): Message | null {
		return this.messages.find((m) => m.id === this.selectedId) ?? this.messages.at(-1) ?? null;
	}

	select(id: number) {
		this.selectedId = id;
	}

	/** Start over (back to the suggestions). Ignored while a question runs. */
	clear() {
		if (this.busy) return;
		this.messages = [];
		this.selectedId = null;
	}

	async ask(question: string) {
		question = question.trim();
		if (!question || this.busy) return;
		this.messages.push({
			id: this.#nextId++,
			question,
			phase: 'queued',
			nodes: {},
			response: null,
			error: null,
			recorded: Boolean(recorded[question]),
			startedAt: Date.now()
		});
		// Work on the proxied entry so every change is reactive.
		const msg = this.messages[this.messages.length - 1];
		this.selectedId = msg.id;

		const events = msg.recorded ? replay(recorded[question]) : this.#live(question);
		for await (const ev of events) this.#apply(msg, ev);
		if (msg.phase !== 'error' && msg.phase !== 'done') {
			msg.phase = 'error';
			msg.error = { code: 'network', message: '' };
		}
		if (msg.phase === 'done') {
			this.answers++;
			if (!msg.recorded) void server.refreshQuota();
		}
	}

	async *#live(question: string): AsyncGenerator<StreamEvent> {
		const ok = await server.wake();
		if (!ok) {
			yield { type: 'error', data: { code: 'network', message: '' } };
			return;
		}
		yield* askStream(question);
	}

	#apply(msg: Message, ev: StreamEvent) {
		if (ev.type === 'start') {
			msg.phase = 'running';
			msg.startedAt = Date.now();
		} else if (ev.type === 'node') {
			msg.phase = 'running';
			msg.nodes[ev.data.node] = ev.data;
		} else if (ev.type === 'done') {
			msg.response = ev.data;
			msg.phase = 'done';
		} else if (ev.type === 'error') {
			msg.error = ev.data;
			msg.phase = 'error';
			if (ev.data.code === 'budget_exhausted') server.budgetExhausted = true;
		}
	}
}

async function* replay(rec: Recording): AsyncGenerator<StreamEvent> {
	let last = 0;
	for (const { at, event } of rec.events) {
		await sleep(Math.max(0, at - last));
		last = at;
		yield event;
	}
}

export const chat = new ChatState();
