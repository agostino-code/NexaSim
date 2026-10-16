import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Globe, DownloadCloud, Loader2, RotateCcw, Layers } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { build3dTwin } from '../../services/api';

type CesiumCommand =
  | { action: 'PLAY' }
  | { action: 'PAUSE' }
  | { action: 'SEEK'; simTime: number }
  | { action: 'SET_SPEED'; multiplier: number }
  | { action: 'TRACK_NODE'; id: string }
  | { action: 'RESET_CAMERA' }
  | { action: 'TOGGLE_LAYER'; layer: 'isl' | 'lobes' | 'footprints'; visible?: boolean }
  | { action: 'HUD_UPDATE'; vehicle: HudVehicle | null }
  | { action: 'VEHICLE_STATE'; vehicles: { id: number; rat: string | null }[] };

type GlobeLayer = 'isl' | 'lobes' | 'footprints';

/** Real per-vehicle telemetry forwarded to the globe cockpit HUD. */
interface HudVehicle {
  id: number;
  name: string;
  speed_kmh: number | null;
  mec_latency_ms: number | null;
  qos_score: number | null;
  battery_soc_pct: number | null;
  active_rat: string | null;
}

const GLOBE_LAYERS: { id: GlobeLayer; label: string; title: string }[] = [
  { id: 'isl', label: 'ISL', title: 'Inter-Satellite Links' },
  { id: 'lobes', label: 'LOBES', title: 'Volumetric 5G antenna lobes' },
  { id: 'footprints', label: 'FOOTPRINTS', title: 'Satellite ground footprints' },
];

export const DigitalTwin3D: React.FC = () => {
  // Zustand atomic selectors
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const simTime = useStudioStore((s) => s.simTime);
  const isPlaying = useStudioStore((s) => s.isPlaying);
  const playbackSpeed = useStudioStore((s) => s.playbackSpeed);
  const selectedNode = useStudioStore((s) => s.selectedNode);
  const selectNode = useStudioStore((s) => s.selectNode);
  const setSimTime = useStudioStore((s) => s.setSimTime);
  const vehicles = useStudioStore((s) => s.vehicles);
  const flyToRequest = useStudioStore((s) => s.flyToRequest);

  const [isGenerating, setIsGenerating] = useState(false);
  const [activeLayers, setActiveLayers] = useState<Record<GlobeLayer, boolean>>({
    isl: true,
    lobes: true,
    footprints: true,
  });
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const globeReadyRef = useRef(false);
  const commandQueueRef = useRef<CesiumCommand[]>([]);
  const lastSeekRef = useRef(0);

  const handleGenerate = async () => {
    if (!currentScenario || isGenerating) return;
    setIsGenerating(true);
    try {
      await build3dTwin(currentScenario.id);
      // Immutable state update
      useStudioStore.setState((s) =>
        s.currentScenario ? { currentScenario: { ...s.currentScenario, has_globe: true } } : s
      );
    } catch (err) {
      console.error('3D Generation failed:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  // Send a command to the Cesium iframe, restricting targetOrigin to window.location.origin
  const sendToCesium = useCallback((cmd: CesiumCommand) => {
    const iframe = iframeRef.current;
    if (!iframe || !iframe.contentWindow || !globeReadyRef.current) {
      commandQueueRef.current.push(cmd);
      return;
    }
    try {
      iframe.contentWindow.postMessage(cmd, window.location.origin);
    } catch (e) {
      console.warn('Failed to postMessage to Cesium:', e);
    }
  }, []);

  // Flush queued commands once the globe signals readiness
  const flushQueue = useCallback(() => {
    const cmds = commandQueueRef.current;
    commandQueueRef.current = [];
    cmds.forEach((cmd) => sendToCesium(cmd));
  }, [sendToCesium]);

  const globeUrl = currentScenario
    ? `/results/${currentScenario.short_name || currentScenario.id}/results/globe.html?studio=1`
    : '';

  // The iframe reloads whenever the URL changes: wait for a fresh GLOBE_READY
  useEffect(() => {
    globeReadyRef.current = false;
    commandQueueRef.current = [];
    lastSeekRef.current = 0;
  }, [globeUrl]);

  // Header -> Cesium: play/pause + speed (the store ticker owns simTime)
  useEffect(() => {
    if (!currentScenario || !currentScenario.has_globe) return;
    sendToCesium({ action: isPlaying ? 'PLAY' : 'PAUSE' });
    sendToCesium({ action: 'SET_SPEED', multiplier: playbackSpeed });
  }, [isPlaying, playbackSpeed, currentScenario, sendToCesium]);

  // Header -> Cesium: SEEK to keep the Cesium clock strictly locked on the
  // studio simTime. Throttled to 10 Hz while playing (the globe interpolates
  // between corrections at its own clock rate); immediate when paused/scrubbed.
  useEffect(() => {
    if (!currentScenario || !currentScenario.has_globe) return;
    const now = performance.now();
    if (isPlaying && now - lastSeekRef.current < 100) return;
    lastSeekRef.current = now;
    sendToCesium({ action: 'SEEK', simTime });
  }, [simTime, isPlaying, currentScenario, sendToCesium]);

  // Header -> Cesium: TRACK_NODE when selection changes
  useEffect(() => {
    if (!currentScenario || !currentScenario.has_globe) return;
    if (selectedNode && selectedNode.type === 'veh') {
      sendToCesium({ action: 'TRACK_NODE', id: `veh_${selectedNode.index}` });
    }
  }, [selectedNode, currentScenario, sendToCesium]);

  // Header -> Cesium: forward the tracked (or leader) vehicle's real
  // telemetry to the globe cockpit HUD. Missing metrics stay null and the
  // HUD renders them as "—" (not recorded).
  useEffect(() => {
    if (!currentScenario || !currentScenario.has_globe) return;
    const tracked =
      selectedNode && selectedNode.type === 'veh'
        ? vehicles.find((v) => v.id === selectedNode.index)
        : undefined;
    const target = tracked ?? vehicles[0];
    sendToCesium({
      action: 'HUD_UPDATE',
      vehicle: target
        ? {
            id: target.id,
            name: target.name,
            speed_kmh: target.speed_kmh,
            mec_latency_ms: target.mec_latency_ms,
            qos_score: target.qos_score,
            battery_soc_pct: target.battery_soc_pct,
            active_rat: target.active_rat,
          }
        : null,
    });
  }, [vehicles, selectedNode, currentScenario, sendToCesium]);

  // Header -> Cesium: forward per-vehicle RAT colours so 2D and 3D always
  // agree. Only recorded link states are forwarded ("not recorded" stays grey).
  useEffect(() => {
    if (!currentScenario || !currentScenario.has_globe) return;
    if (!vehicles.length) return;
    sendToCesium({
      action: 'VEHICLE_STATE',
      vehicles: vehicles.map((v) => ({ id: v.id, rat: v.active_rat ?? null })),
    });
  }, [vehicles, currentScenario, sendToCesium]);

  // One-shot fly-to requests (Node Inspector "Track 3D" / "Focus" buttons):
  // map the selected node to its CZML entity and track it in the globe.
  const flyNonce = flyToRequest?.nonce;
  useEffect(() => {
    if (!currentScenario || !currentScenario.has_globe || !flyToRequest) return;
    if (flyToRequest.target === 'blind') return; // no blind-spot entity in the 3D scene
    const prefix =
      flyToRequest.target === 'veh' ? 'veh_' : flyToRequest.target === 'gnb' ? 'gnb_' : 'gs_';
    sendToCesium({ action: 'TRACK_NODE', id: `${prefix}${flyToRequest.index}` });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flyNonce]);

  const toggleLayer = (layer: GlobeLayer) => {
    setActiveLayers((prev) => {
      const next = { ...prev, [layer]: !prev[layer] };
      sendToCesium({ action: 'TOGGLE_LAYER', layer, visible: next[layer] });
      return next;
    });
  };

  // Handle messages FROM Cesium -> Studio
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Validate origin to ensure only same-origin messages are accepted
      if (event.origin !== window.location.origin) return;
      // Only accept traffic from our own globe iframe
      if (!iframeRef.current || event.source !== iframeRef.current.contentWindow) return;
      if (!event.data || typeof event.data !== 'object') return;
      const { action, ...payload } = event.data as { action?: string } & Record<string, unknown>;

      switch (action) {
        case 'GLOBE_READY':
          globeReadyRef.current = true;
          flushQueue();
          // Initial sync: push the current studio clock state into Cesium
          sendToCesium({ action: isPlaying ? 'PLAY' : 'PAUSE' });
          sendToCesium({ action: 'SET_SPEED', multiplier: playbackSpeed });
          sendToCesium({ action: 'SEEK', simTime });
          // Push the current layer state (idempotent commands)
          (Object.keys(activeLayers) as GlobeLayer[]).forEach((layer) => {
            sendToCesium({ action: 'TOGGLE_LAYER', layer, visible: activeLayers[layer] });
          });
          break;

        case 'NODE_CLICKED': {
          const id = payload.nodeId as string;
          if (id && typeof id === 'string' && id.startsWith('veh_')) {
            const idx = parseInt(id.replace('veh_', ''), 10);
            if (!isNaN(idx)) {
              selectNode({ type: 'veh', index: idx, data: { id: idx, name: `Vehicle ${idx}` } });
            }
          }
          break;
        }

        case 'CAMERA_UPDATE': {
          const lat = payload.lat as number;
          const lon = payload.lon as number;
          const alt = payload.altitude as number;
          if (typeof lat === 'number' && typeof lon === 'number') {
            console.debug('[Cesium] Camera:', { lat, lon, alt });
          }
          break;
        }

        case 'VIEWER_TIME': {
          const viewerTime = payload.time as number;
          if (typeof viewerTime === 'number' && !isPlaying) {
            // Cesium-driven scrubbing reflects back into the studio clock
            setSimTime(viewerTime);
          }
          break;
        }

        default:
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [selectNode, setSimTime, isPlaying, playbackSpeed, simTime, activeLayers, flushQueue, sendToCesium]);

  if (!currentScenario) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#030712] text-slate-400 p-6 text-center select-none">
        <Globe size={48} className="text-slate-600 mb-3" />
        <h3 className="text-sm font-bold text-slate-200">No Scenario Selected</h3>
        <p className="text-xs text-slate-500 max-w-sm mt-1">
          Select an active scenario from the Scenario Catalog to initialize the 3D Space-Ground Twin.
        </p>
      </div>
    );
  }

  if (!currentScenario.has_globe) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gradient-to-b from-slate-900 to-[#030712] text-slate-300 p-6 text-center select-none">
        <Globe size={48} className="text-brand-cyan mb-3 drop-shadow-[0_0_15px_rgba(56,189,248,0.4)]" />
        <h3 className="text-base font-bold text-slate-100">3D Digital Twin Not Generated</h3>
        <p className="text-xs text-slate-400 max-w-md mt-1 mb-4 leading-relaxed">
          The CZML orbital and terrestrial digital twin for <strong>{currentScenario.name}</strong> has not been compiled yet.
        </p>
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className="flex items-center gap-2 px-4 py-2 bg-bg-card border border-border-medium hover:border-brand-cyan hover:text-brand-cyan text-slate-100 text-xs font-semibold rounded shadow transition disabled:opacity-50"
        >
          {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <DownloadCloud size={14} />}
          <span>Generate 3D Digital Twin</span>
        </button>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative bg-[#030712] overflow-hidden">
      <iframe
        ref={iframeRef}
        src={globeUrl}
        className="w-full h-full border-none bg-[#030712]"
        title="3D Geospatial Digital Twin"
        allow="autoplay"
      />

      {/* Sync status overlay (top-left of the 3D viewport) */}
      <div className="absolute top-2 left-2 z-50 flex flex-col gap-1 pointer-events-none">
        <span
          className={`text-[9px] font-mono px-2 py-0.5 rounded bg-black/60 border border-border-medium ${
            isPlaying ? 'text-brand-cyan border-brand-cyan/50' : 'text-slate-500 border-slate-600'
          }`}
        >
          {isPlaying ? '▶ PLAYING' : '⏸ PAUSED'} • t = {simTime.toFixed(1)} s
        </span>
        <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-black/60 border border-border-medium text-slate-400 border-slate-600">
          ⨯ {playbackSpeed.toFixed(1)}x
        </span>
      </div>

      {/* Layer / camera controls (top-right of the 3D viewport) */}
      <div className="absolute top-2 right-2 z-50 flex items-center gap-1 bg-black/60 border border-border-medium rounded px-1 py-0.5">
        <Layers size={11} className="text-slate-400 mr-0.5" />
        {GLOBE_LAYERS.map((layer) => (
          <button
            key={layer.id}
            onClick={() => toggleLayer(layer.id)}
            title={layer.title}
            className={`text-[9px] font-mono px-1.5 py-0.5 rounded transition ${
              activeLayers[layer.id]
                ? 'bg-sky-500/20 text-brand-cyan'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {layer.label}
          </button>
        ))}
        <span className="w-px h-3 bg-border-medium mx-0.5" />
        <button
          onClick={() => sendToCesium({ action: 'RESET_CAMERA' })}
          title="Reset camera to scenario overview"
          className="text-slate-400 hover:text-brand-cyan p-0.5"
        >
          <RotateCcw size={11} />
        </button>
      </div>
    </div>
  );
};
