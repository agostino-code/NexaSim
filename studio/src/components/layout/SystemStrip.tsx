import React from 'react';
import { Activity, Clock, Radio, Wifi } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

export const SystemStrip: React.FC = () => {
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const status = useStudioStore((s) => s.status);
  const throughputMbps = useStudioStore((s) => s.throughputMbps);
  const latencyMs = useStudioStore((s) => s.latencyMs);
  const activeRat = useStudioStore((s) => s.activeRat);
  const wsConnected = useStudioStore((s) => s.wsConnected);

  const getStatusTone = () => {
    if (status.running) return 'bg-brand-cyan shadow-cyan-500/50';
    if (status.exit_code === 0) return 'bg-accent-green shadow-emerald-500/50';
    if (status.exit_code && status.exit_code !== 0) return 'bg-accent-red shadow-red-500/50';
    return 'bg-accent-amber shadow-amber-500/50';
  };

  const getStatusText = () => {
    if (status.running) return 'SIMULATION IN PROGRESS';
    if (status.exit_code === 0) return 'RUN COMPLETED (EXIT 0)';
    if (status.exit_code && status.exit_code !== 0) return `RUN FAILED (EXIT ${status.exit_code})`;
    return 'READY FOR DISPATCH';
  };

  return (
    <div className="h-8 bg-bg-panel-solid border-b border-border-subtle flex items-center justify-between px-4 text-[10px] font-mono uppercase tracking-wider text-slate-400 z-40 overflow-x-auto whitespace-nowrap flex-shrink-0">
      {/* State & Dispatch Status */}
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${getStatusTone()} shadow`} />
        <strong className="text-slate-100 font-semibold">{getStatusText()}</strong>
      </div>

      {/* Scenario Context */}
      <div className="flex items-center gap-2 text-slate-300">
        <span className="font-semibold text-slate-100">
          {currentScenario ? currentScenario.name : 'No Scenario Selected'}
        </span>
        <span className="w-px h-3 bg-border-medium" />
        <span className="text-slate-400">
          {currentScenario
            ? `${currentScenario.area_name} • ${currentScenario.duration_s}s`
            : 'LOCAL CONTROL PLANE'}
        </span>
      </div>

      {/* Live Telemetry Chips */}
      <div className="flex items-center gap-2">
        <div
          className="flex items-center gap-1.5 bg-bg-card border border-border-subtle px-2 py-0.5 rounded text-slate-300"
          title="Fleet-mean selected datarate (datarateSelected vectors / KPI summary)"
        >
          <Activity size={11} className="text-accent-green" />
          <span>THROUGHPUT:</span>
          <b className="text-brand-cyan tabular-nums">
            {throughputMbps != null ? `${throughputMbps.toFixed(1)} Mbps` : '—'}
          </b>
        </div>
        <div
          className="flex items-center gap-1.5 bg-bg-card border border-border-subtle px-2 py-0.5 rounded text-slate-300"
          title="Fleet-mean MEC task latency (mecTaskLatency / RTT). '—' = not recorded."
        >
          <Clock size={11} className="text-amber-400" />
          <span>MEC LATENCY:</span>
          <b className="text-brand-cyan tabular-nums">
            {latencyMs != null ? `${latencyMs.toFixed(1)} ms` : '—'}
          </b>
        </div>
        <div
          className="flex items-center gap-1.5 bg-bg-card border border-border-subtle px-2 py-0.5 rounded text-slate-300"
          title="Dominant recorded link state (activeInterface vectors). '—' = link state not recorded."
        >
          <Radio size={11} className="text-accent-purple" />
          <span>DOMINANT RAT:</span>
          <b className={activeRat ? 'text-accent-green' : 'text-slate-500'}>
            {activeRat ?? '—'}
          </b>
        </div>
        <div className="flex items-center gap-1.5 text-slate-400 pl-1">
          <Wifi size={11} className={wsConnected ? 'text-accent-green' : 'text-slate-600'} />
          <span className={wsConnected ? 'text-accent-green font-semibold' : 'text-slate-500'}>
            {wsConnected ? 'WS STREAM LIVE' : 'WS OFFLINE'}
          </span>
        </div>
      </div>
    </div>
  );
};
