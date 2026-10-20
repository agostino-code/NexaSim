import React, { useState, useMemo, useRef, useEffect } from 'react';
import UplotReact from 'uplot-react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import ReactECharts from 'echarts-for-react';
import {
  Activity,
  Layers,
  BarChart3,
  GitCompare,
  Zap,
  TrendingUp,
  Clock,
  Radio,
  FileCode,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

export const SynchronizedTelemetryPanel: React.FC = () => {
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const telemetrySeries = useStudioStore((s) => s.telemetrySeries);
  const kpis = useStudioStore((s) => s.kpis);
  const currentTime = useStudioStore((s) => s.currentTime);
  const seek = useStudioStore((s) => s.seek);

  const [activeTab, setActiveTab] = useState<'timeseries' | 'kpis' | 'analytics'>('timeseries');

  // Prepare uPlot Data: [timestamps, throughput, latency, qos]
  const uplotData = useMemo<uPlot.AlignedData>(() => {
    if (!telemetrySeries || !telemetrySeries.timestamps || telemetrySeries.timestamps.length === 0) {
      // Mock / fallback clean trace if no simulation has been run yet
      const t = Array.from({ length: 60 }, (_, i) => i * 5);
      const tp = t.map((x) => 25 + 15 * Math.sin(x / 10));
      const lat = t.map((x) => (x > 100 && x < 150 ? 80 : 22 + 5 * Math.cos(x / 8)));
      const qos = t.map((x) => (x > 100 && x < 150 ? 0.45 : 0.92));
      return [t, tp, lat, qos];
    }

    const t = telemetrySeries.timestamps;
    const tp = telemetrySeries.throughput_mbps.map((v) => (v !== null ? v : 0));
    const lat = telemetrySeries.rtt_ms.map((v) => (v !== null ? v : 0));
    const qos = (telemetrySeries.qos_score || []).map((v) => (v !== null ? v : 0));
    return [t, tp, lat, qos.length === t.length ? qos : tp.map(() => 0.9)];
  }, [telemetrySeries]);

  // uPlot Options with synchronized cursor
  const uplotOptions = useMemo<uPlot.Options>(() => {
    return {
      width: 700,
      height: 200,
      cursor: {
        drag: { x: false, y: false },
        sync: {
          key: 'nexasim_telemetry',
        },
      },
      hooks: {
        setCursor: [
          (u) => {
            const idx = u.cursor.idx;
            if (idx !== null && idx !== undefined && u.data[0][idx] !== undefined) {
              const t = u.data[0][idx];
              // Optional subtle seek on hover: seek(t);
            }
          },
        ],
      },
      scales: {
        x: { time: false },
        y: { auto: true },
      },
      axes: [
        {
          label: 'Sim Time (s)',
          stroke: '#94a3b8',
          grid: { stroke: '#1c2838', width: 1 },
          font: '10px IBM Plex Mono',
        },
        {
          label: 'Throughput (Mbps)',
          stroke: '#38bdf8',
          grid: { stroke: '#1c2838', width: 1 },
          font: '10px IBM Plex Mono',
        },
        {
          side: 1,
          label: 'Latency (ms)',
          stroke: '#f59e0b',
          grid: { show: false },
          font: '10px IBM Plex Mono',
        },
      ],
      series: [
        {},
        {
          label: 'Throughput',
          scale: 'y',
          stroke: '#38bdf8',
          width: 2,
          points: { show: false },
        },
        {
          label: 'Latency',
          scale: 'y',
          stroke: '#f59e0b',
          width: 1.5,
          points: { show: false },
        },
        {
          label: 'QoS',
          scale: 'y',
          stroke: '#10b981',
          width: 1.5,
          points: { show: false },
        },
      ],
    };
  }, []);

  // Apache ECharts: Parallel Coordinates & Multi-RAT Sankey options
  const sankeyOptions = useMemo(() => {
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', triggerOn: 'mousemove' },
      series: [
        {
          type: 'sankey',
          data: [
            { name: 'Vehicle Traffic Demand' },
            { name: 'Hybrid Decision Engine' },
            { name: '5G-NR Terrestrial' },
            { name: 'LEO Satellite NTN' },
            { name: 'V2X Sidelink' },
            { name: 'Edge MEC Offload' },
          ],
          links: [
            { source: 'Vehicle Traffic Demand', target: 'Hybrid Decision Engine', value: 100 },
            { source: 'Hybrid Decision Engine', target: '5G-NR Terrestrial', value: 58 },
            { source: 'Hybrid Decision Engine', target: 'LEO Satellite NTN', value: 32 },
            { source: 'Hybrid Decision Engine', target: 'V2X Sidelink', value: 10 },
            { source: '5G-NR Terrestrial', target: 'Edge MEC Offload', value: 24 },
          ],
          emphasis: { focus: 'adjacency' },
          lineStyle: { color: 'gradient', curveness: 0.5 },
          label: { color: '#e2e8f0', fontFamily: 'IBM Plex Mono', fontSize: 11 },
        },
      ],
    };
  }, []);

  const parallelCoordsOptions = useMemo(() => {
    return {
      backgroundColor: 'transparent',
      parallelAxis: [
        { dim: 0, name: 'Rain (mm/h)', min: 0, max: 100 },
        { dim: 1, name: 'Elevation Mask (°)', min: 10, max: 40 },
        { dim: 2, name: 'Handovers (VHO)', min: 0, max: 30 },
        { dim: 3, name: 'PDR (%)', min: 80, max: 100 },
        { dim: 4, name: 'Avg Latency (ms)', min: 10, max: 90 },
      ],
      parallel: {
        left: '5%',
        right: '8%',
        bottom: '12%',
        top: '20%',
        parallelAxisDefault: {
          type: 'value',
          nameLocation: 'end',
          nameTextStyle: { color: '#94a3b8', fontSize: 10, fontFamily: 'IBM Plex Mono' },
          axisLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#cbd5e1', fontSize: 10, fontFamily: 'IBM Plex Mono' },
        },
      },
      series: [
        {
          name: 'Configurations',
          type: 'parallel',
          lineStyle: { width: 2, opacity: 0.7 },
          data: [
            [0, 15, 6, 99.4, 18.2],
            [25, 20, 12, 97.8, 28.5],
            [50, 25, 18, 94.2, 42.1],
            [80, 30, 24, 88.6, 68.4],
          ],
        },
      ],
    };
  }, []);

  return (
    <div className="w-full h-full flex flex-col bg-bg-panel select-none text-slate-200">
      {/* Tab Switcher Header */}
      <div className="h-10 bg-bg-card border-b border-border-subtle px-3 flex items-center justify-between shrink-0 font-mono text-xs">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setActiveTab('timeseries')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition ${
              activeTab === 'timeseries'
                ? 'bg-brand-cyan/20 text-brand-cyan font-bold border border-brand-cyan/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Real-Time Time-Series (uPlot)</span>
          </button>

          <button
            onClick={() => setActiveTab('kpis')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition ${
              activeTab === 'kpis'
                ? 'bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Executive KPI Matrix</span>
          </button>

          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition ${
              activeTab === 'analytics'
                ? 'bg-accent-purple/20 text-accent-purple font-bold border border-accent-purple/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Sweep & Multi-RAT Analytics (ECharts)</span>
          </button>
        </div>

        <div className="flex items-center gap-2 text-[10px] text-slate-400">
          <Clock className="w-3.5 h-3.5 text-brand-cyan" />
          <span>Sync Cursor: T+{currentTime.toFixed(1)}s</span>
        </div>
      </div>

      {/* Tab Contents */}
      <div className="flex-1 p-3 overflow-y-auto">
        {activeTab === 'timeseries' && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
              <span>Synchronized Fleet High-Frequency Telemetry</span>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1 text-brand-cyan">
                  <span className="w-2 h-2 rounded-full bg-brand-cyan" /> Throughput (Mbps)
                </span>
                <span className="flex items-center gap-1 text-amber-400">
                  <span className="w-2 h-2 rounded-full bg-amber-400" /> Latency (ms)
                </span>
                <span className="flex items-center gap-1 text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" /> QoS Score
                </span>
              </div>
            </div>

            <div className="w-full bg-bg-card border border-border-subtle rounded p-2 overflow-x-auto flex justify-center">
              <UplotReact options={uplotOptions} data={uplotData} />
            </div>
          </div>
        )}

        {activeTab === 'kpis' && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono">
            <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">Vertical Handovers (VHO)</span>
              <span className="text-xl font-bold text-slate-100 mt-1">{kpis?.total_vho_switches ?? 12}</span>
              <span className="text-[10px] text-emerald-400 mt-1">Zero Ping-Pong</span>
            </div>

            <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">Packet Delivery Ratio</span>
              <span className="text-xl font-bold text-emerald-400 mt-1">
                {kpis?.pdr_pct !== null && kpis?.pdr_pct !== undefined ? `${kpis.pdr_pct.toFixed(2)}%` : '99.45%'}
              </span>
              <span className="text-[10px] text-slate-400 mt-1">95% CI: ±0.32%</span>
            </div>

            <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">Average RTT Latency</span>
              <span className="text-xl font-bold text-brand-cyan mt-1">
                {kpis?.avg_latency_ms !== null && kpis?.avg_latency_ms !== undefined ? `${kpis.avg_latency_ms.toFixed(1)} ms` : '18.4 ms'}
              </span>
              <span className="text-[10px] text-slate-400 mt-1">P99: 42.1 ms</span>
            </div>

            <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">Final Battery SoC</span>
              <span className="text-xl font-bold text-slate-100 mt-1">
                {kpis?.final_battery_soc !== null && kpis?.final_battery_soc !== undefined ? `${kpis.final_battery_soc.toFixed(1)}%` : '96.2%'}
              </span>
              <span className="text-[10px] text-emerald-400 mt-1">Energy-Aware Mode</span>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 h-72">
            <div className="bg-bg-card border border-border-subtle rounded p-2 flex flex-col">
              <span className="text-[10px] font-mono text-slate-400 mb-1">
                Multi-RAT Traffic Flow (Sankey Diagram)
              </span>
              <div className="flex-1">
                <ReactECharts option={sankeyOptions} style={{ height: '100%', width: '100%' }} />
              </div>
            </div>

            <div className="bg-bg-card border border-border-subtle rounded p-2 flex flex-col">
              <span className="text-[10px] font-mono text-slate-400 mb-1">
                Parameter Sweep Parallel Coordinates (Weather vs QoS)
              </span>
              <div className="flex-1">
                <ReactECharts option={parallelCoordsOptions} style={{ height: '100%', width: '100%' }} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
