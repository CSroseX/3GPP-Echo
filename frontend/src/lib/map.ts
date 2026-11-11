/** Geometry for the system map: right-angled arrow routes between boxes. */

import type { MapEdge, MapNode, Side } from '#lib/content/pipeline';

type Pt = [number, number];

function anchor(n: MapNode, side: Side, offset = 0): Pt {
	switch (side) {
		case 'r':
			return [n.x + n.w, n.y + n.h / 2 + offset];
		case 'l':
			return [n.x, n.y + n.h / 2 + offset];
		case 't':
			return [n.x + n.w / 2 + offset, n.y];
		case 'b':
			return [n.x + n.w / 2 + offset, n.y + n.h];
	}
}

/** Pick sides from relative position when the edge doesn't name them. */
function sides(a: MapNode, b: MapNode): [Side, Side] {
	const dx = b.x + b.w / 2 - (a.x + a.w / 2);
	const dy = b.y + b.h / 2 - (a.y + a.h / 2);
	const overlapY = Math.abs(dy) < (a.h + b.h) / 2;
	if (overlapY) return dx >= 0 ? ['r', 'l'] : ['l', 'r'];
	return dy >= 0 ? ['b', 't'] : ['t', 'b'];
}

const horizontal = (s: Side) => s === 'r' || s === 'l';

export interface Route {
	d: string;
	points: Pt[];
	label: Pt | null;
}

export function route(e: MapEdge, byId: Map<string, MapNode>): Route | null {
	const a = byId.get(e.from);
	const b = byId.get(e.to);
	if (!a || !b) return null;
	const [s1, s2] = e.fromSide && e.toSide ? [e.fromSide, e.toSide] : sides(a, b);
	const p1 = anchor(a, e.fromSide ?? s1, e.fromOffset);
	const p2 = anchor(b, e.toSide ?? s2, e.toOffset);

	let pts: Pt[];
	if (e.via?.length) pts = [p1, ...e.via, p2];
	else if (horizontal(s1) && horizontal(s2)) {
		const mx = (p1[0] + p2[0]) / 2;
		pts = Math.abs(p1[1] - p2[1]) < 1 ? [p1, p2] : [p1, [mx, p1[1]], [mx, p2[1]], p2];
	} else if (!horizontal(s1) && !horizontal(s2)) {
		const my = (p1[1] + p2[1]) / 2;
		pts = Math.abs(p1[0] - p2[0]) < 1 ? [p1, p2] : [p1, [p1[0], my], [p2[0], my], p2];
	} else if (horizontal(s1)) pts = [p1, [p2[0], p1[1]], p2];
	else pts = [p1, [p1[0], p2[1]], p2];

	// Label at the middle of the longest segment.
	let best = -1;
	let label: Pt | null = null;
	for (let i = 0; i < pts.length - 1; i++) {
		const [x1, y1] = pts[i];
		const [x2, y2] = pts[i + 1];
		const len = Math.abs(x2 - x1) + Math.abs(y2 - y1);
		if (len > best) {
			best = len;
			label = [(x1 + x2) / 2, (y1 + y2) / 2];
		}
	}
	return { d: 'M' + pts.map((p) => p.join(' ')).join(' L'), points: pts, label: e.label ? label : null };
}
