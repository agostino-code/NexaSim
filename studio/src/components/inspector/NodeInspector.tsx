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
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { deleteNode } from '../../services/api';
import { ratLabel } from '../../theme/palette';

/** "—" for not-recorded (null) metrics; never fabricates a number. */
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
    <label className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">{label}</label>
    <input
      type="number"
      step={step}
      min={min}
      max={max}
      value={value ?? ''}
      placeholder="not recorded"
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === '') return; // never silently zero a missing value
        const n = parseFloat(raw);
        if (!Number.isNaN(n)) onCommit(n);
      }}
      className="w-full bg-bg-card border border-border-subtle px-2 py-1 rounded text-slate-100 outline-none focus:border-brand-cyan placeholder:text-slate-600"
    />
  </div>
);

export const NodeInspector: React.FC = () => {
  const selectedNode = useStudioStore((s) => s.selectedNode);
  const selectNode = useStudioStore((s) => s.selectNode);
  const updateNode = useStudioStore((s) => s.updateNode);
  const removeNode = useStudioStore((s) => s.removeNode);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const appendLog = useStudioStore((s) => s.appendLog);
  const requestFlyTo = useStudioStore((s) => s.requestFlyTo);
  const vehicles = useStudioStore((s) => s.vehicles);

  if (!selectedNode || !selectedNode.data) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4 text-center text-slate-500 bg-bg-panel select-none">
        <Settings2 size={36} className="text-slate-600 mb-2" />
        <span className="text-xs font-semibold text-slate-400">No Element Selected</span>
        <p className="text-[11px] text-slate-600 max-w-[200px] mt-1">
          Click any 5G cell, gateway, blind spot or vehicle on the 2D map / 3D globe to inspect
          properties.
        </p>
      </div>
    );
  }

  const { type, index, data } = selectedNode;

  // For vehicles, merge the latest recorded telemetry snapshot
  const vehLive = type === 'veh' ? vehicles.find((v) => v.id === (data.id as number)) : undefined;
  const display = type === 'veh' ? { ...data, ...(vehLive ?? {}) } : data;

  const focusPoint = (): [number, number] | null => {
    if (type === 'gnb' || type === 'gs') {
      if (display.lat == null || display.lon == null) return null;
      return [display.lat as number, display.lon as number];
    }
    if (type === 'blind') {
      if (data.lat_min == null || data.lat_max == null || data.lon_min == null || data.lon_max == null)
        return null;
      return [(data.lat_min + data.lat_max) / 2, (data.lon_min + data.lon_max) / 2];
    }
    if (display.lat != null && display.lon != null) return [display.lat as number, display.lon as number];
    return null;
  };

  const handleFocus2D = () => {
    const p = focusPoint();
    if (p) requestFlyTo(type, index, p[0], p[1]);
  };

  const handleTrack3D = () => {
    if (type === 'blind') return; // no blind-spot entity in the 3D scene
    const p = focusPoint();
    requestFlyTo(type, index, p?.[0] ?? 0, p?.[1] ?? 0);
  };

  const handleDelete = async () => {
    if (!currentScenario || type === 'veh') return;
    try {
      await deleteNode(currentScenario.id, type, data.name);
      removeNode(type, index);
      appendLog(`[-] Node '${data.name}' deleted.`);
    } catch (err: any) {
      appendLog(`[!] Delete error: ${err.message}`);
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'gnb':
        return <Radio size={14} className="text-accent-green" />;
      case 'gs':
        return <Satellite size={14} className="text-amber-400" />;
      case 'blind':
        return <ShieldAlert size={14} className="text-accent-red" />;
      case 'veh':
        return <Car size={14} className="text-brand-cyan" />;
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg-panel border-l border-border-subtle text-slate-200 select-none overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border-subtle bg-bg-panel-solid">
        <div className="flex items-center gap-2">
          {getIcon()}
          <span className="text-xs font-bold text-slate-100 uppercase tracking-tight">
            {type === 'gnb' ? '5G gNodeB' : type === 'gs' ? 'Gateway' : type === 'blind' ? 'Blind Spot' : 'Vehicle'}
          </span>
        </div>
        <button
          onClick={() => selectNode(null)}
          className="text-slate-500 hover:text-slate-200 transition"
          title="Close inspector"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body Form */}
      <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-2.5 text-xs font-mono">
        <div>
          <label className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
            Identifier
          </label>
          <input
            type="text"
            value={data.name || ''}
            disabled={type === 'veh'}
            onChange={(e) => updateNode(type, index, { name: e.target.value })}
            className="w-full bg-bg-card border border-border-subtle px-2 py-1 rounded text-slate-100 outline-none focus:border-brand-cyan disabled:opacity-70"
          />
        </div>

        {(type === 'gnb' || type === 'gs') && (
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="Latitude"
              value={display.lat}
              step="0.0001"
              min={-90}
              max={90}
              onCommit={(v) => updateNode(type, index, { lat: v })}
            />
            <NumberField
              label="Longitude"
              value={display.lon}
              step="0.0001"
              min={-180}
              max={180}
              onCommit={(v) => updateNode(type, index, { lon: v })}
            />
          </div>
        )}

        {type === 'gnb' && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Height (m)"
                value={display.height_m}
                min={0}
                max={300}
                onCommit={(v) => updateNode(type, index, { height_m: v })}
              />
              <NumberField
                label="Tx Power (dBm)"
                value={display.tx_power_dbm}
                min={-20}
                max={80}
                onCommit={(v) => updateNode(type, index, { tx_power_dbm: v })}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Freq (GHz)"
                value={display.frequency_ghz}
                step="0.1"
                min={0.4}
                max={100}
                onCommit={(v) => updateNode(type, index, { frequency_ghz: v })}
              />
              <NumberField
                label="Radius (m)"
                value={display.coverage_radius_m}
                min={50}
                max={50000}
                onCommit={(v) => updateNode(type, index, { coverage_radius_m: v })}
              />
            </div>
          </>
        )}

        {type === 'gs' && (
          <NumberField
            label="Altitude (m ASL)"
            value={display.altitude_m}
            min={-500}
            max={9000}
            onCommit={(v) => updateNode(type, index, { altitude_m: v })}
          />
        )}

        {type === 'blind' && (
          <>
            <NumberField
              label="Attenuation (dB)"
              value={data.attenuation_db}
              min={0}
              max={300}
              onCommit={(v) => updateNode(type, index, { attenuation_db: v })}
            />
            <div className="grid grid-cols-2 gap-2">
              <NumberField
                label="Lat Min"
                value={data.lat_min}
                step="0.0001"
                min={-90}
                max={90}
                onCommit={(v) => updateNode(type, index, { lat_min: v })}
              />
              <NumberField
                label="Lat Max"
                value={data.lat_max}
                step="0.0001"
                min={-90}
                max={90}
                onCommit={(v) => updateNode(type, index, { lat_max: v })}
              />
            </div>
          </>
        )}

        {/* Vehicle: read-only recorded telemetry (never editable, never invented) */}
        {type === 'veh' && (
          <div className="border border-border-subtle rounded bg-bg-card/60 p-2.5 flex flex-col gap-1 text-[11px]">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-0.5">
              Recorded telemetry
            </span>
            <div className="flex justify-between">
              <span className="text-slate-500">Active link</span>
              <span className="text-slate-200">{ratLabel(display.active_rat ?? null)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Speed</span>
              <span className="text-slate-200">{fmt(display.speed_kmh, 1, ' km/h')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">MEC latency</span>
              <span className="text-slate-200">{fmt(display.mec_latency_ms, 1, ' ms')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">QoS utility</span>
              <span className="text-slate-200">{fmt(display.qos_score, 3)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Battery SoC</span>
              <span className="text-slate-200">{fmt(display.battery_soc_pct, 1, '%')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">VHO switches</span>
              <span className="text-slate-200">{display.vho_count ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Blind spot</span>
              <span className={display.in_blind ? 'text-accent-amber' : 'text-slate-200'}>
                {display.in_blind ? '⚠ inside' : 'no'}
              </span>
            </div>
            {display.lat == null && (
              <span className="text-[10px] text-slate-500 mt-1 leading-relaxed">
                Position not recorded for this vehicle — the map draws it interpolated along the
                recorded route (labelled as derived).
              </span>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="p-3 border-t border-border-subtle bg-bg-panel-solid flex items-center justify-between gap-1.5 flex-wrap">
        <button
          onClick={handleDelete}
          disabled={type === 'veh'}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-accent-red hover:bg-red-500/10 border border-red-500/30 rounded transition disabled:opacity-40 disabled:cursor-not-allowed"
          title={type === 'veh' ? 'Vehicles come from the simulation — not removable' : 'Delete this node'}
        >
          <Trash2 size={12} /> Delete
        </button>
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleFocus2D}
            disabled={!focusPoint()}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-200 hover:text-brand-cyan hover:border-brand-cyan border border-border-medium rounded transition disabled:opacity-40 disabled:cursor-not-allowed"
            title="Fly the 2D map to this element"
          >
            <MapPin size={12} /> Focus 2D
          </button>
          <button
            onClick={handleTrack3D}
            disabled={type === 'blind'}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-200 hover:text-brand-cyan hover:border-brand-cyan border border-border-medium rounded transition disabled:opacity-40 disabled:cursor-not-allowed"
            title={
              type === 'blind'
                ? 'Blind spots exist only on the 2D map'
                : 'Track this entity in the 3D globe'
            }
          >
            <Crosshair size={12} /> Track 3D
          </button>
        </div>
      </div>
    </div>
  );
};
