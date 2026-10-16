import React, { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
import { Printer, RefreshCw, Database } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { fetchTelemetry, fetchKpis } from '../../services/api';
import { TelemetrySeries, KpiSummary } from '../../types/scenario';
import { InfoTip } from '../common/InfoTip';
import { Sparkline } from '../common/Sparkline';

/** "—" for not-recorded (null) metrics; never fabricates a number. */
const fmtMetric = (v: number | null | undefined, digits = 1, suffix = ''): string =>
  v == null || Number.isNaN(v) ? '—' : `${v.toFixed(digits)}${suffix}`;

const lastNonNull = (arr?: (number | null)[] | null): number | null => {
  if (!arr) return null;
  for (let i = arr.length - 1; i >= 0; i -= 1) {
    const v = arr[i];
    if (v != null && !Number.isNaN(v)) return v;
  }
  return null;
};

const meanNonNull = (arr?: (number | null)[] | null): number | null => {
  if (!arr) return null;
  const vals = arr.filter((v): v is number => v != null && !Number.isNaN(v));
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
};

const computeHasRunData = (telemetry: TelemetrySeries, kpiData: KpiSummary): boolean =>
  telemetry.timestamps.some((t) => t > 0) ||
  telemetry.throughput_mbps.some((v) => v != null) ||
  telemetry.handover_events.some((v) => v != null) ||
  [
    kpiData.throughput_mbps,
    kpiData.avg_latency_ms,
    kpiData.total_vho_switches,
    kpiData.mean_qos_score,
    kpiData.final_battery_soc,
    kpiData.sat_usage_pct,
  ].some((v) => v != null);

const dominantRat = (telemetry: TelemetrySeries, kpiData: KpiSummary): string | null => {
  const lastRat = lastNonNull(telemetry.active_interface);
  if (lastRat != null) return lastRat >= 0.5 ? 'LEO' : '5G';
  if (kpiData.sat_usage_pct != null) return kpiData.sat_usage_pct > 50 ? 'LEO' : '5G';
  return null;
};

/** Axis title styling shared by all charts (units always explicit). */
const axisTitle = (text: string) => ({
  display: true,
  text,
  color: '#94a3b8',
  font: { family: "'IBM Plex Mono', monospace", size: 10 },
});

export const ExecutiveDashboard: React.FC = () => {
  // Zustand atomic selectors — eliminates full-dashboard re-renders on simTime frame ticks
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const status = useStudioStore((s) => s.status);
  const throughputMbps = useStudioStore((s) => s.throughputMbps);
  const latencyMs = useStudioStore((s) => s.latencyMs);
  const activeRat = useStudioStore((s) => s.activeRat);
  const telemetrySeries = useStudioStore((s) => s.telemetrySeries);
  const kpis = useStudioStore((s) => s.kpis);
  const hasRunData = useStudioStore((s) => s.hasRunData);
  const setTelemetrySeries = useStudioStore((s) => s.setTelemetrySeries);
  const setKpis = useStudioStore((s) => s.setKpis);
  const setHasRunData = useStudioStore((s) => s.setHasRunData);
  const setFleetAggregates = useStudioStore((s) => s.setFleetAggregates);
  const setProvenanceOpen = useStudioStore((s) => s.setProvenanceOpen);

  const chartRef1 = useRef<HTMLCanvasElement>(null);
  const chartRef2 = useRef<HTMLCanvasElement>(null);
  const chartRef3 = useRef<HTMLCanvasElement>(null);
  const chartRef4 = useRef<HTMLCanvasElement>(null);

  // Persistent Chart.js instance references created once on mount
  const chart1Instance = useRef<Chart | null>(null);
  const chart2Instance = useRef<Chart | null>(null);
  const chart3Instance = useRef<Chart | null>(null);
  const chart4Instance = useRef<Chart | null>(null);

  const baseChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false as const,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(11, 17, 24, 0.95)',
        borderColor: '#27374d',
        borderWidth: 1,
        bodyFont: { family: "'IBM Plex Mono', monospace", size: 10 },
        titleFont: { family: "'Space Grotesk', sans-serif", size: 11, weight: 'bold' as const },
      },
    },
    scales: {
      x: {
        type: 'linear' as const,
        grid: { color: 'rgba(28, 40, 56, 0.6)' },
        ticks: { color: '#64748b', font: { family: "'IBM Plex Mono', monospace", size: 9 } },
        title: {
          display: true,
          text: 'Simulation Time (s)',
          color: '#94a3b8',
          font: { family: "'IBM Plex Mono', monospace", size: 10 },
        },
      },
      y: {
        grid: { color: 'rgba(28, 40, 56, 0.6)' },
        ticks: { color: '#64748b', font: { family: "'IBM Plex Mono', monospace", size: 9 } },
      },
    },
  };

  // Load real telemetry + KPI data when scenario changes, guarded with AbortController
  useEffect(() => {
    if (!currentScenario) return;
    const abortCtrl = new AbortController();

    const loadData = async () => {
      try {
        const [telemetry, kpiData] = await Promise.all([
          fetchTelemetry(currentScenario.id, abortCtrl.signal),
          fetchKpis(currentScenario.id, abortCtrl.signal),
        ]);
        setTelemetrySeries(telemetry);
        setKpis(kpiData);
        setHasRunData(computeHasRunData(telemetry, kpiData));
        // Publish the scenario's real aggregates for the system strip.
        setFleetAggregates({
          throughput_mbps: kpiData.throughput_mbps ?? lastNonNull(telemetry.throughput_mbps),
          latency_ms: kpiData.avg_latency_ms ?? lastNonNull(telemetry.rtt_ms),
          active_rat: dominantRat(telemetry, kpiData),
        });
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
        console.error('Failed to load telemetry/KPI data:', err);
      }
    };

    loadData();
    return () => {
      abortCtrl.abort();
    };
  }, [currentScenario?.id, setTelemetrySeries, setKpis, setHasRunData, setFleetAggregates]);

  // QoS series availability (charts + overlay)
  const qosSeries = telemetrySeries?.qos_score ?? [];
  const qosHasSeries = qosSeries.some((v) => v != null);
  const qosMean = kpis?.mean_qos_score ?? null;
  const qosChartEmpty = hasRunData && !qosHasSeries && qosMean == null;

  // Latency / handover series availability ("not recorded" overlays)
  const latencySeries = telemetrySeries?.rtt_ms ?? [];
  const latencyHasSeries = latencySeries.some((v) => v != null);
  const latencyChartEmpty =
    hasRunData && !latencyHasSeries && (kpis?.avg_latency_ms ?? null) == null;

  const handoverSeries = telemetrySeries?.handover_events ?? [];
  const handoverHasSeries = handoverSeries.some((v) => v != null);
  const handoverChartEmpty =
    hasRunData && !handoverHasSeries && (kpis?.total_vho_switches ?? null) == null;

  // Initialize the 4 Chart.js instances ONCE on component mount
  useEffect(() => {
    // Chart 1: Active Interface (stepped 0=5G, 1=Satellite)
    if (chartRef1.current) {
      chart1Instance.current = new Chart(chartRef1.current, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Active RAT (0=5G-NR, 1=Satellite LEO)',
              data: [],
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              borderWidth: 2,
              pointRadius: 0,
              stepped: true,
              fill: true,
            },
          ],
        },
        options: {
          ...baseChartOptions,
          scales: {
            ...baseChartOptions.scales,
            y: {
              ...baseChartOptions.scales.y,
              min: 0,
              max: 1.2,
              title: axisTitle('Link state (0 = 5G · 1 = LEO)'),
            },
          },
        },
      });
    }

    // Chart 2: QoS Score
    if (chartRef2.current) {
      chart2Instance.current = new Chart(chartRef2.current, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'QoS Utility Score (fleet mean)',
              data: [],
              borderColor: '#a855f7',
              backgroundColor: 'rgba(168, 85, 247, 0.1)',
              borderWidth: 2,
              pointRadius: 0,
              fill: true,
            },
          ],
        },
        options: {
          ...baseChartOptions,
          scales: {
            ...baseChartOptions.scales,
            y: {
              ...baseChartOptions.scales.y,
              min: 0,
              max: 1,
              title: axisTitle('QoS utility (0–1)'),
            },
          },
        },
      });
    }

    // Chart 3: MEC Latency (rtt_ms)
    if (chartRef3.current) {
      chart3Instance.current = new Chart(chartRef3.current, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'MEC Latency / RTT (ms)',
              data: [],
              borderColor: '#ec4899',
              backgroundColor: 'rgba(236, 72, 153, 0.1)',
              borderWidth: 2,
              pointRadius: 0,
              fill: true,
            },
          ],
        },
        options: {
          ...baseChartOptions,
          scales: {
            ...baseChartOptions.scales,
            y: {
              ...baseChartOptions.scales.y,
              title: axisTitle('Latency (ms)'),
            },
          },
        },
      });
    }

    // Chart 4: Cumulative Switches (handover_events)
    if (chartRef4.current) {
      chart4Instance.current = new Chart(chartRef4.current, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Cumulative Vertical Handovers',
              data: [],
              borderColor: '#f59e0b',
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              borderWidth: 2,
              pointRadius: 0,
              stepped: true,
              fill: true,
            },
          ],
        },
        options: {
          ...baseChartOptions,
          scales: {
            ...baseChartOptions.scales,
            y: {
              ...baseChartOptions.scales.y,
              title: axisTitle('Handovers (count)'),
            },
          },
        },
      });
    }

    // Destroy instances only on component unmount
    return () => {
      chart1Instance.current?.destroy();
      chart2Instance.current?.destroy();
      chart3Instance.current?.destroy();
      chart4Instance.current?.destroy();
      chart1Instance.current = null;
      chart2Instance.current = null;
      chart3Instance.current = null;
      chart4Instance.current = null;
    };
  }, []);

  // In-place dataset updates without recreating Chart instances
  useEffect(() => {
    const timestamps = telemetrySeries ? telemetrySeries.timestamps : [];

    // Update Chart 1
    const c1 = chart1Instance.current;
    if (c1) {
      c1.data.labels = timestamps;
      c1.data.datasets[0].data = telemetrySeries ? telemetrySeries.active_interface : [];
      c1.update('none');
    }

    // Update Chart 2
    const c2 = chart2Instance.current;
    if (c2) {
      const qosData = qosHasSeries
        ? qosSeries
        : qosMean != null
          ? timestamps.map(() => qosMean)
          : [];
      const qosLabel = qosHasSeries
        ? 'QoS Utility Score (fleet mean)'
        : qosMean != null
          ? 'QoS Utility (KPI mean — series not recorded)'
          : 'QoS — not recorded';
      c2.data.labels = timestamps;
      c2.data.datasets[0].data = qosData;
      c2.data.datasets[0].label = qosLabel;
      c2.update('none');
    }

    // Update Chart 3
    const c3 = chart3Instance.current;
    if (c3) {
      c3.data.labels = timestamps;
      c3.data.datasets[0].data = telemetrySeries ? telemetrySeries.rtt_ms : [];
      c3.update('none');
    }

    // Update Chart 4
    const c4 = chart4Instance.current;
    if (c4) {
      c4.data.labels = timestamps;
      c4.data.datasets[0].data = telemetrySeries ? telemetrySeries.handover_events : [];
      c4.update('none');
    }
  }, [telemetrySeries, kpis, qosHasSeries, qosSeries, qosMean]);

  // Reload real telemetry + KPI data (used by the toolbar and empty-state CTA)
  const handleReload = async () => {
    if (!currentScenario) return;
    try {
      const [telemetry, kpiData] = await Promise.all([
        fetchTelemetry(currentScenario.id),
        fetchKpis(currentScenario.id),
      ]);
      setTelemetrySeries(telemetry);
      setKpis(kpiData);
      setHasRunData(computeHasRunData(telemetry, kpiData));
      setFleetAggregates({
        throughput_mbps: kpiData.throughput_mbps ?? lastNonNull(telemetry.throughput_mbps),
        latency_ms: kpiData.avg_latency_ms ?? lastNonNull(telemetry.rtt_ms),
        active_rat: dominantRat(telemetry, kpiData),
      });
    } catch (err) {
      console.error('Failed to reload telemetry/KPI data:', err);
    }
  };

  // Derive KPI card values from real recorded data; null => rendered as "—".
  // While a live run is active, prefer the streaming aggregates.
  const kpiThroughput = hasRunData
    ? kpis?.throughput_mbps ?? lastNonNull(telemetrySeries?.throughput_mbps)
    : null;
  const kpiLatency = hasRunData
    ? kpis?.avg_latency_ms ?? lastNonNull(telemetrySeries?.rtt_ms)
    : null;
  const kpiVho = hasRunData
    ? kpis?.total_vho_switches ?? lastNonNull(telemetrySeries?.handover_events)
    : null;
  const kpiQos = hasRunData
    ? kpis?.mean_qos_score ?? meanNonNull(telemetrySeries?.qos_score)
    : null;
  const satPct: number | null =
    hasRunData && kpis?.sat_usage_pct != null ? kpis.sat_usage_pct : null;
  const cellPct: number | null =
    hasRunData && kpis?.cell_usage_pct != null ? kpis.cell_usage_pct : null;

  const throughput = status.running && throughputMbps != null ? throughputMbps : kpiThroughput;
  const latency = status.running && latencyMs != null ? latencyMs : kpiLatency;
  const vhoCount = kpiVho;
  const qosScore = kpiQos;

  const effectiveRat =
    status.running && activeRat
      ? activeRat
      : telemetrySeries
        ? dominantRat(telemetrySeries, kpis ?? { scenario: '' })
        : null;
  const ratLabel =
    effectiveRat === 'LEO' ? 'Satellite LEO' : effectiveRat === '5G' ? '5G-NR Terrestrial' : effectiveRat === 'V2X' ? 'V2X' : 'IDLE';
  const emptyState = !hasRunData && !currentScenario;

  return (
    <div className="flex flex-col h-full p-3 bg-bg-base overflow-y-auto select-none gap-3">
      {/* Top Banner Toolbar */}
      <div className="flex items-center justify-between bg-bg-panel border border-border-subtle p-2 rounded">
        <div>
          <span className="text-[10px] font-mono font-bold text-accent-amber uppercase tracking-wider block">
            Executive Mission Report
          </span>
          <strong className="text-xs text-slate-100">
            {currentScenario ? currentScenario.name : 'All Scenarios'}
          </strong>
          {!hasRunData && currentScenario && (
            <span className="ml-2 text-[9px] bg-amber-500/10 text-accent-amber border border-amber-500/30 px-1.5 py-0.5 rounded uppercase">
              awaiting run data
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setProvenanceOpen(true)}
            className="flex items-center gap-1 px-2.5 py-1 bg-bg-card hover:bg-bg-card-hover border border-border-medium rounded text-[11px] font-semibold text-slate-300"
            title="Data & Sources — what is recorded, derived, and never synthesized"
          >
            <Database size={12} /> Sources
          </button>
          <button
            onClick={handleReload}
            className="flex items-center gap-1 px-2.5 py-1 bg-bg-card hover:bg-bg-card-hover border border-border-medium rounded text-[11px] font-semibold text-slate-300"
            title="Reload the recorded telemetry vectors and KPI summary"
          >
            <RefreshCw size={12} /> Reload Data
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1 px-2.5 py-1 bg-bg-card hover:bg-bg-card-hover border border-border-medium rounded text-[11px] font-semibold text-slate-300"
          >
            <Printer size={12} /> Print PDF
          </button>
        </div>
      </div>

      {/* Graceful empty state when no simulation has run */}
      {!hasRunData && currentScenario && (
        <div className="flex flex-col items-center justify-center h-full bg-bg-panel border border-border-subtle rounded p-6 text-center select-none">
          <div className="text-slate-500 mb-3">⏳</div>
          <h3 className="text-sm font-bold text-slate-200 mb-1">No Simulation Data Yet</h3>
          <p className="text-xs text-slate-400 max-w-xs mb-2">
            Run the '{currentScenario.name}' scenario from the Studio control panel (
            <b className="text-slate-300">▶ Run Simulation</b> in the header) to populate real
            OMNeT++ telemetry vectors (datarateSelected, mecTaskLatency, switchCount,
            activeInterface) and the KPI summary.
          </p>
          <p className="text-[10px] text-slate-500 max-w-xs mb-4">
            Already ran it outside the Studio? Reload to pick up the recorded results.
          </p>
          <button
            onClick={handleReload}
            className="px-4 py-2 bg-bg-card border border-border-medium hover:border-brand-cyan hover:text-brand-cyan text-slate-100 text-xs font-semibold rounded transition flex items-center gap-1.5"
          >
            <RefreshCw size={14} /> Reload Recorded Data
          </button>
        </div>
      )}

      {/* KPI Cards Grid (real data; "—" when the metric was never recorded) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded relative overflow-hidden">
          <div className="h-0.5 w-full bg-accent-green absolute top-0 left-0" />
          <div className="text-[10px] uppercase font-mono font-bold text-slate-400 flex items-center gap-1">
            <span>5G Terrestrial</span>
            <InfoTip text="Share of recorded samples where the active interface was the 5G-NR cell (cell_usage_pct KPI). '—' = not recorded." />
          </div>
          <div className="text-lg font-bold font-mono text-slate-100 mt-0.5 tabular-nums">
            {fmtMetric(cellPct, 1, '%')}
          </div>
          <div className="text-[10px] text-slate-400">Primary cellular</div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded relative overflow-hidden">
          <div className="h-0.5 w-full bg-brand-cyan absolute top-0 left-0" />
          <div className="text-[10px] uppercase font-mono font-bold text-slate-400 flex items-center gap-1">
            <span>LEO Satellite</span>
            <InfoTip text="Share of recorded samples where the active interface was the LEO satellite link (sat_usage_pct KPI). '—' = not recorded." />
          </div>
          <div className="text-lg font-bold font-mono text-slate-100 mt-0.5 tabular-nums">
            {fmtMetric(satPct, 1, '%')}
          </div>
          <div className="text-[10px] text-slate-400">NTN space backhaul</div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded relative overflow-hidden">
          <div className="h-0.5 w-full bg-accent-amber absolute top-0 left-0" />
          <div className="text-[10px] uppercase font-mono font-bold text-slate-400 flex items-center gap-1">
            <span>VHO Switches</span>
            <InfoTip text="Vertical handovers recorded in the switchCount vectors (make-before-break 5G ⇄ LEO switching)." />
          </div>
          <div className="flex items-end justify-between gap-1 mt-0.5">
            <div className="text-lg font-bold font-mono text-slate-100 tabular-nums">
              {vhoCount != null ? vhoCount : '—'}
            </div>
            <Sparkline data={handoverSeries} color="#f59e0b" />
          </div>
          <div className="text-[10px] text-slate-400">Make-before-break</div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded relative overflow-hidden">
          <div className="h-0.5 w-full bg-accent-purple absolute top-0 left-0" />
          <div className="text-[10px] uppercase font-mono font-bold text-slate-400 flex items-center gap-1">
            <span>QoS Utility</span>
            <InfoTip text="Fleet-mean multi-criteria QoS utility (qosScore / mean_qos_score), 0–1. '—' = not recorded." />
          </div>
          <div className="flex items-end justify-between gap-1 mt-0.5">
            <div className="text-lg font-bold font-mono text-slate-100 tabular-nums">
              {fmtMetric(qosScore, 3)}
            </div>
            <Sparkline data={qosSeries} color="#a855f7" />
          </div>
          <div className="text-[10px] text-slate-400">Optimal (0.0–1.0)</div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded relative overflow-hidden">
          <div className="h-0.5 w-full bg-accent-pink absolute top-0 left-0" />
          <div className="text-[10px] uppercase font-mono font-bold text-slate-400 flex items-center gap-1">
            <span>MEC Latency</span>
            <InfoTip text="MEC task latency / RTT (mecTaskLatency vectors, avg_latency_ms KPI). URLLC target < 50 ms. '—' = not recorded." />
          </div>
          <div className="flex items-end justify-between gap-1 mt-0.5">
            <div className="text-lg font-bold font-mono text-slate-100 tabular-nums">
              {fmtMetric(latency, 1, ' ms')}
            </div>
            <Sparkline data={latencySeries} color="#ec4899" />
          </div>
          <div className="text-[10px] text-slate-400">URLLC &lt; 50 ms</div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded relative overflow-hidden">
          <div className="h-0.5 w-full bg-brand-blue absolute top-0 left-0" />
          <div className="text-[10px] uppercase font-mono font-bold text-slate-400 flex items-center gap-1">
            <span>Throughput</span>
            <InfoTip text="Aggregated selected datarate (datarateSelected vectors / throughput_mbps KPI). '—' = not recorded." />
          </div>
          <div className="flex items-end justify-between gap-1 mt-0.5">
            <div className="text-lg font-bold font-mono text-slate-100 tabular-nums">
              {throughput != null ? `${throughput.toFixed(1)}M` : '—'}
            </div>
            <Sparkline data={telemetrySeries?.throughput_mbps} color="#3b82f6" />
          </div>
          <div className="text-[10px] text-slate-400">Aggregated rate</div>
        </div>
      </div>

      {/* 2x2 Charts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 flex-1 min-h-[360px]">
        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded flex flex-col">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-bold text-slate-200 flex items-center gap-1">
              Active RAT Transition (5G vs Satellite)
              <InfoTip text="Recorded activeInterface vector: 0 = 5G-NR terrestrial, 1 = LEO satellite. Stepped line = switching events." />
            </span>
            <span
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                effectiveRat === 'LEO' ? 'bg-sky-500/10 text-brand-cyan border border-sky-500/30' : 'bg-emerald-500/10 text-accent-green border border-emerald-500/30'
              }`}
            >
              {ratLabel}
            </span>
          </div>
          <div className="flex-1 relative min-h-[140px]">
            <canvas ref={chartRef1} />
            {emptyState && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 pointer-events-none">
                <span className="text-[10px] text-slate-400 font-mono">No vector data — run a simulation</span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded flex flex-col">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-bold text-slate-200 flex items-center gap-1">
              Multi-Criteria QoS Utility Score
              <InfoTip text="qosScore vectors (fleet mean); when the series was not recorded the KPI mean is drawn as a flat reference line." />
            </span>
            <span className="text-[9px] font-mono bg-purple-500/10 text-accent-purple px-1.5 py-0.5 rounded">
              &gt; 0.85 Target
            </span>
          </div>
          <div className="flex-1 relative min-h-[140px]">
            <canvas ref={chartRef2} />
            {qosChartEmpty && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[10px] text-slate-400 font-mono">QoS series not recorded</span>
                <span className="text-[9px] text-slate-500 font-mono">
                  run a simulation to capture qosScore vectors
                </span>
              </div>
            )}
            {emptyState && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 pointer-events-none">
                <span className="text-[10px] text-slate-400 font-mono">No vector data — run a simulation</span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded flex flex-col">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-bold text-slate-200 flex items-center gap-1">
              End-to-End Latency &amp; MEC Compute
              <InfoTip text="mecTaskLatency / RTT vectors in milliseconds. '—' and the overlay mean the metric was not recorded by this run." />
            </span>
            <span className="text-[9px] font-mono bg-pink-500/10 text-accent-pink px-1.5 py-0.5 rounded">
              URLLC Delay
            </span>
          </div>
          <div className="flex-1 relative min-h-[140px]">
            <canvas ref={chartRef3} />
            {latencyChartEmpty && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[10px] text-slate-400 font-mono">Latency series not recorded</span>
                <span className="text-[9px] text-slate-500 font-mono">
                  no mecTaskLatency / rtt vectors in this run
                </span>
              </div>
            )}
            {emptyState && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 pointer-events-none">
                <span className="text-[10px] text-slate-400 font-mono">No vector data — run a simulation</span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-bg-panel border border-border-subtle p-2.5 rounded flex flex-col">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-bold text-slate-200 flex items-center gap-1">
              Cumulative Seamless Handovers
              <InfoTip text="switchCount vectors: cumulative vertical handovers (5G ⇄ LEO) per the make-before-break strategy." />
            </span>
            <span className="text-[9px] font-mono bg-amber-500/10 text-accent-amber px-1.5 py-0.5 rounded">
              Zero Loss
            </span>
          </div>
          <div className="flex-1 relative min-h-[140px]">
            <canvas ref={chartRef4} />
            {handoverChartEmpty && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[10px] text-slate-400 font-mono">Handover series not recorded</span>
                <span className="text-[9px] text-slate-500 font-mono">
                  no switchCount vectors in this run
                </span>
              </div>
            )}
            {emptyState && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 pointer-events-none">
                <span className="text-[10px] text-slate-400 font-mono">No vector data — run a simulation</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
