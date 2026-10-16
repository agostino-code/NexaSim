import React, { useState } from 'react';
import { Search, Satellite, Radio, Car, Save, Loader2, Info } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { saveScenario } from '../../services/api';

export const ScenarioCatalog: React.FC = () => {
  const scenarios = useStudioStore((s) => s.scenarios);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const selectScenario = useStudioStore((s) => s.selectScenario);
  const appendLog = useStudioStore((s) => s.appendLog);
  const [filter, setFilter] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const filteredScenarios = scenarios.filter((sc) => {
    const q = filter.toLowerCase().trim();
    if (!q) return true;
    return (
      sc.name.toLowerCase().includes(q) ||
      (sc.area_name && sc.area_name.toLowerCase().includes(q)) ||
      (sc.description && sc.description.toLowerCase().includes(q))
    );
  });

  const handleSave = async () => {
    if (!currentScenario) return;
    setIsSaving(true);
    appendLog(`[*] Saving changes for scenario '${currentScenario.id}'...`);
    try {
      await saveScenario(currentScenario.id, {
        scenario: {
          name: currentScenario.name,
          time: { duration_s: currentScenario.duration_s },
          area: {
            name: currentScenario.area_name,
            center_lat: currentScenario.center[0],
            center_lon: currentScenario.center[1],
            elevation_mask_deg: currentScenario.elevation_mask_deg,
          },
          terrestrial: {
            switching_mode: currentScenario.switching_mode,
            alpine_weather: { rain_rate_mm_hr: currentScenario.rain_rate },
            gnb: { sites: currentScenario.gnbs, count: currentScenario.gnbs.length },
            blind_spots: currentScenario.blind_spots,
            ue: { count: currentScenario.vehicles },
          },
          constellation: {
            ground_stations: currentScenario.ground_stations,
          },
        },
      });
      appendLog(`[+] Scenario '${currentScenario.name}' persisted successfully to disk.`);
    } catch (err: any) {
      appendLog(`[!] Save error: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg-panel border-r border-border-subtle text-slate-200 select-none overflow-hidden">
      {/* Search Header */}
      <div className="p-3 border-b border-border-subtle flex flex-col gap-2">
        <div className="flex items-center justify-between text-[11px] font-bold text-slate-400 uppercase tracking-wider">
          <span>Scenario Catalog</span>
          <span className="bg-sky-500/10 text-brand-cyan px-1.5 py-0.5 rounded font-mono text-[10px]">
            {scenarios.length}
          </span>
        </div>
        <div className="relative flex items-center">
          <Search size={12} className="absolute left-2.5 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search mission scenarios..."
            className="w-full bg-bg-card border border-border-subtle text-slate-100 pl-8 pr-2 py-1.5 rounded text-xs outline-none focus:border-brand-cyan transition"
          />
        </div>
      </div>

      {/* Scenario List */}
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1.5">
        {filteredScenarios.map((sc) => {
          const isActive = currentScenario?.id === sc.id;
          return (
            <div
              key={sc.id}
              onClick={() => selectScenario(sc)}
              className={`p-2.5 rounded border cursor-pointer transition ${
                isActive
                  ? 'bg-sky-950/20 border-brand-cyan shadow-sm shadow-cyan-500/10'
                  : 'bg-bg-card border-border-subtle hover:border-border-medium hover:bg-bg-card-hover'
              }`}
            >
              <div className="text-xs font-bold text-slate-100 tracking-tight">{sc.name}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">{sc.area_name}</div>
              <div className="flex flex-wrap gap-1.5 mt-2">
                <span className="bg-sky-500/10 text-brand-cyan text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1">
                  <Satellite size={10} /> {sc.satellites} Sats
                </span>
                <span className="bg-emerald-500/10 text-accent-green text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1">
                  <Radio size={10} /> {sc.gnbs?.length || 0} gNBs
                </span>
                <span className="bg-pink-500/10 text-accent-pink text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1">
                  <Car size={10} /> {sc.vehicles || 4} UEs
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Parameters Panel */}
      {currentScenario && (
        <div className="border-t border-border-subtle p-3 bg-bg-panel-solid flex flex-col gap-2 max-h-56 overflow-y-auto">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Scenario Specifications
            </span>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-1 px-2 py-0.5 bg-bg-card hover:bg-emerald-500/20 text-accent-green border border-emerald-500/30 rounded text-[10px] font-bold transition disabled:opacity-50"
            >
              {isSaving ? <Loader2 size={10} className="animate-spin" /> : <Save size={10} />}
              <span>Save</span>
            </button>
          </div>
          <div className="text-[11px] text-slate-300 flex flex-col gap-1 font-mono">
            <div>
              <span className="text-slate-500">Duration:</span> {currentScenario.duration_s}s
            </div>
            <div>
              <span className="text-slate-500">Elevation Mask:</span> {currentScenario.elevation_mask_deg}°
            </div>
            <div>
              <span className="text-slate-500">VHO Strategy:</span> {currentScenario.switching_mode}
            </div>
            <div>
              <span className="text-slate-500">Ka-Band Rain:</span> {currentScenario.rain_rate} mm/h
            </div>
            {currentScenario.description && (
              <p className="text-[10px] text-slate-500 font-sans mt-1 leading-relaxed">
                {currentScenario.description}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
