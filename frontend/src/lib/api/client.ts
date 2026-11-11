/**
 * Backend client. The only module that knows URLs and wire formats.
 */

import { site } from '#lib/config/site';
import type { ApiError, Quota, StreamEvent } from './types';

const url = (path: string) => `${site.apiBase.replace(/\/$/, '')}${path}`;

/** True when the backend answers its health check within `timeoutMs`. */
export async function health(timeoutMs = 60_000): Promise<boolean> {
	try {
		const r = await fetch(url('/api/health'), { signal: AbortSignal.timeout(timeoutMs) });
		return r.ok;
	} catch {
		return false;
	}
}

export async function quota(): Promise<Quota | null> {
	try {
		const r = await fetch(url('/api/quota'));
		return r.ok ? ((await r.json()) as Quota) : null;
	} catch {
		return null;
	}
}

/**
 * Ask a question and receive the pipeline's events as they happen.
 * POST + Server-Sent Events over fetch (EventSource can't POST).
 */
export async function* askStream(question: string, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
	let r: Response;
	try {
		r = await fetch(url('/api/ask/stream'), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
			body: JSON.stringify({ question }),
			signal
		});
	} catch {
		yield { type: 'error', data: { code: 'network', message: '' } };
		return;
	}

	if (!r.ok || !r.body) {
		let err: ApiError = { code: 'default', message: '' };
		try {
			const body = await r.json();
			if (body?.detail?.code) err = body.detail;
		} catch {
			/* keep the default */
		}
		yield { type: 'error', data: err };
		return;
	}

	const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
	let buffer = '';
	try {
		while (true) {
			const { value, done } = await reader.read();
			if (done) break;
			buffer += value;
			let cut: number;
			while ((cut = buffer.indexOf('\n\n')) !== -1) {
				const block = buffer.slice(0, cut);
				buffer = buffer.slice(cut + 2);
				const event = parseBlock(block);
				if (event) yield event;
			}
		}
	} catch {
		yield { type: 'error', data: { code: 'network', message: '' } };
	}
}

function parseBlock(block: string): StreamEvent | null {
	let type = '';
	let data = '';
	for (const line of block.split('\n')) {
		if (line.startsWith('event: ')) type = line.slice(7).trim();
		else if (line.startsWith('data: ')) data += line.slice(6);
	}
	if (!type) return null;
	const parsed = data ? JSON.parse(data) : {};
	if (type === 'start') return { type: 'start' };
	if (type === 'node' || type === 'done' || type === 'error') return { type, data: parsed } as StreamEvent;
	return null;
}
