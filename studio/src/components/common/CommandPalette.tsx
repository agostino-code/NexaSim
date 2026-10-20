import React, { useEffect, useState } from 'react';
import { Command } from 'cmdk';
import {
  Search,
  Layers,
  Radio,
  Satellite,
  Car,
  Compass,
  Play,
  Pause,
  Sliders,
  FileCode,
  Sparkles,
  ShieldAlert,
  Building,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

export const CommandPalette: React.FC = () => {
  const isOpen = useStudioStore((s) => s.isCommandPaletteOpen);
  const setOpen = useStudioStore((s) => s.setCommandPaletteOpen);
  const activeMode = useStudioStore((s) => s.activeMode);
  const setActiveMode = useStudioStore((s) => s.setActiveMode);
  const scenarios = useStudioStore((s) => s.scenarios);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const selectScenario = useStudioStore((s) => s.selectScenario);
  const vehicles = useStudioStore((s) => s.vehicles);
  const isPlaying = useStudioStore((s) => s.isPlaying);
  const togglePlay = useStudioStore((s) => s.togglePlay);
  const requestFlyTo = useStudioStore((s) => s.requestFlyTo);
  const selectNode = useStudioStore((s) => s.selectNode);
  const layers = useStudioStore((s) => s.layersVisibility);
  const toggleLayer = useStudioStore((s) => s.toggleLayerVisibility);

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(!isOpen);
      }
      if (e.key === 'Escape' && isOpen) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, setOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-xl bg-bg-panel border border-border-highlight/40 rounded-lg shadow-2xl overflow-hidden text-slate-200 font-sans"
        onClick={(e) => e.stopPropagation()}
      >
        <Command label="NexaSim Mission Control Palette" className="w-full">
          <div className="flex items-center px-3 border-b border-border-subtle bg-bg-card/50">
            <Search className="w-4 h-4 text-brand-cyan shrink-0 mr-2" />
            <Command.Input
              autoFocus
              placeholder="Type a command, search node (veh.0, gnb_1), or switch mode..."
              className="w-full bg-transparent py-3 text-sm text-slate-100 placeholder-slate-500 outline-none font-mono"
            />
            <span className="text-[10px] text-slate-500 font-mono px-1.5 py-0.5 border border-border-subtle rounded">
              ESC
            </span>
          </div>

          <Command.List className="max-h-80 overflow-y-auto p-2 text-xs divide-y divide-border-subtle/50">
            <Command.Empty className="py-6 text-center text-slate-500 text-xs">
              No matching commands or entities found.
            </Command.Empty>

            {/* Workspace Modes */}
            <Command.Group heading="Workspace Modes" className="py-1 text-[11px] font-semibold text-slate-400">
              <Command.Item
                onSelect={() => {
                  setActiveMode('design');
                  setOpen(false);
                }}
                className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-brand-cyan/20 hover:text-brand-cyan text-slate-300 transition"
              >
                <Sliders className="w-3.5 h-3.5 text-brand-cyan" />
                <span>Switch to <strong>DESIGN</strong> Mode (Visual Builder & Network Stack)</span>
              </Command.Item>
              <Command.Item
                onSelect={() => {
                  setActiveMode('live');
                  setOpen(false);
                }}
                className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-emerald-500/20 hover:text-emerald-400 text-slate-300 transition"
              >
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                <span>Switch to <strong>LIVE</strong> Mode (Real-Time Telemetry & Digital Twin)</span>
              </Command.Item>
              <Command.Item
                onSelect={() => {
                  setActiveMode('analyze');
                  setOpen(false);
                }}
                className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-accent-purple/20 hover:text-accent-purple text-slate-300 transition"
              >
                <FileCode className="w-3.5 h-3.5 text-accent-purple" />
                <span>Switch to <strong>ANALYZE</strong> Mode (Monte Carlo & Sweep Compare)</span>
              </Command.Item>
            </Command.Group>

            {/* Simulation Controls */}
            <Command.Group heading="Simulation Controls" className="py-1 text-[11px] font-semibold text-slate-400">
              <Command.Item
                onSelect={() => {
                  togglePlay();
                  setOpen(false);
                }}
                className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-slate-300 transition"
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5 text-amber-400" /> : <Play className="w-3.5 h-3.5 text-emerald-400" />}
                <span>{isPlaying ? 'Pause Simulation Playback' : 'Resume Simulation Playback'}</span>
              </Command.Item>
            </Command.Group>

            {/* Scenarios */}
            <Command.Group heading="Scenarios" className="py-1 text-[11px] font-semibold text-slate-400">
              {scenarios.map((sc) => (
                <Command.Item
                  key={sc.id}
                  onSelect={() => {
                    selectScenario(sc);
                    setOpen(false);
                  }}
                  className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 transition ${
                    currentScenario?.id === sc.id ? 'text-brand-cyan font-bold' : 'text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Compass className="w-3.5 h-3.5 text-slate-400" />
                    <span>{sc.name}</span>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500">{sc.id}</span>
                </Command.Item>
              ))}
            </Command.Group>

            {/* Scenario Nodes */}
            {currentScenario && (
              <Command.Group heading="Entities & Nodes" className="py-1 text-[11px] font-semibold text-slate-400">
                {currentScenario.gnbs?.map((g, idx) => (
                  <Command.Item
                    key={`gnb-${idx}`}
                    onSelect={() => {
                      selectNode({ type: 'gnb', index: idx, data: g });
                      requestFlyTo('gnb', idx, g.lat, g.lon);
                      setOpen(false);
                    }}
                    className="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-slate-300 transition"
                  >
                    <div className="flex items-center gap-2">
                      <Radio className="w-3.5 h-3.5 text-emerald-400" />
                      <span>5G gNodeB: {g.name}</span>
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">[{g.lat.toFixed(4)}, {g.lon.toFixed(4)}]</span>
                  </Command.Item>
                ))}

                {currentScenario.ground_stations?.map((gs, idx) => (
                  <Command.Item
                    key={`gs-${idx}`}
                    onSelect={() => {
                      selectNode({ type: 'gs', index: idx, data: gs });
                      requestFlyTo('gs', idx, gs.lat, gs.lon);
                      setOpen(false);
                    }}
                    className="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-slate-300 transition"
                  >
                    <div className="flex items-center gap-2">
                      <Satellite className="w-3.5 h-3.5 text-orange-400" />
                      <span>NTN Gateway: {gs.name}</span>
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">[{gs.lat.toFixed(4)}, {gs.lon.toFixed(4)}]</span>
                  </Command.Item>
                ))}

                {vehicles.slice(0, 8).map((v) => (
                  <Command.Item
                    key={`veh-${v.id}`}
                    onSelect={() => {
                      selectNode({ type: 'veh', index: v.id, data: v });
                      if (v.lat !== null && v.lon !== null) {
                        requestFlyTo('veh', v.id, v.lat, v.lon);
                      }
                      setOpen(false);
                    }}
                    className="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-slate-300 transition"
                  >
                    <div className="flex items-center gap-2">
                      <Car className="w-3.5 h-3.5 text-brand-cyan" />
                      <span>Vehicle: {v.name}</span>
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">
                      {v.speed_kmh !== null ? `${v.speed_kmh.toFixed(0)} km/h` : 'Stopped'}
                    </span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {/* Map Layers Toggle */}
            <Command.Group heading="Layer Toggles" className="py-1 text-[11px] font-semibold text-slate-400">
              <Command.Item
                onSelect={() => toggleLayer('leoSatellites')}
                className="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-slate-300 transition"
              >
                <div className="flex items-center gap-2">
                  <Satellite className="w-3.5 h-3.5 text-brand-cyan" />
                  <span>Toggle LEO Satellites</span>
                </div>
                <span className={`font-mono text-[10px] ${layers.leoSatellites ? 'text-emerald-400' : 'text-slate-500'}`}>
                  {layers.leoSatellites ? 'VISIBLE' : 'HIDDEN'}
                </span>
              </Command.Item>

              <Command.Item
                onSelect={() => toggleLayer('buildings3D')}
                className="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-slate-300 transition"
              >
                <div className="flex items-center gap-2">
                  <Building className="w-3.5 h-3.5 text-purple-400" />
                  <span>Toggle 3D Buildings</span>
                </div>
                <span className={`font-mono text-[10px] ${layers.buildings3D ? 'text-emerald-400' : 'text-slate-500'}`}>
                  {layers.buildings3D ? 'VISIBLE' : 'HIDDEN'}
                </span>
              </Command.Item>

              <Command.Item
                onSelect={() => toggleLayer('islLinks')}
                className="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-slate-300 transition"
              >
                <div className="flex items-center gap-2">
                  <Layers className="w-3.5 h-3.5 text-amber-400" />
                  <span>Toggle Inter-Satellite Links (ISL)</span>
                </div>
                <span className={`font-mono text-[10px] ${layers.islLinks ? 'text-emerald-400' : 'text-slate-500'}`}>
                  {layers.islLinks ? 'VISIBLE' : 'HIDDEN'}
                </span>
              </Command.Item>
            </Command.Group>
          </Command.List>

          <div className="flex items-center justify-between px-3 py-2 bg-bg-card border-t border-border-subtle text-[10px] text-slate-500 font-mono">
            <span>Navigation: ↑ ↓ Enter</span>
            <span>NexaSphere Aerospace Studio v4.0</span>
          </div>
        </Command>
      </div>
    </div>
  );
};
