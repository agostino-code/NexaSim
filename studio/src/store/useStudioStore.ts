import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import {
  ScenarioSummary,
  ScenarioConfig,
  SimStatus,
  VehicleTelemetry,
  LiveTelemetryFrame,
  TelemetrySeries,
  KpiSummary,
  FleetTimelineResponse,
  CompareResponse,
  SelectedNodeType,
  SelectedNode,
  WorkspaceMode,
  LayersVisibility,
  DrawingToolType,
  ValidationError,
  SimulationFrame,
  SimulationRadioLink,
  SatelliteEntity,
} from '../types/scenario';

export interface FlyToRequest {
  target: SelectedNodeType;
  index: number;
  lat: number;
  lon: number;
  nonce: number;
}

export interface StudioState {
  // -------------------------------------------------------------
  // 1. WorkspaceSlice
  // -------------------------------------------------------------
  activeMode: WorkspaceMode;
  activePresetLayout: string;
  isCommandPaletteOpen: boolean;
  setActiveMode: (mode: WorkspaceMode) => void;
  setActivePresetLayout: (layout: string) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;

  // -------------------------------------------------------------
  // 2. TimelineSlice
  // -------------------------------------------------------------
  currentTime: number;
  simTime: number; // Backwards-compatible alias for currentTime
  duration: number;
  isPlaying: boolean;
  playbackSpeed: number;
  telemetryBuffer: Record<number, SimulationFrame>; // timestamp (rounded to 0.1s) -> frame
  availableTimestamps: number[];
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  seek: (time: number) => void;
  setSimTime: (time: number) => void; // Alias for seek
  stepForward: (delta?: number) => void;
  stepBackward: (delta?: number) => void;
  setPlaybackSpeed: (speed: number) => void;
  ingestFrame: (frame: SimulationFrame | Partial<LiveTelemetryFrame>) => void;
  clearBuffer: () => void;
  startPlayback: () => void;
  stopPlayback: () => void;

  // -------------------------------------------------------------
  // 3. ViewportSlice
  // -------------------------------------------------------------
  viewState: {
    longitude: number;
    latitude: number;
    zoom: number;
    pitch: number;
    bearing: number;
    transitionDuration?: number;
  };
  projection: 'globe' | 'mercator';
  trackedNodeId: string | null;
  layersVisibility: LayersVisibility;
  setViewState: (
    patch: Partial<{
      longitude: number;
      latitude: number;
      zoom: number;
      pitch: number;
      bearing: number;
      transitionDuration?: number;
    }>
  ) => void;
  setProjection: (projection: 'globe' | 'mercator') => void;
  setTrackedNodeId: (id: string | null) => void;
  toggleLayerVisibility: (layer: keyof LayersVisibility) => void;
  setLayersVisibility: (patch: Partial<LayersVisibility>) => void;

  // -------------------------------------------------------------
  // 4. ScenarioBuilderSlice
  // -------------------------------------------------------------
  draftScenario: ScenarioConfig | null;
  validationErrors: ValidationError[];
  drawingTool: DrawingToolType;
  isDirty: boolean;
  isGenerating: boolean;
  setDraftScenario: (draft: ScenarioConfig | null) => void;
  updateDraftSection: (path: string, value: any) => void;
  setValidationErrors: (errors: ValidationError[]) => void;
  setDrawingTool: (tool: DrawingToolType) => void;
  setIsDirty: (dirty: boolean) => void;
  setIsGenerating: (generating: boolean) => void;
  exportToYaml: () => string;

  // -------------------------------------------------------------
  // 5. SelectionSlice
  // -------------------------------------------------------------
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  selectedLinkId: string | null;
  comparedRunIds: string[];
  selectedNode: SelectedNode | null; // Backwards compatibility
  selectNode: (node: SelectedNode | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  setHoveredNodeId: (id: string | null) => void;
  setSelectedLinkId: (id: string | null) => void;
  toggleComparedRun: (runId: string) => void;

  // -------------------------------------------------------------
  // Legacy & Shared Simulation Context (Backwards Compatibility)
  // -------------------------------------------------------------
  scenarios: ScenarioSummary[];
  currentScenario: ScenarioSummary | null;
  status: SimStatus;
  logs: string[];
  throughputMbps: number | null;
  latencyMs: number | null;
  activeRat: string | null;
  vehicles: VehicleTelemetry[];
  satellites: SatelliteEntity[];
  activeLinks: SimulationRadioLink[];
  wsConnected: boolean;
  flyToRequest: FlyToRequest | null;
  provenanceOpen: boolean;
  telemetrySeries: TelemetrySeries | null;
  kpis: KpiSummary | null;
  hasRunData: boolean;
  fleetTimeline: FleetTimelineResponse | null;
  compareData: CompareResponse | null;
  compareBaselineEnabled: boolean;

  // Legacy actions
  setScenarios: (scenarios: ScenarioSummary[]) => void;
  selectScenario: (scenario: ScenarioSummary) => void;
  setStatus: (status: SimStatus) => void;
  appendLog: (log: string) => void;
  appendLogs: (logs: string[]) => void;
  clearLogs: () => void;
  updateNode: (type: SelectedNodeType, index: number, updatedData: any) => void;
  updateScenarioParams: (patch: Partial<ScenarioSummary>) => void;
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
  setFleetTimeline: (timeline: FleetTimelineResponse | null) => void;
  setCompareData: (data: CompareResponse | null) => void;
  toggleCompareBaseline: () => void;
  setFleetAggregates: (agg: {
    throughput_mbps: number | null;
    latency_ms: number | null;
    active_rat: string | null;
  }) => void;
}

const defaultLayersVisibility: LayersVisibility = {
  vehicles: true,
  uavs: true,
  ships: true,
  trains: true,
  rsuAndGnb: true,
  groundStations: true,
  leoSatellites: true,
  leoOrbits: true,
  islLinks: true,
  v2xLinks: true,
  nrLinks: true,
  ntnLinks: true,
  sensorCones: true,
  gemv2LosRays: true,
  buildings3D: true,
  terrain3D: true,
};

let playbackTimer: number | null = null;

export const useStudioStore = create<StudioState>()(
  subscribeWithSelector(
    immer((set, get) => ({
      // -------------------------------------------------------------
      // 1. WorkspaceSlice Implementation
      // -------------------------------------------------------------
      activeMode: 'live',
      activePresetLayout: 'mission_control',
      isCommandPaletteOpen: false,

      setActiveMode: (mode) =>
        set((state) => {
          state.activeMode = mode;
          if (mode === 'design') {
            state.activePresetLayout = 'builder';
          } else if (mode === 'analyze') {
            state.activePresetLayout = 'analytics';
          } else {
            state.activePresetLayout = 'mission_control';
          }
        }),

      setActivePresetLayout: (layout) =>
        set((state) => {
          state.activePresetLayout = layout;
        }),

      setCommandPaletteOpen: (open) =>
        set((state) => {
          state.isCommandPaletteOpen = open;
        }),

      toggleCommandPalette: () =>
        set((state) => {
          state.isCommandPaletteOpen = !state.isCommandPaletteOpen;
        }),

      // -------------------------------------------------------------
      // 2. TimelineSlice Implementation
      // -------------------------------------------------------------
      currentTime: 0,
      simTime: 0,
      duration: 300,
      isPlaying: false,
      playbackSpeed: 1,
      telemetryBuffer: {},
      availableTimestamps: [],

      play: () => {
        const { isPlaying } = get();
        if (isPlaying) return;
        set((state) => {
          state.isPlaying = true;
        });
        get().startPlayback();
      },

      pause: () => {
        set((state) => {
          state.isPlaying = false;
        });
        get().stopPlayback();
      },

      togglePlay: () => {
        if (get().isPlaying) {
          get().pause();
        } else {
          get().play();
        }
      },

      seek: (time) =>
        set((state) => {
          const maxDur = state.duration > 0 ? state.duration : 3600;
          const clamped = Math.max(0, Math.min(time, maxDur));
          state.currentTime = clamped;
          state.simTime = clamped;

          // Lookup closest frame from telemetryBuffer if available
          const roundedKey = Math.round(clamped * 10) / 10;
          const frame = state.telemetryBuffer[roundedKey];
          if (frame) {
            state.vehicles = frame.vehicles;
            state.satellites = frame.satellites;
            state.activeLinks = frame.links;
            if (frame.aggregates) {
              state.throughputMbps = frame.aggregates.throughput_mbps;
              state.latencyMs = frame.aggregates.latency_ms;
              state.activeRat = frame.aggregates.active_rat;
            }
          }
        }),

      setSimTime: (time) => get().seek(time),

      stepForward: (delta = 0.5) => {
        const { currentTime, duration, seek } = get();
        seek(Math.min(currentTime + delta, duration));
      },

      stepBackward: (delta = 0.5) => {
        const { currentTime, seek } = get();
        seek(Math.max(currentTime - delta, 0));
      },

      setPlaybackSpeed: (speed) =>
        set((state) => {
          state.playbackSpeed = speed;
          if (state.isPlaying) {
            get().stopPlayback();
            get().startPlayback();
          }
        }),

      ingestFrame: (frame: any) =>
        set((state) => {
          const t = frame.sim_time !== undefined ? frame.sim_time : frame.simTime ?? state.currentTime;
          const roundedT = Math.round(t * 10) / 10;
          const vehs = frame.vehicles || [];
          const sats = frame.satellites || state.satellites || [];
          const links = frame.links || state.activeLinks || [];

          state.telemetryBuffer[roundedT] = {
            simTime: t,
            vehicles: vehs,
            satellites: sats,
            links: links,
            aggregates: {
              throughput_mbps: frame.throughput_mbps ?? state.throughputMbps,
              latency_ms: frame.latency_ms ?? state.latencyMs,
              active_rat: frame.active_rat ?? state.activeRat,
            },
          };

          if (!state.availableTimestamps.includes(roundedT)) {
            state.availableTimestamps.push(roundedT);
            state.availableTimestamps.sort((a, b) => a - b);
          }

          // If close to live time, update current telemetry
          if (Math.abs(state.currentTime - t) < 1.0 || state.isPlaying) {
            state.currentTime = t;
            state.simTime = t;
            state.vehicles = vehs;
            if (frame.throughput_mbps !== undefined) state.throughputMbps = frame.throughput_mbps;
            if (frame.latency_ms !== undefined) state.latencyMs = frame.latency_ms;
            if (frame.active_rat !== undefined) state.activeRat = frame.active_rat;
          }
        }),

      clearBuffer: () =>
        set((state) => {
          state.telemetryBuffer = {};
          state.availableTimestamps = [];
        }),

      startPlayback: () => {
        if (playbackTimer !== null) clearInterval(playbackTimer);
        const tickInterval = 50; // 20 FPS ticks
        playbackTimer = window.setInterval(() => {
          const { isPlaying, currentTime, duration, playbackSpeed, seek, pause } = get();
          if (!isPlaying) {
            clearInterval(playbackTimer!);
            playbackTimer = null;
            return;
          }
          const dt = (tickInterval / 1000) * playbackSpeed;
          const nextTime = currentTime + dt;
          if (nextTime >= duration) {
            seek(duration);
            pause();
          } else {
            seek(nextTime);
          }
        }, tickInterval);
      },

      stopPlayback: () => {
        if (playbackTimer !== null) {
          clearInterval(playbackTimer);
          playbackTimer = null;
        }
      },

      // -------------------------------------------------------------
      // 3. ViewportSlice Implementation
      // -------------------------------------------------------------
      viewState: {
        longitude: 10.5,
        latitude: 46.5,
        zoom: 3.5,
        pitch: 45,
        bearing: 0,
      },
      projection: 'globe',
      trackedNodeId: null,
      layersVisibility: defaultLayersVisibility,

      setViewState: (patch) =>
        set((state) => {
          state.viewState = { ...state.viewState, ...patch };
        }),

      setProjection: (projection) =>
        set((state) => {
          state.projection = projection;
        }),

      setTrackedNodeId: (id) =>
        set((state) => {
          state.trackedNodeId = id;
        }),

      toggleLayerVisibility: (layer) =>
        set((state) => {
          state.layersVisibility[layer] = !state.layersVisibility[layer];
        }),

      setLayersVisibility: (patch) =>
        set((state) => {
          state.layersVisibility = { ...state.layersVisibility, ...patch };
        }),

      // -------------------------------------------------------------
      // 4. ScenarioBuilderSlice Implementation
      // -------------------------------------------------------------
      draftScenario: null,
      validationErrors: [],
      drawingTool: 'select',
      isDirty: false,
      isGenerating: false,

      setDraftScenario: (draft) =>
        set((state) => {
          state.draftScenario = draft;
          state.isDirty = false;
        }),

      updateDraftSection: (path, value) =>
        set((state) => {
          if (!state.draftScenario) return;
          const keys = path.split('.');
          let curr: any = state.draftScenario;
          for (let i = 0; i < keys.length - 1; i++) {
            if (curr[keys[i]] === undefined) curr[keys[i]] = {};
            curr = curr[keys[i]];
          }
          curr[keys[keys.length - 1]] = value;
          state.isDirty = true;
        }),

      setValidationErrors: (errors) =>
        set((state) => {
          state.validationErrors = errors;
        }),

      setDrawingTool: (tool) =>
        set((state) => {
          state.drawingTool = tool;
        }),

      setIsDirty: (dirty) =>
        set((state) => {
          state.isDirty = dirty;
        }),

      setIsGenerating: (generating) =>
        set((state) => {
          state.isGenerating = generating;
        }),

      exportToYaml: () => {
        const { draftScenario } = get();
        if (!draftScenario) return '';
        try {
          const yaml = (window as any).jsyaml || null;
          if (yaml) return yaml.dump(draftScenario);
          return JSON.stringify(draftScenario, null, 2);
        } catch {
          return JSON.stringify(draftScenario, null, 2);
        }
      },

      // -------------------------------------------------------------
      // 5. SelectionSlice Implementation
      // -------------------------------------------------------------
      selectedNodeId: null,
      hoveredNodeId: null,
      selectedLinkId: null,
      comparedRunIds: [],
      selectedNode: null,

      selectNode: (selectedNode) =>
        set((state) => {
          state.selectedNode = selectedNode;
          state.selectedNodeId = selectedNode
            ? `${selectedNode.type}.${selectedNode.data?.name || selectedNode.data?.id || selectedNode.index}`
            : null;
        }),

      setSelectedNodeId: (id) =>
        set((state) => {
          state.selectedNodeId = id;
        }),

      setHoveredNodeId: (id) =>
        set((state) => {
          state.hoveredNodeId = id;
        }),

      setSelectedLinkId: (id) =>
        set((state) => {
          state.selectedLinkId = id;
        }),

      toggleComparedRun: (runId) =>
        set((state) => {
          if (state.comparedRunIds.includes(runId)) {
            state.comparedRunIds = state.comparedRunIds.filter((r) => r !== runId);
          } else {
            state.comparedRunIds.push(runId);
          }
        }),

      // -------------------------------------------------------------
      // Shared Simulation Context & Legacy Actions
      // -------------------------------------------------------------
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
      logs: [],
      throughputMbps: null,
      latencyMs: null,
      activeRat: null,
      vehicles: [],
      satellites: [],
      activeLinks: [],
      wsConnected: false,
      flyToRequest: null,
      provenanceOpen: false,
      telemetrySeries: null,
      kpis: null,
      hasRunData: false,
      fleetTimeline: null,
      compareData: null,
      compareBaselineEnabled: false,

      setScenarios: (scenarios) =>
        set((state) => {
          state.scenarios = scenarios;
        }),

      selectScenario: (scenario) =>
        set((state) => {
          state.currentScenario = scenario;
          state.duration = scenario.duration_s || 300;
          state.currentTime = 0;
          state.simTime = 0;
          state.vehicles = [];
          state.activeLinks = [];
          state.selectedNode = null;
          state.selectedNodeId = null;
          state.telemetrySeries = null;
          state.kpis = null;
          state.hasRunData = false;
          state.fleetTimeline = null;
          state.compareData = null;
          state.telemetryBuffer = {};
          state.availableTimestamps = [];

          // Center view on scenario area
          if (scenario.center) {
            state.viewState.latitude = scenario.center[0];
            state.viewState.longitude = scenario.center[1];
            state.viewState.zoom = 10;
          }
        }),

      setStatus: (status) =>
        set((state) => {
          state.status = status;
        }),

      appendLog: (log) =>
        set((state) => {
          state.logs.push(log);
          if (state.logs.length > 500) {
            state.logs.shift();
          }
        }),

      appendLogs: (newLogs) =>
        set((state) => {
          state.logs.push(...newLogs);
          if (state.logs.length > 500) {
            state.logs = state.logs.slice(-500);
          }
        }),

      clearLogs: () =>
        set((state) => {
          state.logs = [];
        }),

      updateNode: (type, index, updatedData) =>
        set((state) => {
          if (!state.currentScenario) return;
          const sc = state.currentScenario;
          let updatedNodeData = updatedData;
          if (type === 'gnb' && sc.gnbs[index]) {
            sc.gnbs[index] = { ...sc.gnbs[index], ...updatedData };
            updatedNodeData = sc.gnbs[index];
          } else if (type === 'gs' && sc.ground_stations[index]) {
            sc.ground_stations[index] = { ...sc.ground_stations[index], ...updatedData };
            updatedNodeData = sc.ground_stations[index];
          } else if (type === 'blind' && sc.blind_spots[index]) {
            sc.blind_spots[index] = { ...sc.blind_spots[index], ...updatedData };
            updatedNodeData = sc.blind_spots[index];
          }
          if (state.selectedNode && state.selectedNode.type === type && state.selectedNode.index === index) {
            state.selectedNode.data = updatedNodeData;
          }
        }),

      updateScenarioParams: (patch) =>
        set((state) => {
          if (!state.currentScenario) return;
          Object.assign(state.currentScenario, patch);
          const scId = state.currentScenario.id;
          const idx = state.scenarios.findIndex((s) => s.id === scId);
          if (idx !== -1) {
            Object.assign(state.scenarios[idx], patch);
          }
          if (patch.duration_s !== undefined) {
            state.duration = patch.duration_s;
          }
        }),

      addNode: (type, data) =>
        set((state) => {
          if (!state.currentScenario) return;
          const sc = state.currentScenario;
          if (type === 'gnb') {
            sc.gnbs = sc.gnbs || [];
            sc.gnbs.push(data);
          } else if (type === 'gs') {
            sc.ground_stations = sc.ground_stations || [];
            sc.ground_stations.push(data);
          } else if (type === 'blind') {
            sc.blind_spots = sc.blind_spots || [];
            sc.blind_spots.push(data);
          }
        }),

      removeNode: (type, index) =>
        set((state) => {
          if (!state.currentScenario) return;
          const sc = state.currentScenario;
          if (type === 'gnb' && sc.gnbs) {
            sc.gnbs.splice(index, 1);
          } else if (type === 'gs' && sc.ground_stations) {
            sc.ground_stations.splice(index, 1);
          } else if (type === 'blind' && sc.blind_spots) {
            sc.blind_spots.splice(index, 1);
          }
          state.selectedNode = null;
          state.selectedNodeId = null;
        }),

      requestFlyTo: (target, index, lat, lon) =>
        set((state) => {
          state.flyToRequest = { target, index, lat, lon, nonce: Date.now() };
          state.viewState.latitude = lat;
          state.viewState.longitude = lon;
          state.viewState.zoom = Math.max(state.viewState.zoom, 12);
        }),

      setProvenanceOpen: (open) =>
        set((state) => {
          state.provenanceOpen = open;
        }),

      setWsConnected: (connected) =>
        set((state) => {
          state.wsConnected = connected;
        }),

      updateLiveTelemetry: (frame) =>
        set((state) => {
          if (frame.sim_time !== undefined) {
            state.currentTime = frame.sim_time;
            state.simTime = frame.sim_time;
          }
          if (frame.throughput_mbps !== undefined) state.throughputMbps = frame.throughput_mbps;
          if (frame.latency_ms !== undefined) state.latencyMs = frame.latency_ms;
          if (frame.active_rat !== undefined) state.activeRat = frame.active_rat;
          if (frame.vehicles) state.vehicles = frame.vehicles;
        }),

      setTelemetrySeries: (series) =>
        set((state) => {
          state.telemetrySeries = series;
        }),

      setKpis: (kpis) =>
        set((state) => {
          state.kpis = kpis;
        }),

      setHasRunData: (hasData) =>
        set((state) => {
          state.hasRunData = hasData;
        }),

      setVehicles: (vehicles) =>
        set((state) => {
          state.vehicles = vehicles;
        }),

      setFleetTimeline: (timeline) =>
        set((state) => {
          state.fleetTimeline = timeline;
        }),

      setCompareData: (data) =>
        set((state) => {
          state.compareData = data;
        }),

      toggleCompareBaseline: () =>
        set((state) => {
          state.compareBaselineEnabled = !state.compareBaselineEnabled;
        }),

      setFleetAggregates: (agg) =>
        set((state) => {
          state.throughputMbps = agg.throughput_mbps;
          state.latencyMs = agg.latency_ms;
          state.activeRat = agg.active_rat;
        }),
    }))
  )
);
