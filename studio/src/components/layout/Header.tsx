import React, { useState } from 'react';
import {
  Rocket,
  Search,
  Sliders,
  Radio,
  FileCode,
  Sparkles,
  Database,
  Loader2,
  ChevronDown,
  RotateCw,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { runSimulation, build3dTwin } from '../../services/api';
import { WorkspaceMode } from '../../types/scenario';

export const Header: React.FC = () => {
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const scenarios = useStudioStore((s) => s.scenarios);
  const selectScenario = useStudioStore((s) => s.selectScenario);
  const activeMode = useStudioStore((s) => s.activeMode);
  const setActiveMode = useStudioStore((s) => s.setActiveMode);
  const setCommandPaletteOpen = useStudioStore((s) => s.setCommandPaletteOpen);
  const setProvenanceOpen = useStudioStore((s) => s.setProvenanceOpen);
  const wsConnected = useStudioStore((s) => s.wsConnected);
  const status = useStudioStore((s) => s.status);
  const setStatus = useStudioStore((s) => s.setStatus);
  const appendLog = useStudioStore((s) => s.appendLog);

  const [isRunning, setIsRunning] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

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
      appendLog(`[+] 3D Digital Twin synchronized.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`[!] 3D sync error: ${msg}`);
    } finally {
      setIsSyncing(false);
    }
  };

  const MODES: { id: WorkspaceMode; label: string; icon: React.FC<{ className?: string }>; color: string }[] = [
    { id: 'design', label: 'DESIGN', icon: Sliders, color: 'text-brand-cyan' },
    { id: 'live', label: 'LIVE', icon: Radio, color: 'text-emerald-400' },
    { id: 'analyze', label: 'ANALYZE', icon: FileCode, color: 'text-accent-purple' },
  ];

  return (
    <header className="h-12 bg-bg-panel border-b border-border-subtle px-3 flex items-center justify-between select-none z-30 shrink-0">
      {/* Brand & Scenario Selector */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 pr-3 border-r border-border-subtle">
          <div className="w-6 h-6 rounded bg-gradient-to-br from-brand-cyan to-brand-blue flex items-center justify-center font-bold text-xs text-slate-950 font-mono shadow-md">
            NX
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold tracking-wider text-slate-100 flex items-center gap-1 font-mono">
              NEXASPHERE <span className="text-[10px] text-brand-cyan font-normal font-sans">STUDIO</span>
            </span>
          </div>
        </div>

        {/* Scenario Picker */}
        <div className="relative flex items-center">
          <select
            value={currentScenario?.id || ''}
            onChange={(e) => {
              const sc = scenarios.find((s) => s.id === e.target.value);
              if (sc) selectScenario(sc);
            }}
            className="appearance-none bg-bg-card border border-border-subtle hover:border-border-medium rounded px-2.5 py-1 pr-7 text-xs text-slate-200 font-mono outline-none cursor-pointer transition focus:border-brand-cyan max-w-[200px] truncate"
          >
            {scenarios.map((sc) => (
              <option key={sc.id} value={sc.id}>
                {sc.name}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2 pointer-events-none" />
        </div>

        {/* WebSocket Connection Status */}
        <div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded border border-border-subtle bg-bg-card text-[10px] font-mono"
          title={wsConnected ? 'Telemetry Stream Active' : 'WebSocket Disconnected'}
        >
          <div className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-emerald-400' : 'bg-accent-red'}`} />
          <span className="text-slate-400 hidden md:inline">{wsConnected ? 'STREAM' : 'OFFLINE'}</span>
        </div>
      </div>

      {/* Mode Switcher Tabs (Design | Live | Analyze) */}
      <div className="flex items-center bg-bg-card/70 border border-border-subtle p-0.5 rounded-lg shadow-inner">
        {MODES.map((m) => {
          const Icon = m.icon;
          const isActive = activeMode === m.id;
          return (
            <button
              key={m.id}
              onClick={() => setActiveMode(m.id)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold transition ${
                isActive
                  ? 'bg-bg-panel text-slate-100 shadow-sm border border-border-highlight/40'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-bg-card'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? m.color : 'text-slate-500'}`} />
              <span className="tracking-wide">{m.label}</span>
            </button>
          );
        })}
      </div>

      {/* Actions & Utilities */}
      <div className="flex items-center gap-2">
        {/* Command Palette Trigger */}
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="flex items-center gap-2 px-2.5 py-1 rounded bg-bg-card border border-border-subtle hover:border-border-highlight/50 text-slate-400 hover:text-slate-200 text-xs transition"
          title="Open Command Palette (Ctrl+K)"
        >
          <Search className="w-3.5 h-3.5 text-brand-cyan" />
          <span className="hidden lg:inline text-[11px] font-mono text-slate-400">Search / Cmd</span>
          <kbd className="hidden sm:inline font-mono text-[9px] bg-bg-panel px-1 py-0.5 rounded text-slate-500 border border-border-subtle">
            Ctrl+K
          </kbd>
        </button>

        {/* 3D Twin Sync */}
        <button
          onClick={handleSync3D}
          disabled={isSyncing || !currentScenario}
          className="p-1.5 rounded bg-bg-card border border-border-subtle hover:border-border-highlight/50 text-slate-400 hover:text-brand-cyan transition disabled:opacity-50"
          title="Rebuild 3D Orbital CZML Twin"
        >
          {isSyncing ? <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-cyan" /> : <RotateCw className="w-3.5 h-3.5" />}
        </button>

        {/* Data Provenance modal trigger */}
        <button
          onClick={() => setProvenanceOpen(true)}
          className="p-1.5 rounded bg-bg-card border border-border-subtle hover:border-border-highlight/50 text-slate-400 hover:text-brand-cyan transition"
          title="Data Provenance & Scientific References"
        >
          <Database className="w-3.5 h-3.5" />
        </button>

        {/* Run Simulation Primary Action */}
        <button
          onClick={handleRun}
          disabled={isRunning || !currentScenario || status.running}
          className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-bold font-mono transition shadow-md ${
            status.running || isRunning
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
              : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 border border-emerald-400'
          } disabled:opacity-50`}
        >
          {status.running || isRunning ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>SIMULATING</span>
            </>
          ) : (
            <>
              <Rocket className="w-3.5 h-3.5 fill-current" />
              <span>RUN SIM</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
};
