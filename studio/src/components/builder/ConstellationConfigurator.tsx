import React, { useState } from 'react';
import {
  Satellite,
  Compass,
  Radio,
  Sliders,
  Layers,
  Zap,
  Globe,
  Info,
  CheckCircle2,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

export const ConstellationConfigurator: React.FC = () => {
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const updateScenarioParams = useStudioStore((s) => s.updateScenarioParams);
  const updateDraftSection = useStudioStore((s) => s.updateDraftSection);
  const appendLog = useStudioStore((s) => s.appendLog);

  // Shell parameters
  const [altitudeKm, setAltitudeKm] = useState<number>(550);
  const [inclinationDeg, setInclinationDeg] = useState<number>(53.0);
  const [numPlanes, setNumPlanes] = useState<number>(8);
  const [satsPerPlane, setSatsPerPlane] = useState<number>(4);
  const [elevationMaskDeg, setElevationMaskDeg] = useState<number>(
    currentScenario?.elevation_mask_deg ?? 20
  );
  const [frequencyBand, setFrequencyBand] = useState<string>('Ka (28 GHz / 1 GHz BW)');
  const [islEnabled, setIslEnabled] = useState<boolean>(true);
  const [islMaxRangeKm, setIslMaxRangeKm] = useState<number>(5000);

  const totalSats = numPlanes * satsPerPlane;
  const orbitalPeriodMin = (
    (2 * Math.PI * Math.sqrt(Math.pow((6371 + altitudeKm) * 1000, 3) / 3.986004418e14)) /
    60
  ).toFixed(1);

  const footprintRadiusKm = Math.sqrt(
    Math.pow(6371 + altitudeKm, 2) - Math.pow(6371, 2)
  ).toFixed(0);

  const handleApply = () => {
    updateScenarioParams({
      satellites: totalSats,
      elevation_mask_deg: elevationMaskDeg,
    });
    updateDraftSection('scenario.constellation', {
      type: 'starlink_shell',
      shells: [
        {
          name: 'active_leo_shell',
          altitude_km: altitudeKm,
          inclination_deg: inclinationDeg,
          num_planes: numPlanes,
          sats_per_plane: satsPerPlane,
        },
      ],
      isl: {
        enabled: islEnabled,
        type: 'laser',
        wavelength_nm: 1550,
        max_range_km: islMaxRangeKm,
        num_ports_per_sat: 4,
      },
    });
    appendLog(
      `[+] Applied Walker-Delta constellation: ${totalSats} sats, ${altitudeKm}km @ ${inclinationDeg}° inc.`
    );
  };

  return (
    <div className="h-full bg-bg-panel border-r border-border-subtle flex flex-col overflow-y-auto p-3 text-xs text-slate-200 select-none">
      {/* Header */}
      <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <Satellite className="w-4 h-4 text-brand-cyan" />
          <h3 className="font-bold text-xs uppercase tracking-wider text-slate-100 font-mono">
            LEO Constellation Configurator
          </h3>
        </div>
        <span className="font-mono text-[10px] text-brand-cyan bg-brand-cyan/10 px-2 py-0.5 rounded border border-brand-cyan/30">
          Walker-Delta 3D
        </span>
      </div>

      {/* Orbital Quick Metrics */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-bg-card border border-border-subtle rounded p-2 flex flex-col">
          <span className="text-[10px] text-slate-500 font-mono">Total Spacecraft</span>
          <span className="font-mono text-base font-bold text-slate-100">{totalSats}</span>
        </div>
        <div className="bg-bg-card border border-border-subtle rounded p-2 flex flex-col">
          <span className="text-[10px] text-slate-500 font-mono">Orbital Period</span>
          <span className="font-mono text-base font-bold text-brand-cyan">{orbitalPeriodMin}m</span>
        </div>
        <div className="bg-bg-card border border-border-subtle rounded p-2 flex flex-col">
          <span className="text-[10px] text-slate-500 font-mono">Footprint Radius</span>
          <span className="font-mono text-base font-bold text-emerald-400">{footprintRadiusKm}km</span>
        </div>
      </div>

      {/* Sliders & Parameters */}
      <div className="flex flex-col gap-3 font-mono">
        {/* Altitude */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Orbital Altitude:</span>
            <span className="text-brand-cyan font-bold">{altitudeKm} km</span>
          </div>
          <input
            type="range"
            min={300}
            max={1200}
            step={25}
            value={altitudeKm}
            onChange={(e) => setAltitudeKm(Number(e.target.value))}
            className="nx-range w-full"
          />
        </div>

        {/* Inclination */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Orbital Inclination:</span>
            <span className="text-brand-cyan font-bold">{inclinationDeg}°</span>
          </div>
          <input
            type="range"
            min={0}
            max={98}
            step={0.5}
            value={inclinationDeg}
            onChange={(e) => setInclinationDeg(Number(e.target.value))}
            className="nx-range w-full"
          />
        </div>

        {/* Orbital Planes */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Orbital Planes:</span>
            <span className="text-brand-cyan font-bold">{numPlanes} planes</span>
          </div>
          <input
            type="range"
            min={1}
            max={24}
            step={1}
            value={numPlanes}
            onChange={(e) => setNumPlanes(Number(e.target.value))}
            className="nx-range w-full"
          />
        </div>

        {/* Sats Per Plane */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Satellites Per Plane:</span>
            <span className="text-brand-cyan font-bold">{satsPerPlane} sats</span>
          </div>
          <input
            type="range"
            min={1}
            max={24}
            step={1}
            value={satsPerPlane}
            onChange={(e) => setSatsPerPlane(Number(e.target.value))}
            className="nx-range w-full"
          />
        </div>

        {/* Ground Elevation Mask */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">User Terminal Elevation Mask:</span>
            <span className="text-amber-400 font-bold">{elevationMaskDeg}°</span>
          </div>
          <input
            type="range"
            min={5}
            max={50}
            step={1}
            value={elevationMaskDeg}
            onChange={(e) => setElevationMaskDeg(Number(e.target.value))}
            className="nx-range w-full"
          />
        </div>

        {/* RF Carrier Band */}
        <div className="flex flex-col gap-1 mt-1">
          <span className="text-slate-400 text-[11px]">Feeder / Service Carrier Band:</span>
          <select
            value={frequencyBand}
            onChange={(e) => setFrequencyBand(e.target.value)}
            className="bg-bg-card border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none text-[11px]"
          >
            <option value="Ka (28 GHz / 1 GHz BW)">Ka-Band (28 GHz / 1000 MHz BW)</option>
            <option value="Ku (12 GHz / 500 MHz BW)">Ku-Band (12 GHz / 500 MHz BW)</option>
            <option value="S (2 GHz / 30 MHz BW)">S-Band (2 GHz / 30 MHz BW 3GPP Rel-17)</option>
          </select>
        </div>

        {/* ISL Mesh Topology */}
        <div className="bg-bg-card border border-border-subtle rounded p-2.5 flex flex-col gap-2 mt-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-[11px] text-slate-200 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-orange-400" />
              Inter-Satellite Links (ISL)
            </span>
            <input
              type="checkbox"
              checked={islEnabled}
              onChange={(e) => setIslEnabled(e.target.checked)}
              className="accent-brand-cyan"
            />
          </div>

          {islEnabled && (
            <div className="flex flex-col gap-1 mt-1 text-[10px]">
              <div className="flex justify-between text-slate-400">
                <span>Max Optical Range:</span>
                <span className="text-slate-200">{islMaxRangeKm} km</span>
              </div>
              <input
                type="range"
                min={2000}
                max={7000}
                step={250}
                value={islMaxRangeKm}
                onChange={(e) => setIslMaxRangeKm(Number(e.target.value))}
                className="nx-range w-full"
              />
              <span className="text-slate-500 italic mt-0.5">
                Laser 1550nm mesh topology with 4 full-duplex optical terminals per satellite.
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Commit Configuration Button */}
      <button
        onClick={handleApply}
        className="mt-auto pt-3 flex items-center justify-center gap-1.5 w-full bg-brand-cyan hover:bg-sky-400 text-slate-950 font-bold py-2 rounded text-xs transition shadow-md font-mono"
      >
        <CheckCircle2 className="w-4 h-4" />
        <span>APPLY CONSTELLATION MESH</span>
      </button>
    </div>
  );
};
