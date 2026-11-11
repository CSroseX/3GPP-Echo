/**
 * Runs the guided tours from content/tours.ts with Driver.js. Each tour shows
 * once per browser; elements are found by their `data-tour` attribute.
 */

import { driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';
import { tours, tourSettings, type Tour } from '#lib/content/tours';

const storageKey = (id: string) => `tour:${tourSettings.version}:${id}`;

function seen(id: string): boolean {
	try {
		return localStorage.getItem(storageKey(id)) === '1';
	} catch {
		return false;
	}
}

function markSeen(id: string) {
	try {
		localStorage.setItem(storageKey(id), '1');
	} catch {
		/* private mode: the tour may show again, that's fine */
	}
}

let running = false;

/** The first visible element with this data-tour value (some exist twice, e.g. desktop and phone layouts). */
function visibleTarget(target: string): Element | null {
	const els = document.querySelectorAll<HTMLElement>(`[data-tour="${target}"]`);
	return Array.from(els).find((el) => el.offsetParent !== null || el.getClientRects().length > 0) ?? null;
}

/** Start a tour now (if not seen). If another tour is open, try again shortly. */
export function runTour(tour: Tour, force = false) {
	if (!force && seen(tour.id)) return;
	if (running) {
		setTimeout(() => runTour(tour, force), 1500);
		return;
	}
	const steps: DriveStep[] = tour.steps
		.map((s) => ({ s, el: visibleTarget(s.target) }))
		.filter(({ el }) => el)
		.map(({ s, el }) => ({
			element: el as Element,
			popover: { title: s.title, description: s.text, side: s.side ?? 'bottom', align: 'center' }
		}));
	if (!steps.length) return;

	running = true;
	markSeen(tour.id);
	const d = driver({
		steps,
		showProgress: steps.length > 1,
		progressText: '{{current}} of {{total}}',
		nextBtnText: tourSettings.nextLabel,
		prevBtnText: tourSettings.prevLabel,
		doneBtnText: tourSettings.doneLabel,
		popoverClass: 'echo-tour',
		smoothScroll: true,
		allowClose: true,
		onDestroyed: () => {
			running = false;
		}
	});
	d.drive();
}

/** Start the tour for a trigger after the configured delay. */
export function trigger(match: (t: Tour) => boolean) {
	const tour = tours.find(match);
	if (!tour || seen(tour.id)) return;
	setTimeout(() => runTour(tour), tourSettings.delayMs);
}

/**
 * Fire each section tour the first time its first target is well on screen
 * (inside the middle 60% of the viewport), so the popup never points at
 * something the visitor can't see and the page never scrolls on its own.
 */
export function watchSections(): () => void {
	const byElement = new Map<Element, Tour>();
	const observer = new IntersectionObserver(
		(entries) => {
			for (const e of entries) {
				if (!e.isIntersecting) continue;
				const tour = byElement.get(e.target);
				observer.unobserve(e.target);
				if (tour) setTimeout(() => runTour(tour), tourSettings.delayMs);
			}
		},
		{ threshold: 0, rootMargin: '-20% 0px -20% 0px' }
	);
	for (const t of tours) {
		if (t.trigger.on !== 'section' || seen(t.id)) continue;
		const el = visibleTarget(t.steps[0].target) ?? document.getElementById(t.trigger.section);
		if (!el) continue;
		byElement.set(el, t);
		observer.observe(el);
	}
	return () => observer.disconnect();
}

/** For a "replay tours" control: forget every tour so they show again. */
export function resetTours() {
	for (const t of tours) {
		try {
			localStorage.removeItem(storageKey(t.id));
		} catch {
			/* ignore */
		}
	}
}
