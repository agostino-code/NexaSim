import type { RatType } from '../types/scenario';

/**
 * NexaSim Studio — semantic colour system (single source of truth).
 *
 * The 2D map, the 3D globe, the legends, the fleet matrix and the system
 * strip all derive from these constants, so the operator reads every view
 * with the same colour language.
 *
 * Meaning is fixed:
 *  - green  -> terrestrial 5G-NR
 *  - cyan   -> LEO satellite / space segment
 *  - purple -> V2X sidelink
 *  - slate  -> link state NOT recorded (never a guess)
 *  - amber  -> warning (vehicle inside a blind spot)
 *  - red    -> blind-spot zone geometry
 *  - orange -> ground gateways
 */
export const RAT_COLORS: Record<RatType, string> = {
  '5G': '#10b981', // emerald — 5G-NR terrestrial
  LEO: '#38bdf8', // cyan — LEO satellite
  V2X: '#a855f7', // purple — V2X sidelink
};

export const RAT_LABELS: Record<RatType, string> = {
  '5G': '5G-NR Terrestrial',
  LEO: 'Satellite LEO',
  V2X: 'V2X Sidelink',
};

/** Link state was not recorded by the simulation — rendered slate, never guessed. */
export const UNKNOWN_LINK_COLOR = '#64748b';
/** Blind-spot zone geometry (danger area on the ground). */
export const BLIND_SPOT_COLOR = '#ef4444';
/** Warning state: a vehicle currently inside a blind spot. */
export const WARNING_COLOR = '#f59e0b';
/** Terrestrial base station. */
export const GNB_COLOR = '#10b981';
/** NTN ground gateway (distinct orange, so amber stays reserved for warnings). */
export const GATEWAY_COLOR = '#fb923c';
/** LEO satellite / space segment. */
export const SAT_COLOR = '#38bdf8';
/** Recorded route corridor (neutral, no semantics). */
export const ROUTE_COLOR = '#94a3b8';
/** Geometric serving-link estimate drawn on the 2D map (explicitly derived). */
export const LINK_DERIVED_COLOR = '#cbd5e1';
/** Phased-array beam / ISL glow. */
export const BEAM_COLOR = '#38bdf8';

/** Neutral non-recorded colour for charts / cards. */
export const NOT_RECORDED_COLOR = '#64748b';

export function ratColor(rat: RatType | null | undefined): string {
  return rat ? RAT_COLORS[rat] : UNKNOWN_LINK_COLOR;
}

export function ratLabel(rat: RatType | null | undefined): string {
  return rat ? RAT_LABELS[rat] : 'Link not recorded';
}

export interface LegendEntry {
  color: string;
  label: string;
  kind?: 'dot' | 'ring' | 'square' | 'line' | 'dashed';
}

/** Canonical legend for the 2D tactical map. */
export const MAP_LEGEND: LegendEntry[] = [
  { color: RAT_COLORS['5G'], label: 'Vehicle — 5G link', kind: 'dot' },
  { color: RAT_COLORS.LEO, label: 'Vehicle — LEO link', kind: 'dot' },
  { color: RAT_COLORS.V2X, label: 'Vehicle — V2X', kind: 'dot' },
  { color: UNKNOWN_LINK_COLOR, label: 'Link not recorded', kind: 'dot' },
  { color: WARNING_COLOR, label: 'Inside blind spot', kind: 'dot' },
  { color: BLIND_SPOT_COLOR, label: 'Blind-spot zone', kind: 'square' },
  { color: GNB_COLOR, label: '5G gNodeB (+ coverage)', kind: 'ring' },
  { color: GATEWAY_COLOR, label: 'LEO gateway', kind: 'ring' },
  { color: ROUTE_COLOR, label: 'Recorded route', kind: 'dashed' },
  { color: LINK_DERIVED_COLOR, label: 'Derived link (nearest node by RAT)', kind: 'dashed' },
];

/** Canonical legend for the 3D globe HUD. */
export const GLOBE_LEGEND: LegendEntry[] = [
  { color: SAT_COLOR, label: 'LEO satellites', kind: 'dot' },
  { color: BEAM_COLOR, label: 'Phased-array / ISL', kind: 'line' },
  { color: GNB_COLOR, label: '5G gNodeB', kind: 'dot' },
  { color: GATEWAY_COLOR, label: 'Ground gateway', kind: 'dot' },
  { color: RAT_COLORS['5G'], label: 'Vehicle — 5G link', kind: 'dot' },
  { color: RAT_COLORS.LEO, label: 'Vehicle — LEO link', kind: 'dot' },
  { color: UNKNOWN_LINK_COLOR, label: 'Vehicle — link n/r', kind: 'dot' },
  { color: SAT_COLOR, label: 'Serving sat (highlight)', kind: 'ring' },
];
