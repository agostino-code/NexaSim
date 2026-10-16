import React from 'react';
import { X, Database, Route, ShieldCheck, AlertTriangle } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

interface ProvenanceSectionProps {
  icon: React.ReactNode;
  title: string;
  tone?: 'default' | 'amber';
  children: React.ReactNode;
}

const ProvenanceSection: React.FC<ProvenanceSectionProps> = ({
  icon,
  title,
  tone = 'default',
  children,
}) => (
  <div
    className={`border rounded p-3 ${
      tone === 'amber'
        ? 'bg-amber-500/5 border-amber-500/25'
        : 'bg-bg-card border-border-subtle'
    }`}
  >
    <div className="flex items-center gap-2 mb-2">
      <span className={tone === 'amber' ? 'text-accent-amber' : 'text-brand-cyan'}>{icon}</span>
      <span className="text-xs font-bold text-slate-100 uppercase tracking-tight">{title}</span>
    </div>
    <div className="text-[11px] text-slate-300 leading-relaxed flex flex-col gap-1.5">
      {children}
    </div>
  </div>
);

/**
 * "Data & Sources" panel: a single place that documents what is recorded,
 * what is geometric derivation, and what the Studio refuses to synthesize.
 */
export const DataProvenanceModal: React.FC = () => {
  const provenanceOpen = useStudioStore((s) => s.provenanceOpen);
  const setProvenanceOpen = useStudioStore((s) => s.setProvenanceOpen);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const hasRunData = useStudioStore((s) => s.hasRunData);
  const wsConnected = useStudioStore((s) => s.wsConnected);
  const status = useStudioStore((s) => s.status);

  if (!provenanceOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={() => setProvenanceOpen(false)}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] flex flex-col bg-bg-panel border border-border-medium rounded-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle bg-bg-panel-solid">
          <div className="flex items-center gap-2">
            <Database size={16} className="text-brand-cyan" />
            <div>
              <span className="text-sm font-bold text-slate-100">Data &amp; Sources</span>
              <span className="block text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                What is measured, what is derived, what is never invented
              </span>
            </div>
          </div>
          <button
            onClick={() => setProvenanceOpen(false)}
            className="text-slate-500 hover:text-slate-200 transition p-1"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          {/* Current scenario status */}
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
            <span className="text-slate-400 uppercase tracking-wider">Scenario:</span>
            <b className="text-slate-100">{currentScenario ? currentScenario.name : 'None selected'}</b>
            {currentScenario && (
              <span
                className={`px-1.5 py-0.5 rounded border ${
                  hasRunData
                    ? 'bg-emerald-500/10 text-accent-green border-emerald-500/30'
                    : 'bg-amber-500/10 text-accent-amber border-amber-500/30'
                }`}
              >
                {hasRunData ? 'recordings found' : 'no recordings yet'}
              </span>
            )}
            <span
              className={`px-1.5 py-0.5 rounded border ${
                status.running
                  ? 'bg-sky-500/10 text-brand-cyan border-sky-500/30'
                  : 'bg-bg-card text-slate-500 border-border-subtle'
              }`}
            >
              {status.running ? 'live run streaming' : wsConnected ? 'ws connected' : 'ws offline'}
            </span>
          </div>

          <ProvenanceSection icon={<Database size={14} />} title="Recorded by the simulation (source of truth)">
            <p>
              <b className="text-slate-100">OMNeT++ vectors</b> —{' '}
              <span className="font-mono text-[10px] text-brand-cyan">
                .vec / exported_vectors.csv
              </span>
              : <span className="font-mono text-[10px]">datarateSelected</span> (throughput),{' '}
              <span className="font-mono text-[10px]">mecTaskLatency</span> (MEC latency),{' '}
              <span className="font-mono text-[10px]">switchCount</span> (vertical handovers),{' '}
              <span className="font-mono text-[10px]">activeInterface</span> (5G vs LEO),{' '}
              <span className="font-mono text-[10px]">qosScore</span>,{' '}
              <span className="font-mono text-[10px]">batterySoC</span>.
            </p>
            <p>
              <b className="text-slate-100">KPI summary</b> —{' '}
              <span className="font-mono text-[10px]">kpi_summary.json</span>: aggregate packet
              delivery, cell/satellite usage, mean QoS, mean latency.
            </p>
            <p>
              <b className="text-slate-100">Vehicle kinematics &amp; routes</b> — TraCI FCD /{' '}
              <span className="font-mono text-[10px]">route_geo.json</span>: recorded positions,
              speed and the route corridor drawn on the 2D map.
            </p>
          </ProvenanceSection>

          <ProvenanceSection icon={<Route size={14} />} title="Derived geometry (physics / geometry — labelled in the UI)">
            <p>
              <b className="text-slate-100">Heading arrows</b> (2D map): bearing between consecutive
              recorded positions, or the direction of the route segment when the position itself is
              interpolated.
            </p>
            <p>
              <b className="text-slate-100">Dashed “derived link”</b> (2D map): line to the nearest
              infrastructure node for the <i>recorded</i> RAT — a geometric estimate of the serving
              node, not a measured association.
            </p>
            <p>
              <b className="text-slate-100">LEO beams, elevation, slant range, Doppler</b> (3D globe):
              computed from the propagated Keplerian ephemeris of the constellation — real orbital
              mechanics, but not a simulated radio measurement.
            </p>
            <p>
              <b className="text-slate-100">Coverage circles / satellite footprints</b>: from the
              configured gNB radius and the elevation mask — configuration geometry.
            </p>
          </ProvenanceSection>

          <ProvenanceSection
            icon={<ShieldCheck size={14} />}
            title="Never synthesized"
            tone="amber"
          >
            <p>
              Metrics that were not recorded are shown as{' '}
              <b className="font-mono text-accent-amber">—</b>{' '}
              (“not recorded”) — in the map popups, the fleet table, the KPI cards and the globe HUD.
              Charts without recorded series display an explicit “not recorded” overlay instead of a
              fabricated line.
            </p>
            <p className="flex items-start gap-1.5">
              <AlertTriangle size={12} className="text-accent-amber mt-0.5 shrink-0" />
              <span>
                The same colour language is used everywhere: green = 5G, cyan = LEO, purple = V2X,
                slate = not recorded, amber = warning (blind spot), red = blind-spot zone.
              </span>
            </p>
          </ProvenanceSection>
        </div>
      </div>
    </div>
  );
};
