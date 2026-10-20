import React from 'react';
import {
  Settings2,
  Trash2,
  X,
  ShieldAlert,
  Radio,
  Satellite,
  Car,
  MapPin,
  Crosshair,
  Activity,
  Zap,
  Battery,
  Clock,
  Compass,
  Eye,
  Sliders,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { deleteNode } from '../../services/api';
import { ratLabel, ratColor } from '../../theme/palette';
import { VehicleTelemetry } from '../../types/scenario';

const fmt = (v: number | null | undefined, digits = 1, suffix = ''): string =>
  v == null || Number.isNaN(v) ? '—' : `${v.toFixed(digits)}${suffix}`;

interface NumberFieldProps {
  label: string;
  value: number | null | undefined;
  onCommit: (v: number) => void;
  step?: string;
  min?: number;
  max?: number;
}

const NumberField: React.FC<NumberFieldProps> = ({ label, value, onCommit, step, min, max }) => (
  <div>
    <label className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1 font-mono">{label}</label>
    <input
      type="number"
      step={step}
      min={min}
      max={max}
      value={value ?? ''}
      placeholder="not recorded"
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === '') return;
        const n = parseFloat(raw);
        if (!Number.isNaN(n)) onCommit(n);
      }}
      className="w-full bg-bg-card border border-border-subtle px-2 py-1 rounded text-slate-100 outline-none focus:border-brand-cyan placeholder:text-slate-600 font-mono text-xs"
    />
  </div>
);

/**
 * 2D Canvas Mini Radar / Perception FoV View for Ego Vehicle.
 * Renders radar detection arcs, range rings, and surrounding obstacles.
 */
const MiniRadarView: React.FC<{ vehicle: VehicleTelemetry }> = ({ vehicle }) => {
  const heading = vehicle.heading_deg ?? 0;
  const inBlind = vehicle.in_blind;

  return (
    <div className="flex flex-col gap-1.5 p-2 bg-bg-base border border-border-subtle rounded mt-2">
      <div className="flex items-center justify-between text-[10px] font-mono">
        <span className="flex items-center gap-1 text-brand-cyan font-bold">
          <Eye className="w-3 h-3" />
          <span>LOCAL PERCEPTION MODEL (ETSI CPM)</span>
        </span>
        <span className="text-slate-500">Range: 150m</span>
      </div>

      <div className="relative w-full h-32 flex items-center justify-center overflow-hidden bg-radial from-slate-900/60 to-bg-base border border-border-subtle/40 rounded">
        {/* Radar Range Rings */}
        <div className="absolute w-28 h-28 rounded-full border border-brand-cyan/20 pointer-events-none" />
        <div className="absolute w-20 h-20 rounded-full border border-brand-cyan/25 pointer-events-none" />
        <div className="absolute w-12 h-12 rounded-full border border-brand-cyan/30 pointer-events-none" />

        {/* Crosshair Axes */}
        <div className="absolute w-full h-px bg-border-subtle/50 pointer-events-none" />
        <div className="absolute h-full w-px bg-border-subtle/50 pointer-events-none" />

        {/* 120° Front FoV Cone */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <polygon
            points="50%,50% 15%,0 85%,0"
            fill={inBlind ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.18)'}
            stroke={inBlind ? '#ef4444' : '#38bdf8'}
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        </svg>

        {/* Simulated Detected Objects in FOV */}
        <div className="absolute top-5 left-1/2 -translate-x-3 w-2 h-2 rounded-full bg-emerald-400 shadow-md animate-pulse" title="Lead Vehicle" />
        <div className="absolute top-10 right-10 w-2 h-2 rounded-full bg-amber-400 shadow-md" title="Tracked Obstacle" />

        {/* Ego Vehicle Center Marker */}
        <div className="relative z-10 flex flex-col items-center">
          <div
            className="w-4 h-4 bg-brand-cyan border border-white rounded flex items-center justify-center shadow-lg"
            style={{ transform: `rotate(${heading}deg)` }}
          >
            <div className="w-0.5 h-2 bg-slate-950 mb-1" />
          </div>
          <span className="text-[9px] font-mono text-slate-400 mt-0.5 font-bold">EGO</span>
        </div>
      </div>

      <div className="flex items-center justify-between text-[9px] font-mono text-slate-500">
        <span>Sensors: FrontRadar + CamSensor</span>
        <span className="text-emerald-400 font-bold">2 Tracked Objects</span>
      </div>
    </div>
  );
};

export const NodeInspector: React.FC = () => {
  const selectedNode = useStudioStore((s) => s.selectedNode);
  const selectNode = useStudioStore((s) => s.selectNode);
  const updateNode = useStudioStore((s) => s.updateNode);
  const removeNode = useStudioStore((s) => s.removeNode);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const appendLog = useStudioStore((s) => s.appendLog);
  const requestFlyTo = useStudioStore((s) => s.requestFlyTo);
  const vehicles = useStudioStore((s) => s.vehicles);
  const setTrackedNodeId = useStudioStore((s) => s.setTrackedNodeId);
  const trackedNodeId = useStudioStore((s) => s.trackedNodeId);

  if (!selectedNode || !selectedNode.data) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4 text-center text-slate-500 bg-bg-panel select-none">
        <Settings2 size={36} className="text-slate-600 mb-2" />
        <span className="text-xs font-semibold text-slate-400 font-mono">No Element Selected</span>
        <p className="text-[11px] text-slate-600 max-w-[200px] mt-1 font-sans">
          Click any 5G cell, gateway, blind spot or vehicle on the map/globe to inspect properties.
        </p>
      </div>
    );
  }

  const { type, index } = selectedNode;
  const isVeh = type === 'veh';
  const liveVeh = isVeh ? vehicles.find((v) => v.id === selectedNode.data.id) ?? selectedNode.data : null;
  const data = isVeh ? liveVeh : selectedNode.data;

  const handleDelete = async () => {
    if (!currentScenario) return;
    if (type === 'veh') return;

    const nodeName = data.name;
    appendLog(`[*] Deleting ${type} '${nodeName}' from scenario '${currentScenario.id}'...`);
    try {
      await deleteNode(currentScenario.id, type, nodeName);
      removeNode(type, index);
      appendLog(`[+] Node '${nodeName}' deleted and scenario synchronized.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`[!] Delete failed: ${msg}`);
    }
  };

  const isTracking = trackedNodeId === `${type}.${data.id || data.name || index}`;

  return (
    <div className="h-full bg-bg-panel border-l border-border-subtle flex flex-col overflow-y-auto select-none font-sans text-slate-200">
      {/* Title & Close */}
      <div className="p-3 border-b border-border-subtle flex items-center justify-between bg-bg-card shrink-0">
        <div className="flex items-center gap-2">
          {type === 'gnb' && <Radio className="w-4 h-4 text-emerald-400" />}
          {type === 'gs' && <Satellite className="w-4 h-4 text-orange-400" />}
          {type === 'blind' && <ShieldAlert className="w-4 h-4 text-accent-red" />}
          {type === 'veh' && <Car className="w-4 h-4 text-brand-cyan" />}
          {type === 'sat' && <Satellite className="w-4 h-4 text-brand-cyan" />}
          <div>
            <span className="text-xs font-bold font-mono text-slate-100 block">
              {data.name || `${type.toUpperCase()} #${index}`}
            </span>
            <span className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">
              {type === 'gnb' ? '5G gNodeB Cell' : type === 'gs' ? 'NTN Gateway' : type === 'blind' ? 'Radio Blind Spot' : type === 'sat' ? 'LEO Spacecraft' : 'Vehicle UE'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {isVeh && (
            <button
              onClick={() => setTrackedNodeId(isTracking ? null : `${type}.${data.id}`)}
              className={`p-1.5 rounded transition ${isTracking ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'text-slate-400 hover:text-slate-200 hover:bg-bg-panel'}`}
              title={isTracking ? 'Release Camera Lock' : 'Lock Camera on Vehicle'}
            >
              <Crosshair className={`w-3.5 h-3.5 ${isTracking ? 'animate-spin' : ''}`} />
            </button>
          )}

          <button
            onClick={() => selectNode(null)}
            className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-bg-panel rounded transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-3 flex-1 flex flex-col gap-3 text-xs">
        {/* Vehicle Telemetry & Kinematics */}
        {isVeh && (
          <>
            {/* Kinematic Card */}
            <div className="bg-bg-card border border-border-subtle rounded p-2.5 flex flex-col gap-1.5 font-mono">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Compass className="w-3.5 h-3.5 text-brand-cyan" />
                Kinematics & Positioning
              </span>
              <div className="grid grid-cols-2 gap-2 text-[11px] mt-1">
                <div>
                  <span className="text-slate-500">Speed:</span>{' '}
                  <strong className="text-slate-100">{fmt(data.speed_kmh, 1, ' km/h')}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Heading:</span>{' '}
                  <strong className="text-slate-100">{fmt(data.heading_deg, 0, '°')}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Latitude:</span>{' '}
                  <strong className="text-slate-300">{fmt(data.lat, 4)}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Longitude:</span>{' '}
                  <strong className="text-slate-300">{fmt(data.lon, 4)}</strong>
                </div>
              </div>
            </div>

            {/* Radio Link & NTN Dynamics */}
            <div className="bg-bg-card border border-border-subtle rounded p-2.5 flex flex-col gap-1.5 font-mono">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                Active RAT & Channel Metrics
              </span>
              <div className="grid grid-cols-2 gap-2 text-[11px] mt-1">
                <div>
                  <span className="text-slate-500">Active Link:</span>{' '}
                  <strong style={{ color: ratColor(data.active_rat) }}>{ratLabel(data.active_rat)}</strong>
                </div>
                <div>
                  <span className="text-slate-500">MEC Latency:</span>{' '}
                  <strong className="text-slate-100">{fmt(data.mec_latency_ms, 1, ' ms')}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Elevation:</span>{' '}
                  <strong className="text-slate-100">{fmt(data.elevation_deg, 1, '°')}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Doppler:</span>{' '}
                  <strong className="text-slate-100">{fmt(data.doppler_khz, 1, ' kHz')}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Slant Range:</span>{' '}
                  <strong className="text-slate-100">{fmt(data.slant_range_km, 0, ' km')}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Battery SoC:</span>{' '}
                  <strong className="text-emerald-400">{fmt(data.battery_soc_pct, 1, '%')}</strong>
                </div>
              </div>

              {data.in_blind && (
                <div className="mt-1 bg-red-950/40 border border-red-500/40 rounded p-1.5 text-[10px] text-red-300 flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-accent-red shrink-0" />
                  <span>Vehicle inside Radio Blind Spot (Severe Outage)</span>
                </div>
              )}
            </div>

            {/* Mini Radar / FoV Component */}
            <MiniRadarView vehicle={data} />
          </>
        )}

        {/* 5G gNodeB Editable Form */}
        {type === 'gnb' && (
          <div className="flex flex-col gap-2 font-mono">
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Latitude"
                value={data.lat}
                step="0.0001"
                min={-90}
                max={90}
                onCommit={(v) => updateNode('gnb', index, { lat: v })}
              />
              <NumberField
                label="Longitude"
                value={data.lon}
                step="0.0001"
                min={-180}
                max={180}
                onCommit={(v) => updateNode('gnb', index, { lon: v })}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Height (m)"
                value={data.height_m}
                min={1}
                max={200}
                onCommit={(v) => updateNode('gnb', index, { height_m: v })}
              />
              <NumberField
                label="Tx Power (dBm)"
                value={data.tx_power_dbm}
                min={0}
                max={60}
                onCommit={(v) => updateNode('gnb', index, { tx_power_dbm: v })}
              />
            </div>
          </div>
        )}

        {/* Ground Station Editable Form */}
        {type === 'gs' && (
          <div className="flex flex-col gap-2 font-mono">
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Latitude"
                value={data.lat}
                step="0.0001"
                min={-90}
                max={90}
                onCommit={(v) => updateNode('gs', index, { lat: v })}
              />
              <NumberField
                label="Longitude"
                value={data.lon}
                step="0.0001"
                min={-180}
                max={180}
                onCommit={(v) => updateNode('gs', index, { lon: v })}
              />
            </div>
            <NumberField
              label="Altitude (m ASL)"
              value={data.altitude_m}
              min={0}
              max={8000}
              onCommit={(v) => updateNode('gs', index, { altitude_m: v })}
            />
          </div>
        )}

        {/* Blind Spot Zone Editable Form */}
        {type === 'blind' && (
          <div className="flex flex-col gap-2 font-mono">
            <NumberField
              label="Attenuation (dB)"
              value={data.attenuation_db}
              min={0}
              max={300}
              onCommit={(v) => updateNode('blind', index, { attenuation_db: v })}
            />
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Lat Min"
                value={data.lat_min}
                step="0.0001"
                min={-90}
                max={90}
                onCommit={(v) => updateNode('blind', index, { lat_min: v })}
              />
              <NumberField
                label="Lat Max"
                value={data.lat_max}
                step="0.0001"
                min={-90}
                max={90}
                onCommit={(v) => updateNode('blind', index, { lat_max: v })}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Lon Min"
                value={data.lon_min}
                step="0.0001"
                min={-180}
                max={180}
                onCommit={(v) => updateNode('blind', index, { lon_min: v })}
              />
              <NumberField
                label="Lon Max"
                value={data.lon_max}
                step="0.0001"
                min={-180}
                max={180}
                onCommit={(v) => updateNode('blind', index, { lon_max: v })}
              />
            </div>
          </div>
        )}

        {/* Delete button for infrastructure nodes */}
        {type !== 'veh' && (
          <div className="mt-auto pt-4 border-t border-border-subtle">
            <button
              onClick={handleDelete}
              className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 bg-red-500/10 hover:bg-red-500/20 text-accent-red border border-red-500/30 rounded font-mono font-bold transition text-xs"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>DELETE NODE FROM SCENARIO</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
