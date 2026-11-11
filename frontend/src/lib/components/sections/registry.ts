/**
 * Maps section ids (config/site.ts `sections`) to their components.
 * A new section = a component + one line here + its id in `sections`.
 */

import type { Component } from 'svelte';
import type { SectionId } from '#lib/config/site';
import Demo from './Demo.svelte';
import Evals from './Evals.svelte';
import Pipeline from './Pipeline.svelte';
import Pitch from './Pitch.svelte';

export const registry: Partial<Record<SectionId, Component>> = {
	pitch: Pitch,
	pipeline: Pipeline,
	evals: Evals,
	demo: Demo
};
