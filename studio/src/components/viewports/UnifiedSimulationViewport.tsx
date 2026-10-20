import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import DeckGL from '@deck.gl/react';
import {
  ScatterplotLayer,
  ArcLayer,
  LineLayer,
  PathLayer,
  PolygonLayer,
  TextLayer,
} from '@deck.gl/layers';
import {
  Globe,
  Map as MapIcon,
  Layers,
  Crosshair,
  Compass,
  Maximize2,
  Building,
  Mountain,
  Eye,
  EyeOff,
  Radio,
  Satellite as SatIcon,
  Car,
  ShieldAlert,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import {
  RAT_COLORS,
  GATEWAY_COLOR,
  GNB_COLOR,
  SAT_COLOR,
  BLIND_SPOT_COLOR,
  BEAM_COLOR,
} from '../../theme/palette';
import { generateSyntheticShellSats, calculateOrbitGroundTrack } from '../../services/orbitPropagator';
import { SatelliteEntity, SimulationRadioLink, VehicleTelemetry } from '../../types/scenario';

// Dark Tactical MapLibre style using Carto Dark Matter (or local vector fallback)
const MAP_STYLE_DARK: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'carto-dark': {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
      ],
      tileSize: 256,
      attribution: '© CARTO, © OpenStreetMap',
    },
  },
  layers: [
    {
      id: 'carto-dark-layer',
      type: 'raster',
      source: 'carto-dark',
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

export const UnifiedSimulationViewport: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  // Zustand State Selectors
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const viewState = useStudioStore((s) => s.viewState);
  const setViewState = useStudioStore((s) => s.setViewState);
  const projection = useStudioStore((s) => s.projection);
  const setProjection = useStudioStore((s) => s.setProjection);
  const trackedNodeId = useStudioStore((s) => s.trackedNodeId);
  const setTrackedNodeId = useStudioStore((s) => s.setTrackedNodeId);
  const layers = useStudioStore((s) => s.layersVisibility);
  const toggleLayer = useStudioStore((s) => s.toggleLayerVisibility);
  const vehicles = useStudioStore((s) => s.vehicles);
  const activeLinks = useStudioStore((s) => s.activeLinks);
  const selectedNode = useStudioStore((s) => s.selectedNode);
  const selectNode = useStudioStore((s) => s.selectNode);
  const activeMode = useStudioStore((s) => s.activeMode);
  const currentTime = useStudioStore((s) => s.currentTime);

  const [isLayersOpen, setIsLayersOpen] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Initialize MapLibre GL instance
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const initialMap = new maplibregl.Map({
      container: mapContainerRef.current,
      style: MAP_STYLE_DARK,
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
      pitch: viewState.pitch,
      bearing: viewState.bearing,
      attributionControl: false,
    });

    initialMap.on('load', () => {
      mapRef.current = initialMap;
      setMapLoaded(true);

      // Apply initial projection
      if ((initialMap as any).setProjection) {
        (initialMap as any).setProjection({ type: projection === 'globe' ? 'globe' : 'mercator' });
      }
    });

    initialMap.on('move', () => {
      const c = initialMap.getCenter();
      setViewState({
        longitude: c.lng,
        latitude: c.lat,
        zoom: initialMap.getZoom(),
        pitch: initialMap.getPitch(),
        bearing: initialMap.getBearing(),
      });
    });

    return () => {
      initialMap.remove();
      mapRef.current = null;
    };
  }, []);

  // Sync projection changes to MapLibre
  useEffect(() => {
    if (!mapRef.current || !mapLoaded) return;
    const map = mapRef.current as any;
    if (map.setProjection) {
      map.setProjection({ type: projection === 'globe' ? 'globe' : 'mercator' });
    }
  }, [projection, mapLoaded]);

  // Center camera when scenario changes
  useEffect(() => {
    if (!currentScenario || !mapRef.current || !mapLoaded) return;
    if (currentScenario.center) {
      mapRef.current.flyTo({
        center: [currentScenario.center[1], currentScenario.center[0]],
        zoom: 11,
        duration: 1500,
      });
    }
  }, [currentScenario?.id, mapLoaded]);

  // Auto-track camera on selected vehicle if trackedNodeId is set
  useEffect(() => {
    if (!trackedNodeId || !mapRef.current || !mapLoaded) return;
    const vehId = parseInt(trackedNodeId.replace('veh.', ''), 10);
    const v = vehicles.find((veh) => veh.id === vehId);
    if (v && v.lat !== null && v.lon !== null) {
      mapRef.current.easeTo({
        center: [v.lon, v.lat],
        duration: 150,
      });
    }
  }, [trackedNodeId, vehicles, mapLoaded]);

  // Generate constellation satellites and orbital tracks
  const { constellationSats, orbitTracks, islLinks } = useMemo(() => {
    const baseDate = new Date('2026-08-26T12:00:00Z');
    const simDate = new Date(baseDate.getTime() + currentTime * 1000);
    const sats = generateSyntheticShellSats('leoshell', 550, 53.0, 6, 4, simDate);

    // Calculate orbital trails
    const tracks: { path: [number, number, number][] }[] = [];
    if (layers.leoOrbits && sats.length > 0) {
      for (let i = 0; i < Math.min(sats.length, 8); i++) {
        if (sats[i].tleLine1 && sats[i].tleLine2) {
          const pts = calculateOrbitGroundTrack(sats[i].tleLine1!, sats[i].tleLine2!, simDate, 40);
          if (pts.length > 1) {
            tracks.push({ path: pts });
          }
        }
      }
    }

    // Generate ISL Mesh Links between adjacent satellites
    const isls: { source: [number, number, number]; target: [number, number, number] }[] = [];
    if (layers.islLinks && sats.length > 1) {
      for (let p = 0; p < 6; p++) {
        for (let s = 0; s < 4; s++) {
          const curIdx = p * 4 + s;
          const nextInPlane = p * 4 + ((s + 1) % 4);
          const nextPlane = ((p + 1) % 6) * 4 + s;
          if (sats[curIdx] && sats[nextInPlane]) {
            isls.push({
              source: [sats[curIdx].lon, sats[curIdx].lat, sats[curIdx].altM],
              target: [sats[nextInPlane].lon, sats[nextInPlane].lat, sats[nextInPlane].altM],
            });
          }
          if (sats[curIdx] && sats[nextPlane]) {
            isls.push({
              source: [sats[curIdx].lon, sats[curIdx].lat, sats[curIdx].altM],
              target: [sats[nextPlane].lon, sats[nextPlane].lat, sats[nextPlane].altM],
            });
          }
        }
      }
    }

    return { constellationSats: sats, orbitTracks: tracks, islLinks: isls };
  }, [currentTime, layers.leoOrbits, layers.islLinks]);

  // Dynamic Radio Serving Links (Vehicles -> 5G gNodeB or Satellite)
  const radioServingArcs = useMemo(() => {
    if (!layers.nrLinks && !layers.ntnLinks) return [];
    const arcs: any[] = [];
    const gnbs = currentScenario?.gnbs || [];

    vehicles.forEach((v) => {
      if (v.lat === null || v.lon === null) return;
      if (v.active_rat === '5G' && layers.nrLinks && gnbs.length > 0) {
        // Find closest gNodeB
        const g = gnbs[0];
        arcs.push({
          source: [v.lon, v.lat, 0],
          target: [g.lon, g.lat, g.height_m || 30],
          color: [16, 185, 129, 200], // emerald
        });
      } else if (v.active_rat === 'LEO' && layers.ntnLinks && constellationSats.length > 0) {
        // Connect to nearest satellite
        const sat = constellationSats[0];
        arcs.push({
          source: [v.lon, v.lat, 0],
          target: [sat.lon, sat.lat, sat.altM],
          color: [56, 189, 248, 220], // cyan
        });
      }
    });
    return arcs;
  }, [vehicles, currentScenario?.gnbs, constellationSats, layers.nrLinks, layers.ntnLinks]);

  // Selected Vehicle Perception FoV Cone
  const sensorConePolygons = useMemo(() => {
    if (!layers.sensorCones || !selectedNode || selectedNode.type !== 'veh') return [];
    const v = selectedNode.data as VehicleTelemetry;
    if (!v || v.lat === null || v.lon === null) return [];

    const heading = v.heading_deg ?? 0;
    const radius = 0.0015; // ~160 meters
    const fovAngle = 60; // 120 deg total
    const points: [number, number][] = [[v.lon, v.lat]];

    for (let a = -fovAngle; a <= fovAngle; a += 10) {
      const rad = ((heading + a) * Math.PI) / 180;
      points.push([v.lon + radius * Math.sin(rad), v.lat + radius * Math.cos(rad)]);
    }
    points.push([v.lon, v.lat]);

    return [{ polygon: points }];
  }, [selectedNode, layers.sensorCones]);

  // Compose Deck.gl Layers
  const deckLayers = [
    // 1. Blind Spot Polygons
    new PolygonLayer({
      id: 'blind-spots-layer',
      data: currentScenario?.blind_spots || [],
      getPolygon: (d: any) => [
        [d.lon_min, d.lat_min],
        [d.lon_max, d.lat_min],
        [d.lon_max, d.lat_max],
        [d.lon_min, d.lat_max],
        [d.lon_min, d.lat_min],
      ],
      getFillColor: [239, 68, 68, 40],
      getLineColor: [239, 68, 68, 200],
      getLineWidth: 2,
      lineWidthUnits: 'pixels',
      pickable: true,
      onClick: (info) => {
        if (info.object) {
          selectNode({ type: 'blind', index: info.index, data: info.object });
        }
      },
    }),

    // 2. Sensor FoV Cones
    new PolygonLayer({
      id: 'sensor-cones-layer',
      data: sensorConePolygons,
      getPolygon: (d: any) => d.polygon,
      getFillColor: [56, 189, 248, 60],
      getLineColor: [56, 189, 248, 220],
      getLineWidth: 1.5,
      lineWidthUnits: 'pixels',
    }),

    // 3. Orbit Ground Tracks
    new PathLayer({
      id: 'orbit-tracks-layer',
      data: orbitTracks,
      getPath: (d: any) => d.path,
      getColor: [56, 189, 248, 120],
      getWidth: 1.5,
      widthUnits: 'pixels',
    }),

    // 4. Inter-Satellite Links (ISL Mesh)
    new LineLayer({
      id: 'isl-mesh-layer',
      data: islLinks,
      getSourcePosition: (d: any) => d.source,
      getTargetPosition: (d: any) => d.target,
      getColor: [251, 146, 60, 160], // orange glow
      getWidth: 2,
      widthUnits: 'pixels',
    }),

    // 5. Active Serving Radio Links (Arcs)
    new ArcLayer({
      id: 'radio-arcs-layer',
      data: radioServingArcs,
      getSourcePosition: (d: any) => d.source,
      getTargetPosition: (d: any) => d.target,
      getSourceColor: (d: any) => d.color,
      getTargetColor: (d: any) => d.color,
      getWidth: 2,
    }),

    // 6. Ground Gateways
    layers.groundStations &&
      new ScatterplotLayer({
        id: 'ground-stations-layer',
        data: currentScenario?.ground_stations || [],
        getPosition: (d: any) => [d.lon, d.lat, 0],
        getRadius: 80,
        radiusMinPixels: 7,
        radiusMaxPixels: 14,
        getFillColor: [251, 146, 60, 255],
        getLineColor: [255, 255, 255, 255],
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
        pickable: true,
        onClick: (info) => {
          if (info.object) {
            selectNode({ type: 'gs', index: info.index, data: info.object });
          }
        },
      }),

    // 7. 5G gNodeBs with coverage circles
    layers.rsuAndGnb &&
      new ScatterplotLayer({
        id: 'gnbs-layer',
        data: currentScenario?.gnbs || [],
        getPosition: (d: any) => [d.lon, d.lat, d.height_m || 30],
        getRadius: (d: any) => d.coverage_radius_m || 500,
        radiusMinPixels: 8,
        radiusMaxPixels: 30,
        getFillColor: [16, 185, 129, 60],
        getLineColor: [16, 185, 129, 255],
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
        pickable: true,
        onClick: (info) => {
          if (info.object) {
            selectNode({ type: 'gnb', index: info.index, data: info.object });
          }
        },
      }),

    // 8. LEO Satellites
    layers.leoSatellites &&
      new ScatterplotLayer({
        id: 'satellites-layer',
        data: constellationSats,
        getPosition: (d: SatelliteEntity) => [d.lon, d.lat, d.altM],
        getRadius: 1000,
        radiusMinPixels: 6,
        radiusMaxPixels: 12,
        getFillColor: [56, 189, 248, 255],
        getLineColor: [255, 255, 255, 200],
        getLineWidth: 1.5,
        lineWidthUnits: 'pixels',
        pickable: true,
        onClick: (info) => {
          if (info.object) {
            selectNode({ type: 'sat', index: info.index, data: info.object });
          }
        },
      }),

    // 9. Vehicles Fleet
    layers.vehicles &&
      new ScatterplotLayer({
        id: 'vehicles-layer',
        data: vehicles.filter((v) => v.lat !== null && v.lon !== null),
        getPosition: (v: VehicleTelemetry) => [v.lon!, v.lat!, v.altitude_m || 0],
        getRadius: 25,
        radiusMinPixels: 6,
        radiusMaxPixels: 14,
        getFillColor: (v: VehicleTelemetry) => {
          if (v.in_blind) return [245, 158, 11, 255]; // amber
          if (v.active_rat === '5G') return [16, 185, 129, 255];
          if (v.active_rat === 'LEO') return [56, 189, 248, 255];
          if (v.active_rat === 'V2X') return [168, 85, 247, 255];
          return [100, 116, 139, 255]; // slate
        },
        getLineColor: (v: VehicleTelemetry) =>
          selectedNode?.type === 'veh' && selectedNode.data?.id === v.id
            ? [255, 255, 255, 255]
            : [0, 0, 0, 180],
        getLineWidth: (v: VehicleTelemetry) =>
          selectedNode?.type === 'veh' && selectedNode.data?.id === v.id ? 3 : 1.5,
        lineWidthUnits: 'pixels',
        pickable: true,
        onClick: (info) => {
          if (info.object) {
            selectNode({ type: 'veh', index: info.object.id, data: info.object });
          }
        },
      }),
  ].filter(Boolean);

  return (
    <div className="relative w-full h-full overflow-hidden bg-bg-base select-none">
      {/* MapLibre WebGL Canvas Container */}
      <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

      {/* Deck.GL Overlay synchronized with MapLibre */}
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }: any) => {
          setViewState(vs);
          if (mapRef.current) {
            mapRef.current.jumpTo({
              center: [vs.longitude, vs.latitude],
              zoom: vs.zoom,
              pitch: vs.pitch,
              bearing: vs.bearing,
            });
          }
        }}
        controller={true}
        layers={deckLayers}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'default')}
      />

      {/* Tactical HUD Overlay Toolbar (Top Center) */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 bg-bg-panel/90 backdrop-blur-md border border-border-subtle p-1 rounded-lg shadow-2xl z-20 text-xs">
        {/* Globe vs Mercator projection switcher */}
        <button
          onClick={() => setProjection(projection === 'globe' ? 'mercator' : 'globe')}
          className={`flex items-center gap-1 px-2.5 py-1 rounded font-bold font-mono transition ${
            projection === 'globe'
              ? 'bg-brand-cyan/20 text-brand-cyan border border-brand-cyan/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
          title="Switch 2D Mercator / 3D Globe Projection"
        >
          {projection === 'globe' ? <Globe className="w-3.5 h-3.5" /> : <MapIcon className="w-3.5 h-3.5" />}
          <span>{projection.toUpperCase()}</span>
        </button>

        <div className="w-px h-4 bg-border-subtle" />

        {/* Camera Tracking Toggle */}
        <button
          onClick={() => {
            if (trackedNodeId) {
              setTrackedNodeId(null);
            } else if (selectedNode) {
              setTrackedNodeId(`${selectedNode.type}.${selectedNode.data?.id || selectedNode.index}`);
            }
          }}
          disabled={!selectedNode && !trackedNodeId}
          className={`flex items-center gap-1 px-2 py-1 rounded font-mono text-[11px] transition ${
            trackedNodeId
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold'
              : 'text-slate-400 hover:text-slate-200 disabled:opacity-40'
          }`}
          title={trackedNodeId ? 'Release Target Lock' : 'Lock Camera on Selected Entity'}
        >
          <Crosshair className={`w-3.5 h-3.5 ${trackedNodeId ? 'animate-spin' : ''}`} />
          <span>{trackedNodeId ? 'LOCKED' : 'TRACK'}</span>
        </button>

        <div className="w-px h-4 bg-border-subtle" />

        {/* Layer Visibility Menu Trigger */}
        <button
          onClick={() => setIsLayersOpen(!isLayersOpen)}
          className={`flex items-center gap-1 px-2 py-1 rounded font-mono text-[11px] transition ${
            isLayersOpen ? 'bg-bg-card text-brand-cyan' : 'text-slate-400 hover:text-slate-200'
          }`}
          title="Toggle Geospatial & Radio Layers"
        >
          <Layers className="w-3.5 h-3.5" />
          <span>LAYERS</span>
        </button>
      </div>

      {/* Layer Toggles Floating Dropdown Card */}
      {isLayersOpen && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 w-64 bg-bg-panel/95 backdrop-blur-md border border-border-highlight/40 rounded-lg p-2.5 shadow-2xl z-30 flex flex-col gap-1.5 text-xs">
          <span className="text-[10px] font-bold text-slate-400 font-mono uppercase tracking-wider mb-1">
            Display Layer Switches
          </span>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <SatIcon className="w-3.5 h-3.5 text-brand-cyan" /> LEO Satellites
            </span>
            <input
              type="checkbox"
              checked={layers.leoSatellites}
              onChange={() => toggleLayer('leoSatellites')}
              className="accent-brand-cyan"
            />
          </label>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <Compass className="w-3.5 h-3.5 text-brand-blue" /> Orbit Tracks
            </span>
            <input
              type="checkbox"
              checked={layers.leoOrbits}
              onChange={() => toggleLayer('leoOrbits')}
              className="accent-brand-cyan"
            />
          </label>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-orange-400" /> ISL Mesh Links
            </span>
            <input
              type="checkbox"
              checked={layers.islLinks}
              onChange={() => toggleLayer('islLinks')}
              className="accent-brand-cyan"
            />
          </label>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-emerald-400" /> 5G gNodeBs & Coverage
            </span>
            <input
              type="checkbox"
              checked={layers.rsuAndGnb}
              onChange={() => toggleLayer('rsuAndGnb')}
              className="accent-brand-cyan"
            />
          </label>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <Car className="w-3.5 h-3.5 text-brand-cyan" /> Fleet Vehicles
            </span>
            <input
              type="checkbox"
              checked={layers.vehicles}
              onChange={() => toggleLayer('vehicles')}
              className="accent-brand-cyan"
            />
          </label>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <Crosshair className="w-3.5 h-3.5 text-emerald-400" /> 5G Serving Links
            </span>
            <input
              type="checkbox"
              checked={layers.nrLinks}
              onChange={() => toggleLayer('nrLinks')}
              className="accent-brand-cyan"
            />
          </label>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <SatIcon className="w-3.5 h-3.5 text-brand-cyan" /> NTN Satellite Links
            </span>
            <input
              type="checkbox"
              checked={layers.ntnLinks}
              onChange={() => toggleLayer('ntnLinks')}
              className="accent-brand-cyan"
            />
          </label>

          <label className="flex items-center justify-between text-slate-300 hover:text-white cursor-pointer py-0.5">
            <span className="flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-accent-red" /> Blind Spot Zones
            </span>
            <input
              type="checkbox"
              checked={true}
              readOnly
              className="accent-accent-red opacity-80"
            />
          </label>
        </div>
      )}

      {/* Mini Tactical Legend (Bottom Left) */}
      <div className="absolute bottom-3 left-3 bg-bg-panel/85 backdrop-blur-md border border-border-subtle p-2 rounded text-[10px] font-mono flex flex-col gap-1 z-20 text-slate-300 shadow-lg pointer-events-none">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
          <span>5G NR Terrestrial</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-brand-cyan" />
          <span>Satellite LEO NTN</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-accent-purple" />
          <span>V2X Direct Sidelink</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          <span>Outage / Blind Spot</span>
        </div>
      </div>
    </div>
  );
};
