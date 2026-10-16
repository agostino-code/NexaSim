import React, { useMemo, useState } from 'react';
import { Car, Activity, TrendingUp, Battery, ArrowDown, ArrowUp, Filter } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { VehicleTelemetry, RatType } from '../../types/scenario';
import { InfoTip } from '../common/InfoTip';
import { RAT_LABELS, RAT_COLORS, WARNING_COLOR, UNKNOWN_LINK_COLOR } from '../../theme/palette';

const RAT_CLASS: Record<RatType, string> = {
  '5G': 'bg-emerald-500/15 text-accent-green border border-emerald-500/30',
  LEO: 'bg-sky-500/15 text-brand-cyan border border-sky-500/30',
  V2X: 'bg-purple-500/15 text-accent-purple border border-purple-500/30',
};

/** Compact status wording (colour language shared with the map/globe). */
const RAT_STATUS: Record<RatType, string> = {
  '5G': '5G primary link',
  LEO: 'LEO failover active',
  V2X: 'V2X sidelink active',
};

/** "—" for not-recorded (null) metrics; never fabricates a number. */
const fmt = (v: number | null | undefined, digits = 1, suffix = ''): string =>
  v == null || Number.isNaN(v) ? '—' : `${v.toFixed(digits)}${suffix}`;

const meanNonNull = (arr: (number | null | undefined)[]): number | null => {
  const vals = arr.filter((v): v is number => v != null && !Number.isNaN(v));
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
};

type SortKey = 'id' | 'speed' | 'latency' | 'qos' | 'battery' | 'vho';
type SortDir = 'asc' | 'desc';

interface SortHeaderProps {
  label: string;
  sortKey: SortKey;
  active: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
  tip?: string;
  className?: string;
}

const SortHeader: React.FC<SortHeaderProps> = ({
  label,
  sortKey,
  active,
  dir,
  onSort,
  tip,
  className = '',
}) => (
  <th className={`p-2.5 ${className}`}>
    <span className="flex items-center gap-1">
      <button
        onClick={() => onSort(sortKey)}
        className={`flex items-center gap-1 uppercase tracking-wider transition hover:text-slate-200 ${
          active === sortKey ? 'text-brand-cyan' : ''
        }`}
        title={`Sort by ${label}`}
      >
        {label}
        {active === sortKey &&
          (dir === 'asc' ? <ArrowUp size={9} /> : <ArrowDown size={9} />)}
      </button>
      {tip && <InfoTip text={tip} />}
    </span>
  </th>
);

const valueOf = (v: VehicleTelemetry, key: SortKey): number | null => {
  switch (key) {
    case 'id':
      return v.id;
    case 'speed':
      return v.speed_kmh;
    case 'latency':
      return v.mec_latency_ms;
    case 'qos':
      return v.qos_score;
    case 'battery':
      return v.battery_soc_pct;
    case 'vho':
      return v.vho_count;
  }
};

export const FleetMatrixTable: React.FC = () => {
  const vehicles = useStudioStore((s) => s.vehicles);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const hasRunData = useStudioStore((s) => s.hasRunData);
  const [sortKey, setSortKey] = useState<SortKey>('id');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [ratFilter, setRatFilter] = useState<'all' | RatType | 'none'>('all');
  const [blindOnly, setBlindOnly] = useState(false);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'id' ? 'asc' : 'desc');
    }
  };

  const rows = useMemo(() => {
    let list = [...vehicles];
    if (ratFilter === 'none') {
      list = list.filter((v) => !v.active_rat);
    } else if (ratFilter !== 'all') {
      list = list.filter((v) => v.active_rat === ratFilter);
    }
    if (blindOnly) list = list.filter((v) => v.in_blind);
    list.sort((a, b) => {
      const av = valueOf(a, sortKey);
      const bv = valueOf(b, sortKey);
      // Not-recorded values always sort last, regardless of direction
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return sortDir === 'asc' ? av - bv : bv - av;
    });
    return list;
  }, [vehicles, ratFilter, blindOnly, sortKey, sortDir]);

  // Fleet aggregates computed from the actual per-vehicle rows (null-safe)
  const fleetThroughput = meanNonNull(vehicles.map((v) => v.throughput_mbps));
  const fleetLatency = meanNonNull(vehicles.map((v) => v.mec_latency_ms));

  return (
    <div className="flex flex-col h-full bg-bg-base p-3 overflow-hidden select-none">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Car size={14} className="text-brand-cyan" />
          <strong className="text-xs text-slate-100 uppercase tracking-tight">
            Connected Convoy &amp; Fleet Multi-RAT Matrix
          </strong>
        </div>
        <div className="flex items-center gap-2">
          {/* Filters */}
          <span className="flex items-center gap-1 text-[10px] font-mono text-slate-500">
            <Filter size={10} />
          </span>
          <select
            value={ratFilter}
            onChange={(e) => setRatFilter(e.target.value as typeof ratFilter)}
            className="bg-bg-card border border-border-subtle text-slate-300 text-[10px] font-mono rounded px-1.5 py-0.5 outline-none focus:border-brand-cyan cursor-pointer"
            title="Filter by recorded active link"
          >
            <option value="all" className="bg-bg-panel">RAT: all</option>
            <option value="5G" className="bg-bg-panel">RAT: 5G</option>
            <option value="LEO" className="bg-bg-panel">RAT: LEO</option>
            <option value="V2X" className="bg-bg-panel">RAT: V2X</option>
            <option value="none" className="bg-bg-panel">RAT: not recorded</option>
          </select>
          <button
            onClick={() => setBlindOnly((v) => !v)}
            className={`text-[10px] font-mono px-2 py-0.5 rounded border transition ${
              blindOnly
                ? 'bg-amber-500/15 text-accent-amber border-amber-500/40'
                : 'bg-bg-card text-slate-400 border-border-subtle hover:text-slate-200'
            }`}
            title="Show only vehicles currently inside a blind spot"
          >
            ⚠ blind only
          </button>
          <span className="text-[10px] font-mono text-slate-400 bg-bg-card border border-border-subtle px-2 py-0.5 rounded">
            {rows.length}/{vehicles.length} vehicles
          </span>
        </div>
      </div>

      {/* Graceful empty state */}
      {!hasRunData && currentScenario && (
        <div className="flex-1 flex flex-col items-center justify-center bg-bg-panel border border-border-subtle rounded p-6 text-center select-none">
          <div className="text-slate-500 mb-3">⏳</div>
          <h3 className="text-sm font-bold text-slate-200 mb-1">No Fleet Telemetry Yet</h3>
          <p className="text-xs text-slate-400 max-w-xs">
            Run the scenario (▶ Run Simulation in the header) to populate per-vehicle status, active
            RAT and QoS utility from the recorded OMNeT++ vectors. Metrics that were not recorded
            stay marked as “—”.
          </p>
        </div>
      )}

      <div className="flex-1 overflow-auto border border-border-subtle rounded bg-bg-panel">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-bg-panel-solid border-b border-border-subtle text-[10px] font-mono text-slate-400 uppercase tracking-wider sticky top-0 z-10">
              <SortHeader
                label="Vehicle"
                sortKey="id"
                active={sortKey}
                dir={sortDir}
                onSort={handleSort}
              />
              <th className="p-2.5">
                <span className="flex items-center gap-1">
                  Active Link
                  <InfoTip text="Recorded activeInterface link state (vector when available, otherwise the per-node activeInterface:last scalar). '—' = link state not recorded." />
                </span>
              </th>
              <th className="p-2.5">Status</th>
              <SortHeader
                label="Speed (km/h)"
                sortKey="speed"
                active={sortKey}
                dir={sortDir}
                onSort={handleSort}
                tip="Vehicle speed recorded in the FCD / TraCI traces. '—' = not recorded."
              />
              <SortHeader
                label="MEC Latency"
                sortKey="latency"
                active={sortKey}
                dir={sortDir}
                onSort={handleSort}
                tip="MEC task latency / RTT (mecTaskLatency vectors, ms). URLLC target < 50 ms."
              />
              <SortHeader
                label="QoS Score"
                sortKey="qos"
                active={sortKey}
                dir={sortDir}
                onSort={handleSort}
                tip="Multi-criteria QoS utility (qosScore vectors, 0–1)."
              />
              <SortHeader
                label="Battery SoC"
                sortKey="battery"
                active={sortKey}
                dir={sortDir}
                onSort={handleSort}
                tip="Battery state of charge (batterySoC vectors, %)."
              />
              <SortHeader
                label="VHO Switches"
                sortKey="vho"
                active={sortKey}
                dir={sortDir}
                onSort={handleSort}
                tip="Cumulative vertical handovers (switchCount vectors)."
              />
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle font-mono text-[11px]">
            {rows.map((v) => {
              const rat: RatType | null =
                v.active_rat === '5G' || v.active_rat === 'LEO' || v.active_rat === 'V2X'
                  ? v.active_rat
                  : null;
              const inBlind = v.in_blind;
              const isLeader = v.id === 0;
              return (
                <tr key={v.id} className="hover:bg-bg-card transition">
                  <td className="p-2.5 font-sans font-bold text-slate-100">
                    <span className="flex items-center gap-1.5">
                      {rat && (
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ background: inBlind ? WARNING_COLOR : RAT_COLORS[rat] }}
                          title={inBlind ? 'Inside blind spot' : RAT_LABELS[rat]}
                        />
                      )}
                      {!rat && (
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ background: UNKNOWN_LINK_COLOR }}
                          title="Link state not recorded"
                        />
                      )}
                      <span>{v.name}</span>
                      {isLeader && (
                        <span className="text-[9px] bg-amber-500/10 text-accent-amber border border-amber-500/30 px-1 rounded">
                          Leader
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="p-2.5">
                    {rat ? (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${RAT_CLASS[rat]}`}>
                        {RAT_LABELS[rat]}
                      </span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                  <td className="p-2.5">
                    {rat ? (
                      <span className={inBlind ? 'text-accent-amber' : 'text-slate-300'}>
                        {inBlind ? '⚠ blind spot · ' : ''}
                        {RAT_STATUS[rat]}
                      </span>
                    ) : (
                      <span className="text-slate-500">Link state not recorded</span>
                    )}
                  </td>
                  <td className="p-2.5 tabular-nums text-slate-200">{fmt(v.speed_kmh, 1)}</td>
                  <td className="p-2.5 tabular-nums text-brand-cyan">{fmt(v.mec_latency_ms, 1, ' ms')}</td>
                  <td className="p-2.5 tabular-nums text-accent-purple">{fmt(v.qos_score, 2)}</td>
                  <td className="p-2.5 tabular-nums text-slate-200">
                    <span className="flex items-center gap-1">
                      <Battery size={11} className="text-amber-400" />
                      <span>{fmt(v.battery_soc_pct, 1, '%')}</span>
                    </span>
                  </td>
                  <td className="p-2.5 tabular-nums text-slate-300">
                    {v.vho_count != null ? v.vho_count : '—'}
                  </td>
                </tr>
              );
            })}
            {vehicles.length === 0 && (
              <tr>
                <td colSpan={8} className="p-4 text-center text-slate-500 text-[11px] font-mono">
                  No vehicle telemetry recorded for this scenario. Metrics are never synthesized —
                  run a simulation to populate the fleet matrix.
                </td>
              </tr>
            )}
            {vehicles.length > 0 && rows.length === 0 && (
              <tr>
                <td colSpan={8} className="p-4 text-center text-slate-500 text-[11px] font-mono">
                  No vehicles match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Fleet summary strip (means over recorded rows only) */}
      <div className="mt-2 bg-bg-panel border border-border-subtle rounded p-2.5">
        <div className="flex gap-4 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-1">
            <Activity size={10} className="text-brand-cyan" />
            <span>
              Fleet Throughput:{' '}
              <b className="text-slate-100">
                {fleetThroughput != null ? `${fleetThroughput.toFixed(1)} Mbps` : '—'}
              </b>
            </span>
          </div>
          <div className="flex items-center gap-1">
            <TrendingUp size={10} className="text-accent-pink" />
            <span>
              Mean MEC Latency:{' '}
              <b className="text-slate-100">{fleetLatency != null ? `${fleetLatency.toFixed(1)} ms` : '—'}</b>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
