import { create } from 'zustand';
import {
  ScenarioSummary,
  SimStatus,
  VehicleTelemetry,
  GnbSite,
  GroundStationSite,
  BlindSpotZone,
  LiveTelemetryFrame,
  TelemetrySeries,
  KpiSummary,
  RatType,
} from '../types/scenario';

export type SelectedNodeType = 'gnb' | 'gs' | 'blind' | 'veh';

export interface SelectedNode {
  type: SelectedNodeType;
  index: number;
  data: any;
}

/** One-shot "fly to node" request consumed by the 2D map / 3D globe. */
export interface FlyToRequest {
  target: SelectedNodeType;
  index: number;
  lat: number;
  lon: number;
  /** Monotonic nonce so repeated requests to the same node re-trigger. */
  nonce: number;
}

interface StudioState {
  scenarios: ScenarioSummary[];
  currentScenario: ScenarioSummary | null;
  status: SimStatus;
  logs: string[];
  simTime: number;
  isPlaying: boolean;
  playbackSpeed: number;
  selectedNode: SelectedNode | null;
  // Fleet aggregates: null until a recorded run or live frame provides them
  throughputMbps: number | null;
  latencyMs: number | null;
  activeRat: string | null;
  vehicles: VehicleTelemetry[];
  wsConnected: boolean;

  /** One-shot fly-to request for the viewports (nonce-guarded). */
  flyToRequest: FlyToRequest | null;
  /** Data provenance modal visibility (global: opened from Header or Dashboard). */
  provenanceOpen: boolean;

  // Real telemetry series from /api/telemetry (parsed .vec / KPI data)
  telemetrySeries: TelemetrySeries | null;
  kpis: KpiSummary | null;
  hasRunData: boolean;

  // Actions
  setScenarios: (scenarios: ScenarioSummary[]) => void;
  selectScenario: (scenario: ScenarioSummary) => void;
  setStatus: (status: SimStatus) => void;
  appendLog: (log: string) => void;
  appendLogs: (logs: string[]) => void;
  clearLogs: () => void;
  setSimTime: (time: number) => void;
  togglePlay: () => void;
  setPlaybackSpeed: (speed: number) => void;
  selectNode: (node: SelectedNode | null) => void;
  updateNode: (type: SelectedNodeType, index: number, updatedData: any) => void;
  addNode: (type: Exclude<SelectedNodeType, 'veh'>, data: any) => void;
  removeNode: (type: SelectedNodeType, index: number) => void;
  requestFlyTo: (target: SelectedNodeType, index: number, lat: number, lon: number) => void;
  setProvenanceOpen: (open: boolean) => void;
  setWsConnected: (connected: boolean) => void;
  updateLiveTelemetry: (frame: Partial<LiveTelemetryFrame>) => void;
  setTelemetrySeries: (series: TelemetrySeries) => void;
  setKpis: (kpis: KpiSummary) => void;
  setHasRunData: (hasData: boolean) => void;
  setVehicles: (vehicles: VehicleTelemetry[]) => void;
  setFleetAggregates: (agg: {
    throughput_mbps: number | null;
    latency_ms: number | null;
    active_rat: string | null;
  }) => void;
  // Tick loop control
  startPlayback: () => void;
  stopPlayback: () => void;
}

const SECOND = 1000;

export const useStudioStore = create<StudioState>((set, get) => ({
  scenarios: [],
  currentScenario: null,
  status: {
    running: false,
    run_id: null,
    scenario: null,
    started_at: null,
    logs: [],
    exit_code: null,
  },
  logs: ['NexaSim Studio Enterprise v4.0 (React 18 + TypeScript + Dockview)\nReady for dispatch.'],
  simTime: 0.0,
  isPlaying: false,
  playbackSpeed: 2.0,
  selectedNode: null,
  throughputMbps: null,
  latencyMs: null,
  activeRat: null,
  vehicles: [],
  wsConnected: false,
  telemetrySeries: null,
  kpis: null,
  hasRunData: false,
  flyToRequest: null,
  provenanceOpen: false,

  setScenarios: (scenarios) => set({ scenarios }),

  selectScenario: (scenario) =>
    set({
      currentScenario: scenario,
      simTime: 0.0,
      selectedNode: null,
      telemetrySeries: null,
      kpis: null,
      hasRunData: false,
      throughputMbps: null,
      latencyMs: null,
      activeRat: null,
      vehicles: [],
    }),

  setStatus: (status) => set({ status }),

  appendLog: (log) =>
    set((state) => ({
      logs: [...state.logs.slice(-1500), log],
    })),

  appendLogs: (newLogs) =>
    set((state) => {
      if (!newLogs.length) return state;
      const combined = state.logs.concat(newLogs);
      return {
        logs: combined.length > 1500 ? combined.slice(-1500) : combined,
      };
    }),

  clearLogs: () => set({ logs: ['Console cleared.'] }),

  setSimTime: (simTime) => set({ simTime }),

  togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),

  setPlaybackSpeed: (playbackSpeed) => set({ playbackSpeed }),

  selectNode: (selectedNode) => set({ selectedNode }),

  updateNode: (type, index, updatedData) =>
    set((state) => {
      if (!state.currentScenario) return state;
      const sc = { ...state.currentScenario };
      if (type === 'gnb' && sc.gnbs[index]) {
        sc.gnbs = [...sc.gnbs];
        sc.gnbs[index] = { ...sc.gnbs[index], ...updatedData };
      } else if (type === 'gs' && sc.ground_stations[index]) {
        sc.ground_stations = [...sc.ground_stations];
        sc.ground_stations[index] = { ...sc.ground_stations[index], ...updatedData };
      } else if (type === 'blind' && sc.blind_spots[index]) {
        sc.blind_spots = [...sc.blind_spots];
        sc.blind_spots[index] = { ...sc.blind_spots[index], ...updatedData };
      }
      return { currentScenario: sc };
    }),

  addNode: (type, data) =>
    set((state) => {
      if (!state.currentScenario) return state;
      const sc = { ...state.currentScenario };
      if (type === 'gnb') sc.gnbs = [...(sc.gnbs || []), data];
      else if (type === 'gs') sc.ground_stations = [...(sc.ground_stations || []), data];
      else if (type === 'blind') sc.blind_spots = [...(sc.blind_spots || []), data];
      return { currentScenario: sc };
    }),

  requestFlyTo: (target, index, lat, lon) =>
    set({ flyToRequest: { target, index, lat, lon, nonce: Date.now() } }),

  setProvenanceOpen: (provenanceOpen) => set({ provenanceOpen }),

  removeNode: (type, index) =>
    set((state) => {
      if (!state.currentScenario) return state;
      const sc = { ...state.currentScenario };
      if (type === 'gnb' && sc.gnbs) {
        sc.gnbs = sc.gnbs.filter((_, i) => i !== index);
      } else if (type === 'gs' && sc.ground_stations) {
        sc.ground_stations = sc.ground_stations.filter((_, i) => i !== index);
      } else if (type === 'blind' && sc.blind_spots) {
        sc.blind_spots = sc.blind_spots.filter((_, i) => i !== index);
      }
      return { currentScenario: sc, selectedNode: null };
    }),

  setWsConnected: (wsConnected) => set({ wsConnected }),

  updateLiveTelemetry: (frame) =>
    set((state) => {
      const scenarioMatches =
        !state.status.scenario || state.status.scenario === state.currentScenario?.id;
      if (!state.status.running || !scenarioMatches) return {};
      return {
        throughputMbps: frame.throughput_mbps ?? state.throughputMbps,
        latencyMs: frame.latency_ms ?? state.latencyMs,
        activeRat: frame.active_rat ?? state.activeRat,
        vehicles: frame.vehicles ?? state.vehicles,
        simTime: frame.sim_time ?? state.simTime,
        hasRunData:
          state.hasRunData ||
          (frame.vehicles?.length ?? 0) > 0 ||
          frame.throughput_mbps != null,
      };
    }),

  setTelemetrySeries: (series) => set({ telemetrySeries: series, hasRunData: true }),

  setKpis: (kpis) => set({ kpis, hasRunData: true }),

  setHasRunData: (hasData) => set({ hasRunData: hasData }),

  setVehicles: (vehicles) => set({ vehicles }),

  setFleetAggregates: (agg) =>
    set({
      throughputMbps: agg.throughput_mbps,
      latencyMs: agg.latency_ms,
      activeRat: agg.active_rat,
    }),

  startPlayback: () => set({ isPlaying: true }),

  stopPlayback: () => set({ isPlaying: false }),
}));

/**
 * Playback ticker: advances simTime smoothly while isPlaying is true,
 * looping 0 -> currentScenario.duration_s. While a live simulation is
 * running the ws telemetry frames own the clock, so the ticker idles.
 */
let rafId: number | null = null;
let lastTimestamp = 0;
const MIN_FRAME_DELTA_MS = 16.0; // ~60 FPS update throttle to avoid excessive React state dispatch

export function startStudioPlayback() {
  if (rafId !== null) return;
  lastTimestamp = performance.now();
  const tick = (now: number) => {
    const state = useStudioStore.getState();
    if (!state.isPlaying || !state.currentScenario) {
      rafId = null;
      return;
    }
    if (state.status.running) {
      // Live run: sim_time arrives from /ws/telemetry frames.
      lastTimestamp = now;
      rafId = requestAnimationFrame(tick);
      return;
    }
    const elapsed = now - lastTimestamp;
    if (elapsed < MIN_FRAME_DELTA_MS) {
      rafId = requestAnimationFrame(tick);
      return;
    }
    const dt = elapsed / SECOND;
    lastTimestamp = now;

    const duration = state.currentScenario.duration_s || 0;
    if (duration <= 0) {
      rafId = null;
      return;
    }
    const next = state.simTime + dt * state.playbackSpeed;
    if (next >= duration) {
      // Loop back to 0 while still playing
      useStudioStore.setState({ simTime: 0 });
    } else {
      useStudioStore.setState({ simTime: next });
    }
    rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);
}

export function stopStudioPlayback() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

/**
 * Single source of truth for the ticker: whenever `isPlaying` flips, the
 * rAF loop is started/stopped accordingly (covers togglePlay from Header,
 * keyboard shortcuts, external setState calls, ...).
 */
let wasPlaying = false;
useStudioStore.subscribe((state) => {
  if (state.isPlaying === wasPlaying) return;
  wasPlaying = state.isPlaying;
  if (state.isPlaying) {
    startStudioPlayback();
  } else {
    stopStudioPlayback();
  }
});
