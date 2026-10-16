import React, { useState } from 'react';
import {
  Play,
  Pause,
  StepForward,
  RefreshCw,
  Rocket,
  LayoutGrid,
  Map,
  Globe,
  BarChart3,
  Loader2,
  Database,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { runSimulation, build3dTwin } from '../../services/api';

interface HeaderProps {
  onLayoutPreset?: (preset: 'dual' | '2d' | '3d' | 'analytics') => void;
}

/**
 * Isolated scrubber & timer component subscribing directly to simTime,
 * preventing Header from re-rendering on 60 FPS clock ticks.
 */
export const PlaybackScrubber: React.FC = () => {
  const simTime = useStudioStore((s) => s.simTime);
  const duration = useStudioStore((s) => s.currentScenario?.duration_s ?? 0);
  const setSimTime = useStudioStore((s) => s.setSimTime);

  const minutes = Math.floor(simTime / 60);
  const seconds = (simTime % 60).toFixed(1);

  return (
    <div className="flex items-center gap-1.5">
      <input
        type="range"
        min={0}
        max={duration}
        step={0.1}
        value={Math.min(simTime, duration)}
        onChange={(e) => setSimTime(Number(e.target.value))}
        disabled={duration <= 0}
        className="nx-range w-28 hidden sm:block"
        title="Scrub simulation time"
        aria-label="Simulation time scrubber"
      />
      <div
        className="font-mono text-xs font-semibold text-brand-cyan px-2 border-x border-border-subtle tabular-nums min-w-[76px] text-center"
        title="Simulated time (simTime)"
      >
        T+{String(minutes).padStart(2, '0')}:{String(seconds).padStart(4, '0')}s
      </div>
    </div>
  );
};

export const Header: React.FC<HeaderProps> = ({ onLayoutPreset }) => {
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const scenarios = useStudioStore((s) => s.scenarios);
  const selectScenario = useStudioStore((s) => s.selectScenario);
  const isPlaying = useStudioStore((s) => s.isPlaying);
  const playbackSpeed = useStudioStore((s) => s.playbackSpeed);
  const togglePlay = useStudioStore((s) => s.togglePlay);
  const setSimTime = useStudioStore((s) => s.setSimTime);
  const setPlaybackSpeed = useStudioStore((s) => s.setPlaybackSpeed);
  const setStatus = useStudioStore((s) => s.setStatus);
  const appendLog = useStudioStore((s) => s.appendLog);
  const setProvenanceOpen = useStudioStore((s) => s.setProvenanceOpen);

  const [isRunning, setIsRunning] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [activePreset, setActivePreset] = useState<'dual' | '2d' | '3d' | 'analytics'>('dual');

  const handleRun = async () => {
    if (!currentScenario || isRunning) return;
    setIsRunning(true);
    appendLog(`[*] Dispatching simulation job for '${currentScenario.id}'...`);
    try {
      const res = await runSimulation(currentScenario.id);
      setStatus({
        running: true,
        run_id: res.run_id,
        scenario: currentScenario.id,
        started_at: new Date().toISOString(),
        logs: [],
        exit_code: null,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`[!] Dispatch error: ${msg}`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSync3D = async () => {
    if (!currentScenario || isSyncing) return;
    setIsSyncing(true);
    appendLog(`[*] Regenerating 3D Orbital Digital Twin for '${currentScenario.id}'...`);
    try {
      await build3dTwin(currentScenario.id);
      appendLog(`[+] 3D Digital Twin synchronized successfully.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`[!] 3D Twin sync error: ${msg}`);
    } finally {
      setIsSyncing(false);
    }
  };

  const handlePreset = (preset: 'dual' | '2d' | '3d' | 'analytics') => {
    setActivePreset(preset);
    onLayoutPreset?.(preset);
  };

  return (
    <header className="h-14 bg-bg-panel border-b border-border-subtle flex items-center justify-between px-4 z-50 gap-4 flex-shrink-0">
      {/* Brand Box */}
      <div className="flex items-center gap-3">
        <span className="bg-amber-500/10 text-accent-amber border border-amber-500/40 text-[10px] font-mono font-bold px-2 py-0.5 rounded tracking-wider">
          NEXASPHERE
        </span>
        <div>
          <span className="font-bold text-sm text-slate-100 tracking-tight">NexaSim Studio</span>
          <span className="text-xs text-slate-400 font-medium ml-2 hidden sm:inline">
            Enterprise Control Center
          </span>
        </div>
      </div>

      {/* Scenario Switcher */}
      <div className="hidden lg:flex items-center gap-2 min-w-0">
        <select
          value={currentScenario?.id ?? ''}
          onChange={(e) => {
            const sc = scenarios.find((s) => s.id === e.target.value);
            if (sc) selectScenario(sc);
          }}
          className="bg-bg-card border border-border-subtle text-slate-200 text-xs font-semibold rounded px-2 py-1.5 outline-none focus:border-brand-cyan cursor-pointer max-w-[220px] truncate"
          title="Active scenario"
        >
          {!currentScenario && (
            <option value="" className="bg-bg-panel text-slate-100">
              Select scenario…
            </option>
          )}
          {scenarios.map((s) => (
            <option key={s.id} value={s.id} className="bg-bg-panel text-slate-100">
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {/* Workspace Layout Presets */}
      <div className="hidden md:flex items-center bg-bg-card border border-border-subtle rounded p-0.5 gap-0.5">
        <button
          onClick={() => handlePreset('dual')}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded transition ${
            activePreset === 'dual'
              ? 'bg-brand-blue text-white shadow'
              : 'text-slate-400 hover:text-slate-100'
          }`}
          title="Dual 2D Map & 3D Globe Split View"
        >
          <LayoutGrid size={12} /> Dual
        </button>
        <button
          onClick={() => handlePreset('2d')}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded transition ${
            activePreset === '2d'
              ? 'bg-brand-blue text-white shadow'
              : 'text-slate-400 hover:text-slate-100'
          }`}
          title="Tactical 2D Map View"
        >
          <Map size={12} /> 2D Map
        </button>
        <button
          onClick={() => handlePreset('3d')}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded transition ${
            activePreset === '3d'
              ? 'bg-brand-blue text-white shadow'
              : 'text-slate-400 hover:text-slate-100'
          }`}
          title="3D Digital Twin View"
        >
          <Globe size={12} /> 3D Twin
        </button>
        <button
          onClick={() => handlePreset('analytics')}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded transition ${
            activePreset === 'analytics'
              ? 'bg-brand-blue text-white shadow'
              : 'text-slate-400 hover:text-slate-100'
          }`}
          title="Executive KPI Analytics View"
        >
          <BarChart3 size={12} /> Analytics
        </button>
      </div>

      {/* Simulation Playback Bar */}
      <div className="flex items-center bg-bg-card border border-border-subtle rounded px-2 py-0.5 gap-1.5">
        <button
          onClick={togglePlay}
          className="w-7 h-7 flex items-center justify-center text-slate-300 hover:text-brand-cyan hover:bg-sky-500/10 rounded transition"
          title={isPlaying ? 'Pause simulation' : 'Resume simulation'}
        >
          {isPlaying ? <Pause size={13} /> : <Play size={13} />}
        </button>
        <button
          onClick={() => setSimTime(useStudioStore.getState().simTime + 2.0)}
          className="w-7 h-7 flex items-center justify-center text-slate-300 hover:text-brand-cyan hover:bg-sky-500/10 rounded transition"
          title="Step forward +2.0 s"
        >
          <StepForward size={13} />
        </button>
        <PlaybackScrubber />
        <select
          value={playbackSpeed}
          onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
          className="bg-transparent text-slate-300 font-mono text-[11px] font-semibold outline-none cursor-pointer px-1 py-0.5"
          title="Simulation Speed Multiplier"
        >
          <option value="1" className="bg-bg-panel text-slate-100">1x</option>
          <option value="2" className="bg-bg-panel text-slate-100">2x</option>
          <option value="5" className="bg-bg-panel text-slate-100">5x</option>
          <option value="10" className="bg-bg-panel text-slate-100">10x</option>
        </select>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setProvenanceOpen(true)}
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 bg-bg-card border border-border-medium hover:border-brand-cyan hover:text-brand-cyan text-slate-200 text-xs font-semibold rounded transition"
          title="Data & Sources — what is recorded, derived, and never synthesized"
        >
          <Database size={13} />
          <span>Sources</span>
        </button>
        <button
          onClick={handleSync3D}
          disabled={!currentScenario || isSyncing}
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 bg-bg-card border border-border-medium hover:border-brand-cyan hover:text-brand-cyan text-slate-200 text-xs font-semibold rounded transition disabled:opacity-50"
          title="Regenerate 3D CZML orbital digital twin"
        >
          <RefreshCw size={13} className={isSyncing ? 'animate-spin' : ''} />
          <span>Sync 3D</span>
        </button>
        <button
          onClick={handleRun}
          disabled={!currentScenario || isRunning}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-accent-amber hover:bg-amber-400 text-slate-950 font-bold text-xs rounded shadow-lg shadow-amber-500/20 transition disabled:opacity-50"
          title="Run scenario co-simulation in Docker"
        >
          {isRunning ? <Loader2 size={13} className="animate-spin" /> : <Rocket size={13} />}
          <span>Run Simulation</span>
        </button>
      </div>
    </header>
  );
};
