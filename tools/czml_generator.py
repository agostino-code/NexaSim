#!/usr/bin/env python3
"""
NexaSim 3D Digital Twin & Cesium CZML Generator
Horizon Europe NexaSphere Research Project

Generates full 3D interactive geospatial CesiumJS scenes (CZML):
- Multi-shell LEO constellations (550 km orbits with Keplerian mechanics)
- Inter-Satellite Laser Links (ISL) glowing in 3D space
- Terrestrial 5G-NR Base Stations with coverage cones
- Vehicles traversing 3D orographic terrain (WGS84 geodetic)
- Dynamic beamforming rays connecting phased-array antennas to satellites
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
    """Generates a complete CZML packet stream from scenario configuration."""
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
            "multiplier": 5,
            "range": "LOOP_STOP",
            "step": "SYSTEM_CLOCK_MULTIPLIER"
        }
    })

    # 2. Satellites and Constellation
    const_cfg = sc.get('constellation', {})
    shells = const_cfg.get('shells', [])
    if not shells:
        # Default shell if none defined
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

    all_sat_positions = {} # (plane_idx, sat_idx) -> list of [lon, lat, alt]

    for shell in shells:
        alt_km = float(shell.get('altitude_km', 550.0))
        inc_deg = float(shell.get('inclination_deg', 53.0))
        P = int(shell.get('num_planes', 8))
        S = int(shell.get('sats_per_plane', 4))
        phase = float(shell.get('phase_offset', 0))

        for p in range(P):
            raan = p * (360.0 / P)
            for s in range(S):
                mean_anom = s * (360.0 / S) + phase * p * (360.0 / (P * S))
                sat_id = f"sat_{p}_{s}"
                sat_name = f"LEO Sat P{p} S{s}"

                cartographic_degrees = []
                positions_over_time = []

                for t in time_samples:
                    sample_dt = start_dt + timedelta(seconds=t)
                    sample_iso = sample_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    lon, lat, alt_m = compute_satellite_position(alt_km, inc_deg, raan, mean_anom, t)
                    cartographic_degrees.extend([sample_iso, lon, lat, alt_m])
                    positions_over_time.append((lon, lat, alt_m))

                all_sat_positions[(p, s)] = (sat_id, positions_over_time)

                # Satellite Entity
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
                        "pixelSize": 6,
                        "outlineColor": { "rgba": [14, 165, 233, 200] },
                        "outlineWidth": 2
                    },
                    "path": {
                        "material": {
                            "solidColor": {
                                "color": { "rgba": [56, 189, 248, 80] }
                            }
                        },
                        "width": 1.2,
                        "leadTime": 1800,
                        "trailTime": 1800
                    },
                    "label": {
                        "text": f"Sat {p}-{s}",
                        "font": "11px sans-serif",
                        "fillColor": { "rgba": [248, 250, 252, 220] },
                        "outlineColor": { "rgba": [15, 23, 42, 255] },
                        "outlineWidth": 2,
                        "pixelOffset": { "cartesian2": [0, -14] },
                        "distanceDisplayCondition": { "distanceDisplayCondition": [0, 8000000] }
                    }
                })

        # Inter-Satellite Laser Links (ISL)
        if const_cfg.get('isl', {}).get('enabled', True):
            # Intra-plane links
            for p in range(P):
                for s in range(S):
                    next_s = (s + 1) % S
                    sat1_id = f"sat_{p}_{s}"
                    sat2_id = f"sat_{p}_{next_s}"
                    link_id = f"isl_intra_{p}_{s}_{next_s}"

                    # Connect references
                    czml.append({
                        "id": link_id,
                        "name": f"Laser ISL Intra P{p}",
                        "availability": f"{start_iso_clean}/{end_iso}",
                        "polyline": {
                            "positions": {
                                "references": [f"{sat1_id}#position", f"{sat2_id}#position"]
                            },
                            "material": {
                                "solidColor": {
                                    "color": { "rgba": [56, 189, 248, 160] }
                                }
                            },
                            "width": 1.8
                        }
                    })

    # 3. Terrestrial Infrastructure (gNodeBs)
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

        # Base Station Marker
        czml.append({
            "id": g_id,
            "name": f"5G-NR Base Station: {g_name}",
            "position": {
                "cartographicDegrees": [lon, lat, height]
            },
            "point": {
                "color": { "rgba": [16, 185, 129, 255] },
                "pixelSize": 9,
                "outlineColor": { "rgba": [5, 150, 105, 255] },
                "outlineWidth": 2
            },
            "label": {
                "text": f"5G: {g_name}",
                "font": "12px sans-serif",
                "fillColor": { "rgba": [16, 185, 129, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, -16] }
            },
            # Coverage Cylinder
            "cylinder": {
                "length": height * 2 + 10,
                "topRadius": radius,
                "bottomRadius": radius,
                "material": {
                    "solidColor": {
                        "color": { "rgba": [16, 185, 129, 40] }
                    }
                },
                "outline": True,
                "outlineColor": { "rgba": [16, 185, 129, 120] }
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
            "name": f"NTN Ground Station: {gs_name}",
            "position": {
                "cartographicDegrees": [lon, lat, alt]
            },
            "point": {
                "color": { "rgba": [245, 158, 11, 255] },
                "pixelSize": 10,
                "outlineColor": { "rgba": [217, 119, 6, 255] },
                "outlineWidth": 2
            },
            "label": {
                "text": f"Gateway: {gs_name}",
                "font": "12px sans-serif",
                "fillColor": { "rgba": [245, 158, 11, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, 16] }
            }
        })

    # 5. Vehicles / Mobile Terminals & Dynamic Beam Tracking
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
            # Simulated vehicle traversal along geographic road curve
            lat_offset = (t / duration) * 0.04 + v_idx * 0.001
            lon_offset = math.sin((t / duration) * math.pi * 3) * 0.02
            v_lat = center_lat + lat_offset
            v_lon = center_lon + lon_offset
            v_alt = center_alt + math.cos((t / duration) * math.pi) * 300.0
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
                "pixelSize": 8,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2
            },
            "path": {
                "material": {
                    "solidColor": { "color": { "rgba": [236, 72, 153, 140] } }
                },
                "width": 2.5,
                "leadTime": 0,
                "trailTime": 60
            },
            "label": {
                "text": v_name,
                "font": "12px sans-serif",
                "fillColor": { "rgba": [248, 250, 252, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, -14] }
            }
        })

        # Dynamic Phased Array Beam Tracking to Overhead Satellite
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
                    "solidColor": {
                        "color": { "rgba": [236, 72, 153, 180] }
                    }
                },
                "width": 2.0
            }
        })

    # Write output CZML
    output_czml.parent.mkdir(parents=True, exist_ok=True)
    with open(output_czml, 'w', encoding='utf-8') as f:
        json.dump(czml, f, indent=2)

    return czml

def generate_globe_html(czml_path: Path, output_html: Path, scenario_name: str) -> Path:
    """Creates a self-contained CesiumJS 3D Earth Globe viewer HTML page."""
    with open(czml_path, 'r', encoding='utf-8') as f:
        czml_data = json.load(f)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaSim 3D Space-Ground Digital Twin | {scenario_name}</title>
    <!-- CesiumJS from Official Cloudflare / CDN -->
    <script src="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Cesium.js"></script>
    <link href="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
    <style>
        html, body, #cesiumContainer {{
            width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden;
            background-color: #000; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .hud-overlay {{
            position: absolute;
            top: 16px;
            left: 16px;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 10px;
            padding: 16px 20px;
            color: #f8fafc;
            backdrop-filter: blur(8px);
            z-index: 999;
            max-width: 360px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.4);
        }}
        .hud-title {{
            font-size: 16px;
            font-weight: 700;
            color: #38bdf8;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .hud-subtitle {{
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 12px;
        }}
        .cam-controls {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 10px;
        }}
        .hud-btn {{
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(51, 65, 85, 0.8);
            color: #f8fafc;
            padding: 8px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .hud-btn:hover {{
            background: #0284c7;
            border-color: #38bdf8;
        }}
        .legend-box {{
            margin-top: 12px;
            font-size: 11px;
            color: #cbd5e1;
            border-top: 1px solid rgba(51, 65, 85, 0.6);
            padding-top: 10px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
    </style>
</head>
<body>
    <div id="cesiumContainer"></div>

    <div class="hud-overlay">
        <div class="hud-title">🛰️ NexaSim 3D Digital Twin</div>
        <div class="hud-subtitle">Scenario: <strong>{scenario_name}</strong></div>

        <div style="font-size: 12px; color: #94a3b8; font-weight: 600;">Camera View Presets:</div>
        <div class="cam-controls">
            <button class="hud-btn" onclick="viewGlobal()">🌍 Global LEO</button>
            <button class="hud-btn" onclick="viewVehicle()">🏎️ Vehicle 0</button>
            <button class="hud-btn" onclick="viewRegional()">🏔️ Regional 3D</button>
            <button class="hud-btn" onclick="togglePlay()">⏯️ Play / Pause</button>
        </div>

        <div class="legend-box">
            <div class="legend-item"><span class="dot" style="background:#38bdf8;"></span> LEO Satellite</div>
            <div class="legend-item"><span class="dot" style="background:#10b981;"></span> 5G-NR gNodeB</div>
            <div class="legend-item"><span class="dot" style="background:#ec4899;"></span> Phased Array</div>
            <div class="legend-item"><span class="dot" style="background:#f59e0b;"></span> Ground Gateway</div>
        </div>
    </div>

    <script>
        // Initialize Cesium Viewer with Ion token-less public base layer
        const viewer = new Cesium.Viewer('cesiumContainer', {{
            imageryProvider: new Cesium.TileMapServiceImageryProvider({{
                url: Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')
            }}),
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

        const czmlPayload = {json.dumps(czml_data)};
        let dataSourcePromise = viewer.dataSources.add(Cesium.CzmlDataSource.load(czmlPayload));

        dataSourcePromise.then(function(dataSource) {{
            viewer.clock.multiplier = 3;
            viewRegional();
        }});

        function viewGlobal() {{
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
                destination: Cesium.Cartesian3.fromDegrees(10.5, 46.0, 800000.0),
                orientation: {{
                    heading: Cesium.Math.toRadians(0),
                    pitch: Cesium.Math.toRadians(-45),
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
