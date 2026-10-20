import React, { useState } from 'react';
import {
  MousePointer,
  Square,
  Radio,
  Satellite,
  ShieldAlert,
  Navigation,
  Download,
  Loader2,
  CheckCircle,
  MapPin,
  Sparkles,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { downloadOsmBbox } from '../../services/api';
import { DrawingToolType } from '../../types/scenario';

export const MapScenarioDrawer: React.FC = () => {
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const drawingTool = useStudioStore((s) => s.drawingTool);
  const setDrawingTool = useStudioStore((s) => s.setDrawingTool);
  const addNode = useStudioStore((s) => s.addNode);
  const updateScenarioParams = useStudioStore((s) => s.updateScenarioParams);
  const appendLog = useStudioStore((s) => s.appendLog);

  const [isDownloading, setIsDownloading] = useState(false);
  const [osmDownloaded, setOsmDownloaded] = useState(false);

  // New Node Form States
  const [gnbName, setGnbName] = useState('gnb_custom_1');
  const [gnbHeight, setGnbHeight] = useState(30);
  const [gnbPower, setGnbPower] = useState(46);

  const [gwName, setGwName] = useState('gw_teleport_1');
  const [gwAlt, setGwAlt] = useState(150);

  const [blindName, setBlindName] = useState('tunnel_blind_spot');
  const [blindAtten, setBlindAtten] = useState(35);

  const handleImportOsm = async () => {
    if (!currentScenario) return;
    setIsDownloading(true);
    appendLog(`[*] Downloading OpenStreetMap bounding box for '${currentScenario.id}'...`);
    try {
      const res = await downloadOsmBbox(currentScenario.bbox, currentScenario.id);
      setOsmDownloaded(true);
      appendLog(`[+] OSM network acquired: ${res.osm_file || 'Cached OK'}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`[!] OSM download error: ${msg}`);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleAddDefaultGnb = () => {
    if (!currentScenario) return;
    const center = currentScenario.center || [46.5, 10.5];
    const newGnb = {
      name: gnbName,
      lat: parseFloat((center[0] + (Math.random() - 0.5) * 0.02).toFixed(5)),
      lon: parseFloat((center[1] + (Math.random() - 0.5) * 0.02).toFixed(5)),
      height_m: gnbHeight,
      tx_power_dbm: gnbPower,
      frequency_ghz: 3.5,
      bandwidth_mhz: 100,
      coverage_radius_m: 600,
    };
    addNode('gnb', newGnb);
    appendLog(`[+] Added 5G gNodeB '${gnbName}' at [${newGnb.lat}, ${newGnb.lon}]`);
    setGnbName(`gnb_custom_${Date.now().toString().slice(-4)}`);
  };

  const handleAddDefaultGateway = () => {
    if (!currentScenario) return;
    const center = currentScenario.center || [46.5, 10.5];
    const newGw = {
      name: gwName,
      lat: parseFloat((center[0] + (Math.random() - 0.5) * 0.03).toFixed(5)),
      lon: parseFloat((center[1] + (Math.random() - 0.5) * 0.03).toFixed(5)),
      altitude_m: gwAlt,
      feeder_link: { frequency_ghz: 28.0, bandwidth_mhz: 1000 },
    };
    addNode('gs', newGw);
    appendLog(`[+] Added NTN Gateway '${gwName}' at [${newGw.lat}, ${newGw.lon}]`);
    setGwName(`gw_teleport_${Date.now().toString().slice(-4)}`);
  };

  const handleAddDefaultBlindSpot = () => {
    if (!currentScenario) return;
    const center = currentScenario.center || [46.5, 10.5];
    const newBs = {
      name: blindName,
      lat_min: parseFloat((center[0] - 0.005).toFixed(5)),
      lat_max: parseFloat((center[0] + 0.005).toFixed(5)),
      lon_min: parseFloat((center[1] - 0.005).toFixed(5)),
      lon_max: parseFloat((center[1] + 0.005).toFixed(5)),
      attenuation_db: blindAtten,
    };
    addNode('blind', newBs);
    appendLog(`[+] Added Blind Spot zone '${blindName}' with ${blindAtten} dB attenuation`);
    setBlindName(`blind_spot_${Date.now().toString().slice(-4)}`);
  };

  const TOOLS: { id: DrawingToolType; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: 'select', label: 'Select & Move', icon: MousePointer },
    { id: 'bbox_osm', label: 'OSM Bounding Box', icon: Square },
    { id: 'place_gnb', label: 'Place 5G gNodeB', icon: Radio },
    { id: 'place_ground_station', label: 'Place NTN Gateway', icon: Satellite },
    { id: 'place_blind_spot', label: 'Place Blind Spot', icon: ShieldAlert },
    { id: 'uav_corridor', label: 'UAV Corridor', icon: Navigation },
  ];

  return (
    <div className="h-full bg-bg-panel border-r border-border-subtle flex flex-col overflow-y-auto p-3 text-xs text-slate-200 select-none">
      <div className="flex items-center gap-2 pb-2 mb-3 border-b border-border-subtle">
        <MapPin className="w-4 h-4 text-brand-cyan" />
        <h3 className="font-bold text-xs uppercase tracking-wider text-slate-100 font-mono">
          Visual Tactical Map Drawer
        </h3>
      </div>

      {/* Tool Selector Buttons */}
      <div className="grid grid-cols-2 gap-1.5 mb-4">
        {TOOLS.map((t) => {
          const Icon = t.icon;
          const isActive = drawingTool === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setDrawingTool(t.id)}
              className={`flex items-center gap-1.5 px-2.5 py-2 rounded text-left font-mono text-[11px] transition ${
                isActive
                  ? 'bg-brand-cyan/20 text-brand-cyan border border-brand-cyan/40 font-bold'
                  : 'bg-bg-card border border-border-subtle text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Contextual Panels depending on active tool */}
      <div className="flex-1 flex flex-col gap-3 font-mono">
        {drawingTool === 'bbox_osm' && (
          <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col gap-2.5">
            <span className="font-bold text-slate-100 text-[11px] flex items-center gap-1.5">
              <Square className="w-3.5 h-3.5 text-brand-cyan" />
              OSM Area Bounding Box
            </span>
            <div className="text-[10px] text-slate-400">
              Current Bbox: [
              {currentScenario?.bbox.map((v) => v.toFixed(3)).join(', ')}]
            </div>
            <button
              onClick={handleImportOsm}
              disabled={isDownloading}
              className="mt-1 flex items-center justify-center gap-1.5 bg-brand-cyan/20 hover:bg-brand-cyan/30 text-brand-cyan border border-brand-cyan/40 py-2 rounded font-bold text-xs transition disabled:opacity-50"
            >
              {isDownloading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>FETCHING OVERPASS API...</span>
                </>
              ) : osmDownloaded ? (
                <>
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                  <span>RE-IMPORT OSM NETWORK</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>IMPORT OSM & BUILD SUMO</span>
                </>
              )}
            </button>
          </div>
        )}

        {drawingTool === 'place_gnb' && (
          <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col gap-2">
            <span className="font-bold text-emerald-400 text-[11px] flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5" />
              Add 5G gNodeB Transmitter
            </span>
            <div className="flex flex-col gap-1 text-[11px]">
              <label className="text-slate-400">Name:</label>
              <input
                type="text"
                value={gnbName}
                onChange={(e) => setGnbName(e.target.value)}
                className="bg-bg-panel border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <label className="text-slate-400">Height (m):</label>
                <input
                  type="number"
                  value={gnbHeight}
                  onChange={(e) => setGnbHeight(Number(e.target.value))}
                  className="w-full bg-bg-panel border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none"
                />
              </div>
              <div>
                <label className="text-slate-400">Tx Power (dBm):</label>
                <input
                  type="number"
                  value={gnbPower}
                  onChange={(e) => setGnbPower(Number(e.target.value))}
                  className="w-full bg-bg-panel border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none"
                />
              </div>
            </div>
            <button
              onClick={handleAddDefaultGnb}
              className="mt-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 py-1.5 rounded font-bold text-xs transition"
            >
              + PLACE GNODEB ON MAP
            </button>
          </div>
        )}

        {drawingTool === 'place_ground_station' && (
          <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col gap-2">
            <span className="font-bold text-orange-400 text-[11px] flex items-center gap-1.5">
              <Satellite className="w-3.5 h-3.5" />
              Add NTN Ground Gateway
            </span>
            <div className="flex flex-col gap-1 text-[11px]">
              <label className="text-slate-400">Gateway Name:</label>
              <input
                type="text"
                value={gwName}
                onChange={(e) => setGwName(e.target.value)}
                className="bg-bg-panel border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none"
              />
            </div>
            <div className="flex flex-col gap-1 text-[11px]">
              <label className="text-slate-400">Altitude (m ASL):</label>
              <input
                type="number"
                value={gwAlt}
                onChange={(e) => setGwAlt(Number(e.target.value))}
                className="bg-bg-panel border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none"
              />
            </div>
            <button
              onClick={handleAddDefaultGateway}
              className="mt-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-300 border border-orange-500/40 py-1.5 rounded font-bold text-xs transition"
            >
              + PLACE GATEWAY ON MAP
            </button>
          </div>
        )}

        {drawingTool === 'place_blind_spot' && (
          <div className="bg-bg-card border border-border-subtle rounded p-3 flex flex-col gap-2">
            <span className="font-bold text-accent-red text-[11px] flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" />
              Add Radio Blind Spot Zone
            </span>
            <div className="flex flex-col gap-1 text-[11px]">
              <label className="text-slate-400">Zone Label:</label>
              <input
                type="text"
                value={blindName}
                onChange={(e) => setBlindName(e.target.value)}
                className="bg-bg-panel border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none"
              />
            </div>
            <div className="flex flex-col gap-1 text-[11px]">
              <label className="text-slate-400">Attenuation (dB):</label>
              <input
                type="number"
                value={blindAtten}
                onChange={(e) => setBlindAtten(Number(e.target.value))}
                className="bg-bg-panel border border-border-subtle rounded px-2 py-1 text-slate-100 outline-none"
              />
            </div>
            <button
              onClick={handleAddDefaultBlindSpot}
              className="mt-2 bg-accent-red/20 hover:bg-accent-red/30 text-red-300 border border-red-500/40 py-1.5 rounded font-bold text-xs transition"
            >
              + ADD BLIND ZONE ON MAP
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
