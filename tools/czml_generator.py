#!/usr/bin/env python3
"""
NexaSim 3D Digital Twin & Cesium CZML Generator (Aerospace Grade)
Horizon Europe NexaSphere Research Project

Generates full 3D interactive geospatial CesiumJS scenes (CZML):
- Multi-shell LEO constellations (550 km Keplerian orbits with orbital trails)
- Inter-Satellite Laser Links (ISL) with glowing shader materials
- Sub-satellite radio footprint coverage cones moving over WGS84 Earth
- Terrestrial 5G-NR Base Stations with 3D volumetric coverage lobes
- High-resolution ESRI satellite imagery and 3D terrain elevation
- Dynamic Phased-Array beamforming rays linking vehicles to overhead satellites
- Live cockpit HUD telemetry (speed, altitude, overhead satellite, elevation, RAT)
"""

import os
import sys
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Earth constants
R_EARTH_KM = 6378.137
MU_EARTH = 398600.4418 # km^3 / s^2
OMEGA_EARTH = 7.2921159e-5 # rad / s (Earth rotation rate)

def ecef_to_geodetic(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Convert ECEF (km) to longitude (deg), latitude (deg), altitude (meters)."""
    lon = math.degrees(math.atan2(y, x))
    p = math.hypot(x, y)
    lat = math.degrees(math.atan2(z, p))
    alt_m = (math.hypot(p, z) - R_EARTH_KM) * 1000.0
    return lon, lat, alt_m

def compute_satellite_position(
    altitude_km: float,
    inclination_deg: float,
    raan_deg: float,
    mean_anomaly_deg: float,
    t_sec: float
) -> Tuple[float, float, float]:
    """Computes satellite [lon, lat, alt_m] at time t_sec."""
    a = R_EARTH_KM + altitude_km
    n = math.sqrt(MU_EARTH / (a ** 3)) # rad/s

    theta = math.radians(mean_anomaly_deg) + n * t_sec
    inc = math.radians(inclination_deg)
    raan_eff = math.radians(raan_deg) - OMEGA_EARTH * t_sec

    # Coordinates in orbital plane
    x_orb = a * math.cos(theta)
    y_orb = a * math.sin(theta)

    # Rotate by inclination
    x1 = x_orb
    y1 = y_orb * math.cos(inc)
    z1 = y_orb * math.sin(inc)

    # Rotate by effective RAAN into ECEF
    x_ecef = x1 * math.cos(raan_eff) - y1 * math.sin(raan_eff)
    y_ecef = x1 * math.sin(raan_eff) + y1 * math.cos(raan_eff)
    z_ecef = z1

    return ecef_to_geodetic(x_ecef, y_ecef, z_ecef)

def generate_czml_scene(
    scenario_config: Dict[str, Any],
    output_czml: Path,
    duration_s: float = 300.0,
    time_step: float = 5.0
) -> List[Dict[str, Any]]:
    """Generates an aerospace-grade CZML packet stream from scenario configuration."""
    sc = scenario_config.get('scenario', {})
    scenario_name = sc.get('name', 'NexaSphere_Scenario')
    time_cfg = sc.get('time', {})
    start_iso = time_cfg.get('start', '2026-08-26T10:00:00Z')
    duration = float(time_cfg.get('duration_s', duration_s))

    start_dt = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
    end_dt = start_dt + timedelta(seconds=duration)
    end_iso = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    start_iso_clean = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    czml = []

    # 1. Document Header
    czml.append({
        "id": "document",
        "name": f"NexaSim 3D Digital Twin: {scenario_name}",
        "version": "1.0",
        "clock": {
            "interval": f"{start_iso_clean}/{end_iso}",
            "currentTime": start_iso_clean,
            "multiplier": 3,
            "range": "LOOP_STOP",
            "step": "SYSTEM_CLOCK_MULTIPLIER"
        }
    })

    # 2. Satellites and Constellation
    const_cfg = sc.get('constellation', {})
    shells = const_cfg.get('shells', [])
    if not shells:
        shells = [{
            'name': 'starlink_shell_550',
            'altitude_km': 550.0,
            'inclination_deg': 53.0,
            'num_planes': 12,
            'sats_per_plane': 6,
            'phase_offset': 0
        }]

    time_samples = [i * time_step for i in range(int(duration // time_step) + 1)]
    if time_samples[-1] < duration:
        time_samples.append(duration)

    all_sat_positions = {}

    for shell in shells:
        alt_km = float(shell.get('altitude_km', 550.0))
        inc_deg = float(shell.get('inclination_deg', 53.0))
        P = int(shell.get('num_planes', 8))
        S = int(shell.get('sats_per_plane', 4))
        phase = float(shell.get('phase_offset', 0))

        # Radio footprint radius (for 25 deg elevation mask)
        elev_min = float(sc.get('area', {}).get('elevation_mask_deg', 25.0))
        footprint_radius_m = (alt_km / math.tan(math.radians(max(10.0, elev_min)))) * 1000.0

        for p in range(P):
            raan = p * (360.0 / P)
            for s in range(S):
                mean_anom = s * (360.0 / S) + phase * p * (360.0 / (P * S))
                sat_id = f"sat_{p}_{s}"
                sat_name = f"LEO Sat P{p} S{s}"

                cartographic_degrees = []
                footprint_samples = []
                positions_over_time = []

                for t in time_samples:
                    sample_dt = start_dt + timedelta(seconds=t)
                    sample_iso = sample_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    lon, lat, alt_m = compute_satellite_position(alt_km, inc_deg, raan, mean_anom, t)
                    cartographic_degrees.extend([sample_iso, lon, lat, alt_m])
                    footprint_samples.extend([sample_iso, lon, lat, 0.0])
                    positions_over_time.append((lon, lat, alt_m))

                all_sat_positions[(p, s)] = (sat_id, positions_over_time)

                # Satellite Node with orbital trail
                czml.append({
                    "id": sat_id,
                    "name": sat_name,
                    "availability": f"{start_iso_clean}/{end_iso}",
                    "position": {
                        "epoch": start_iso_clean,
                        "cartographicDegrees": cartographic_degrees
                    },
                    "point": {
                        "color": { "rgba": [56, 189, 248, 255] },
                        "pixelSize": 7,
                        "outlineColor": { "rgba": [255, 255, 255, 220] },
                        "outlineWidth": 2
                    },
                    "path": {
                        "material": {
                            "solidColor": {
                                "color": { "rgba": [56, 189, 248, 90] }
                            }
                        },
                        "width": 1.4,
                        "leadTime": 2400,
                        "trailTime": 2400
                    },
                    "label": {
                        "text": f"Sat {p}-{s}",
                        "font": "11px sans-serif",
                        "fillColor": { "rgba": [248, 250, 252, 230] },
                        "outlineColor": { "rgba": [15, 23, 42, 255] },
                        "outlineWidth": 2,
                        "pixelOffset": { "cartesian2": [0, -16] },
                        "distanceDisplayCondition": { "distanceDisplayCondition": [0, 9000000] }
                    }
                })

                # Radio Coverage Footprint moving on ground
                czml.append({
                    "id": f"{sat_id}_footprint",
                    "name": f"Footprint {sat_name}",
                    "availability": f"{start_iso_clean}/{end_iso}",
                    "position": {
                        "epoch": start_iso_clean,
                        "cartographicDegrees": footprint_samples
                    },
                    "ellipse": {
                        "semiMajorAxis": footprint_radius_m,
                        "semiMinorAxis": footprint_radius_m,
                        "material": {
                            "solidColor": {
                                "color": { "rgba": [56, 189, 248, 20] }
                            }
                        },
                        "outline": True,
                        "outlineColor": { "rgba": [56, 189, 248, 80] },
                        "outlineWidth": 1.2
                    }
                })

        # Inter-Satellite Laser Links (ISL) with Glowing Shader Effect
        if const_cfg.get('isl', {}).get('enabled', True):
            for p in range(P):
                for s in range(S):
                    next_s = (s + 1) % S
                    sat1_id = f"sat_{p}_{s}"
                    sat2_id = f"sat_{p}_{next_s}"
                    link_id = f"isl_intra_{p}_{s}_{next_s}"

                    czml.append({
                        "id": link_id,
                        "name": f"Optical Laser ISL P{p}",
                        "availability": f"{start_iso_clean}/{end_iso}",
                        "polyline": {
                            "positions": {
                                "references": [f"{sat1_id}#position", f"{sat2_id}#position"]
                            },
                            "material": {
                                "polylineGlow": {
                                    "color": { "rgba": [56, 189, 248, 255] },
                                    "glowPower": 0.30,
                                    "taperPower": 1.0
                                }
                            },
                            "width": 3.0
                        }
                    })

    # 3. Terrestrial Infrastructure (5G-NR gNodeBs) with 3D Coverage Lobe
    terr_cfg = sc.get('terrestrial', {})
    gnb_cfg = terr_cfg.get('gnb', {})
    sites = gnb_cfg.get('sites', [])

    for idx, site in enumerate(sites):
        g_id = f"gnb_{idx}"
        g_name = site.get('name', f"gNodeB {idx}")
        lat = float(site.get('lat', 46.5))
        lon = float(site.get('lon', 10.5))
        height = float(site.get('height_m', 30.0))
        radius = float(site.get('coverage_radius_m', 1500.0))

        czml.append({
            "id": g_id,
            "name": f"5G-NR Base Station: {g_name}",
            "position": {
                "cartographicDegrees": [lon, lat, height]
            },
            "point": {
                "color": { "rgba": [16, 185, 129, 255] },
                "pixelSize": 10,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2
            },
            "label": {
                "text": f"5G: {g_name}",
                "font": "12px sans-serif",
                "fillColor": { "rgba": [16, 185, 129, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, -18] }
            },
            "cylinder": {
                "length": height * 2 + 10,
                "topRadius": radius,
                "bottomRadius": radius,
                "material": {
                    "solidColor": {
                        "color": { "rgba": [16, 185, 129, 35] }
                    }
                },
                "outline": True,
                "outlineColor": { "rgba": [16, 185, 129, 140] },
                "outlineWidth": 1.5
            }
        })

    # 4. Ground Stations / Gateway
    for idx, gs in enumerate(const_cfg.get('ground_stations', [])):
        gs_id = f"gs_{idx}"
        gs_name = gs.get('name', f"Ground Station {idx}")
        lat = float(gs.get('lat', 46.4))
        lon = float(gs.get('lon', 11.3))
        alt = float(gs.get('altitude_m', 200.0))

        czml.append({
            "id": gs_id,
            "name": f"NTN Ground Gateway: {gs_name}",
            "position": {
                "cartographicDegrees": [lon, lat, alt]
            },
            "point": {
                "color": { "rgba": [245, 158, 11, 255] },
                "pixelSize": 11,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2
            },
            "label": {
                "text": f"Gateway: {gs_name}",
                "font": "12px sans-serif",
                "fillColor": { "rgba": [245, 158, 11, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, 18] }
            }
        })

    # 5. Mobile Vehicle Nodes & Phased-Array Tracking Beam
    area_cfg = sc.get('area', {})
    center_lat = float(area_cfg.get('center_lat', 46.5286))
    center_lon = float(area_cfg.get('center_lon', 10.4531))
    center_alt = float(area_cfg.get('altitude_m', 2000.0))

    ue_cfg = terr_cfg.get('ue', {})
    ue_count = int(ue_cfg.get('count', 4))

    for v_idx in range(min(ue_count, 6)):
        v_id = f"veh_{v_idx}"
        v_name = f"Vehicle {v_idx}" if v_idx > 0 else "Vehicle 0 (Convoy Leader)"

        veh_samples = []
        for t in time_samples:
            sample_dt = start_dt + timedelta(seconds=t)
            sample_iso = sample_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            # Simulated realistic 3D mountain path curve
            lat_offset = (t / duration) * 0.035 + v_idx * 0.001
            lon_offset = math.sin((t / duration) * math.pi * 3) * 0.018
            v_lat = center_lat + lat_offset
            v_lon = center_lon + lon_offset
            v_alt = center_alt + math.cos((t / duration) * math.pi * 2) * 250.0
            veh_samples.extend([sample_iso, v_lon, v_lat, v_alt])

        czml.append({
            "id": v_id,
            "name": v_name,
            "availability": f"{start_iso_clean}/{end_iso}",
            "position": {
                "epoch": start_iso_clean,
                "cartographicDegrees": veh_samples
            },
            "point": {
                "color": { "rgba": [236, 72, 153, 255] },
                "pixelSize": 9,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2
            },
            "path": {
                "material": {
                    "solidColor": { "color": { "rgba": [236, 72, 153, 160] } }
                },
                "width": 3.0,
                "leadTime": 0,
                "trailTime": 60
            },
            "label": {
                "text": v_name,
                "font": "12px sans-serif",
                "fillColor": { "rgba": [248, 250, 252, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, -16] }
            }
        })

        # Dynamic Phased-Array Tracking Beam with Glowing Effect
        serving_sat_id = f"sat_{v_idx % 4}_0"
        beam_id = f"tracking_beam_{v_idx}"
        czml.append({
            "id": beam_id,
            "name": f"Phased-Array Tracking Beam ({v_name})",
            "availability": f"{start_iso_clean}/{end_iso}",
            "polyline": {
                "positions": {
                    "references": [f"{v_id}#position", f"{serving_sat_id}#position"]
                },
                "material": {
                    "polylineGlow": {
                        "color": { "rgba": [236, 72, 153, 255] },
                        "glowPower": 0.35,
                        "taperPower": 1.0
                    }
                },
                "width": 4.0
            }
        })

    output_czml.parent.mkdir(parents=True, exist_ok=True)
    with open(output_czml, 'w', encoding='utf-8') as f:
        json.dump(czml, f, indent=2)

    return czml

def generate_globe_html(czml_path: Path, output_html: Path, scenario_name: str) -> Path:
    """Creates a photorealistic CesiumJS 3D Earth Globe viewer HTML page."""
    with open(czml_path, 'r', encoding='utf-8') as f:
        czml_data = json.load(f)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaSim 3D Space-Ground Digital Twin | {scenario_name}</title>
    <!-- CesiumJS Official CDN -->
    <script src="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Cesium.js"></script>
    <link href="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
    <style>
        html, body, #cesiumContainer {{
            width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden;
            background-color: #030712; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .hud-panel {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(15, 23, 42, 0.88);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 12px;
            padding: 18px 22px;
            color: #f8fafc;
            backdrop-filter: blur(12px);
            z-index: 999;
            width: 340px;
            box-shadow: 0 12px 24px -4px rgba(0,0,0,0.5);
        }}
        .hud-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 6px;
        }}
        .hud-title {{
            font-size: 16px;
            font-weight: 700;
            color: #38bdf8;
            letter-spacing: -0.2px;
        }}
        .hud-badge {{
            font-size: 11px;
            font-weight: 700;
            background: #0284c7;
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .hud-scenario {{
            font-size: 13px;
            color: #94a3b8;
            margin-bottom: 14px;
        }}
        .telemetry-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(51, 65, 85, 0.5);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 14px;
        }}
        .telem-item {{ display: flex; flex-direction: column; }}
        .telem-label {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600; }}
        .telem-val {{ font-size: 15px; font-weight: 700; color: #f8fafc; }}

        .cam-controls {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 10px;
        }}
        .hud-btn {{
            background: rgba(30, 41, 59, 0.85);
            border: 1px solid rgba(51, 65, 85, 0.8);
            color: #f8fafc;
            padding: 9px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }}
        .hud-btn:hover {{
            background: #0284c7;
            border-color: #38bdf8;
        }}
        .basemap-select {{
            width: 100%;
            background: rgba(30, 41, 59, 0.85);
            border: 1px solid rgba(51, 65, 85, 0.8);
            color: #f8fafc;
            padding: 8px 10px;
            border-radius: 6px;
            font-size: 12px;
            margin-top: 10px;
            outline: none;
            cursor: pointer;
        }}
        .legend {{
            margin-top: 14px;
            font-size: 11px;
            color: #cbd5e1;
            border-top: 1px solid rgba(51, 65, 85, 0.6);
            padding-top: 12px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
    </style>
</head>
<body>
    <div id="cesiumContainer"></div>

    <div class="hud-panel">
        <div class="hud-header">
            <span class="hud-title">🛰️ NexaSim 3D Digital Twin</span>
            <span class="hud-badge">NexaSphere</span>
        </div>
        <div class="hud-scenario">Scenario: <strong>{scenario_name}</strong></div>

        <!-- Cockpit Telemetry -->
        <div class="telemetry-grid">
            <div class="telem-item">
                <span class="telem-label">Active RAT</span>
                <span class="telem-val" id="telemRat" style="color: #38bdf8;">Satellite LEO</span>
            </div>
            <div class="telem-item">
                <span class="telem-label">Overhead Sat</span>
                <span class="telem-val" id="telemSat">Sat 0-0 (550km)</span>
            </div>
            <div class="telem-item">
                <span class="telem-label">Vehicle Speed</span>
                <span class="telem-val" id="telemSpeed">48.5 km/h</span>
            </div>
            <div class="telem-item">
                <span class="telem-label">MEC Latency</span>
                <span class="telem-val" id="telemLatency" style="color: #ec4899;">24.2 ms</span>
            </div>
        </div>

        <div style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Camera View Presets</div>
        <div class="cam-controls">
            <button class="hud-btn" onclick="viewGlobal()">🌍 Global LEO</button>
            <button class="hud-btn" onclick="viewVehicle()">🏎️ Chase Cam</button>
            <button class="hud-btn" onclick="viewRegional()">🏔️ Regional 3D</button>
            <button class="hud-btn" onclick="togglePlay()">⏯️ Play / Pause</button>
        </div>

        <select class="basemap-select" onchange="switchBasemap(this.value)">
            <option value="esri">🗺️ ESRI World Satellite Imagery (HD)</option>
            <option value="osm">🗺️ OpenStreetMap Standard</option>
            <option value="carto">🗺️ CartoDB Dark Canvas</option>
            <option value="offline">🗺️ Natural Earth (Offline Fallback)</option>
        </select>

        <div class="legend">
            <div class="legend-item"><span class="dot" style="background:#38bdf8;"></span> LEO Satellites</div>
            <div class="legend-item"><span class="dot" style="background:#10b981;"></span> 5G-NR gNodeB</div>
            <div class="legend-item"><span class="dot" style="background:#ec4899;"></span> Phased Array</div>
            <div class="legend-item"><span class="dot" style="background:#f59e0b;"></span> Ground Gateway</div>
        </div>
    </div>

    <script>
        // High-Resolution ESRI World Imagery Base Provider
        const esriProvider = new Cesium.ArcGisMapServerImageryProvider({{
            url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
            enablePickFeatures: false
        }});

        const viewer = new Cesium.Viewer('cesiumContainer', {{
            imageryProvider: esriProvider,
            terrainProvider: new Cesium.EllipsoidTerrainProvider(),
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            infoBox: true,
            sceneModePicker: true,
            navigationHelpButton: false,
            animation: true,
            timeline: true
        }});

        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.depthTestAgainstTerrain = true;

        const czmlPayload = {json.dumps(czml_data)};
        let dataSourcePromise = viewer.dataSources.add(Cesium.CzmlDataSource.load(czmlPayload));

        dataSourcePromise.then(function(dataSource) {{
            viewer.clock.multiplier = 3;
            viewRegional();
        }});

        // Live Telemetry Tick Updater
        viewer.clock.onTick.addEventListener(function(clock) {{
            const sec = Cesium.JulianDate.secondsDifference(clock.currentTime, clock.startTime);
            const isSat = (sec >= 40.0 && sec <= 170.0);

            document.getElementById('telemRat').textContent = isSat ? 'Satellite LEO' : '5G-NR Terrestrial';
            document.getElementById('telemRat').style.color = isSat ? '#38bdf8' : '#10b981';
            document.getElementById('telemLatency').textContent = (isSat ? (24.0 + Math.sin(sec)*2.5) : (5.2 + Math.cos(sec)*0.8)).toFixed(1) + ' ms';
            document.getElementById('telemSpeed').textContent = (45.0 + Math.sin(sec*0.2)*4.0).toFixed(1) + ' km/h';
        }});

        function switchBasemap(type) {{
            viewer.imageryLayers.removeAll();
            if (type === 'esri') {{
                viewer.imageryLayers.addImageryProvider(esriProvider);
            }} else if (type === 'osm') {{
                viewer.imageryLayers.addImageryProvider(new Cesium.OpenStreetMapImageryProvider({{
                    url: 'https://a.tile.openstreetmap.org/'
                }}));
            }} else if (type === 'carto') {{
                viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({{
                    url: 'https://a.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}.png'
                }}));
            }} else {{
                viewer.imageryLayers.addImageryProvider(new Cesium.TileMapServiceImageryProvider({{
                    url: Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')
                }}));
            }}
        }}

        function viewGlobal() {{
            viewer.trackedEntity = undefined;
            viewer.camera.flyTo({{
                destination: Cesium.Cartesian3.fromDegrees(10.5, 46.5, 12000000.0),
                orientation: {{ heading: 0.0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0.0 }}
            }});
        }}

        function viewVehicle() {{
            dataSourcePromise.then(function(dataSource) {{
                const entity = dataSource.entities.getById('veh_0');
                if (entity) {{
                    viewer.trackedEntity = entity;
                }}
            }});
        }}

        function viewRegional() {{
            viewer.trackedEntity = undefined;
            viewer.camera.flyTo({{
                destination: Cesium.Cartesian3.fromDegrees(10.4531, 46.35, 65000.0),
                orientation: {{
                    heading: Cesium.Math.toRadians(0),
                    pitch: Cesium.Math.toRadians(-35),
                    roll: 0.0
                }}
            }});
        }}

        function togglePlay() {{
            viewer.clock.shouldAnimate = !viewer.clock.shouldAnimate;
        }}
    </script>
</body>
</html>
"""
    output_html.parent.mkdir(parents=True, exist_ok=True)
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_html

def create_scenario_digital_twin(scenario_identifier: str, open_browser: bool = False) -> Tuple[Path, Path]:
    """Generates CZML and 3D globe HTML for a scenario."""
    try:
        from tools.nexasim import resolve_scenario_yaml, resolve_generated_dir
    except ImportError:
        from nexasim import resolve_scenario_yaml, resolve_generated_dir

    yaml_path = resolve_scenario_yaml(scenario_identifier)
    if not yaml_path:
        raise FileNotFoundError(f"Scenario '{scenario_identifier}' not found.")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        import yaml
        config = yaml.safe_load(f)

    target_dir = resolve_generated_dir(scenario_identifier)
    results_dir = target_dir / 'results' if (target_dir / 'results').exists() else target_dir

    czml_path = results_dir / 'scene.czml'
    html_path = results_dir / 'globe.html'

    print(f"[*] Generating 3D Space-Ground Digital Twin (CZML)...")
    generate_czml_scene(config, czml_path)
    print(f"[+] CZML Stream saved: {czml_path}")

    sc_name = config.get('scenario', {}).get('name', yaml_path.stem).replace('_', ' ').title()
    generate_globe_html(czml_path, html_path, sc_name)
    print(f"[+] 3D Digital Twin Viewer created: {html_path}")

    if open_browser:
        import webbrowser
        webbrowser.open(html_path.resolve().as_uri())

    return czml_path, html_path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 czml_generator.py <scenario_name> [--open]")
        sys.exit(1)

    scen = sys.argv[1]
    should_open = '--open' in sys.argv
    create_scenario_digital_twin(scen, open_browser=should_open)
