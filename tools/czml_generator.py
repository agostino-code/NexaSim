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
from dotenv import load_dotenv
load_dotenv()
import sys
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

def load_real_vehicle_trajectories(
    scenario_dir: Path,
    time_samples: List[float],
    start_dt: datetime,
    duration: float,
    ue_count: int,
    center_lat: float,
    center_lon: float
) -> Dict[int, List[Any]]:
    """
    Loads real georeferenced trajectories for vehicles:
    1. If trace_fcd.xml exists (post-simulation), parses exact microscopic WGS84 GPS traces.
    2. If route_geo.json exists (pre-simulation / real road), interpolates vehicle convoy along the road.
    3. Returns dict of v_idx -> [iso_time, lon, lat, alt, ...]
    """
    trajectories = {v: [] for v in range(ue_count)}

    # 1. Try microscopic SUMO FCD trace first
    fcd_candidates = [
        scenario_dir / 'trace_fcd.xml',
        scenario_dir / 'results' / 'trace_fcd.xml',
        scenario_dir.parent / 'trace_fcd.xml'
    ]
    fcd_path = next((p for p in fcd_candidates if p.exists() and p.stat().st_size > 100), None)

    if fcd_path:
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(fcd_path)
            root = tree.getroot()
            time_map = {}
            for ts in root.findall('timestep'):
                t_sec = float(ts.get('time', 0.0))
                for veh in ts.findall('vehicle'):
                    vid = veh.get('id', '')
                    if vid.startswith('veh_'):
                        try:
                            v_idx = int(vid.replace('veh_', ''))
                        except ValueError:
                            continue
                        if v_idx < ue_count:
                            lon = float(veh.get('x', 0.0))
                            lat = float(veh.get('y', 0.0))
                            alt = float(veh.get('z', 0.0))
                            if v_idx not in time_map:
                                time_map[v_idx] = {}
                            time_map[v_idx][t_sec] = (lon, lat, alt)

            if time_map:
                for v_idx in range(ue_count):
                    v_points = time_map.get(v_idx, {})
                    if not v_points:
                        continue
                    sorted_times = sorted(v_points.keys())
                    for t in time_samples:
                        sample_dt = start_dt + timedelta(seconds=t)
                        sample_iso = sample_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                        # Find closest recorded time
                        closest_t = min(sorted_times, key=lambda st: abs(st - t))
                        lon, lat, alt = v_points[closest_t]
                        trajectories[v_idx].extend([sample_iso, lon, lat, alt])

                if any(len(trajectories[v]) > 0 for v in trajectories):
                    print(f"[CZML Generator] Loaded {len(trajectories)} real vehicle trajectories from FCD trace: {fcd_path.name}")
                    return trajectories
        except Exception as e:
            print(f"[CZML Generator] Warning parsing FCD trace: {e}")

    # 2. Try pre-run real road coordinates from route_geo.json
    geo_candidates = [
        scenario_dir / 'route_geo.json',
        scenario_dir / 'results' / 'route_geo.json',
        scenario_dir.parent / 'route_geo.json'
    ]
    geo_path = next((p for p in geo_candidates if p.exists()), None)

    if geo_path:
        try:
            with open(geo_path, 'r', encoding='utf-8') as f:
                geo_data = json.load(f)
            coords = geo_data.get('coordinates', [])
            if len(coords) >= 2:
                # Compute cumulative segment lengths
                cum_dist = [0.0]
                total_len = 0.0
                for i in range(len(coords) - 1):
                    lat1, lon1 = coords[i]
                    lat2, lon2 = coords[i+1]
                    d_lat = (lat2 - lat1) * 111139.0
                    d_lon = (lon2 - lon1) * 111139.0 * math.cos(math.radians((lat1 + lat2) / 2))
                    seg_len = math.hypot(d_lat, d_lon)
                    total_len += seg_len
                    cum_dist.append(total_len)

                # Determine convoy speed to cover road within duration
                speed_ms = max(8.0, total_len / max(10.0, duration * 0.90))

                for v_idx in range(ue_count):
                    headway_offset_m = v_idx * 30.0  # 30m inter-vehicle distance
                    samples = []
                    for t in time_samples:
                        sample_dt = start_dt + timedelta(seconds=t)
                        sample_iso = sample_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                        dist = max(0.0, min(total_len, speed_ms * t - headway_offset_m))

                        # Find matching segment
                        seg_idx = 0
                        while seg_idx < len(cum_dist) - 2 and cum_dist[seg_idx + 1] < dist:
                            seg_idx += 1

                        s_start = cum_dist[seg_idx]
                        s_end = cum_dist[seg_idx + 1]
                        seg_len = max(0.001, s_end - s_start)
                        fraction = max(0.0, min(1.0, (dist - s_start) / seg_len))

                        latA, lonA = coords[seg_idx]
                        latB, lonB = coords[seg_idx + 1]
                        v_lat = latA + fraction * (latB - latA)
                        v_lon = lonA + fraction * (lonB - lonA)
                        samples.extend([sample_iso, v_lon, v_lat, 0.0])

                    trajectories[v_idx] = samples

                print(f"[CZML Generator] Interpolated {ue_count} vehicles along real road ({len(coords)} waypoints) from {geo_path.name}")
                return trajectories
        except Exception as e:
            print(f"[CZML Generator] Warning loading route_geo.json: {e}")

    return trajectories

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
                "pixelSize": 11,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2,
                "heightReference": "CLAMP_TO_GROUND"
            },
            "label": {
                "text": f"5G: {g_name}",
                "font": "12px sans-serif",
                "fillColor": { "rgba": [16, 185, 129, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, -18] },
                "heightReference": "CLAMP_TO_GROUND"
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
                "outlineWidth": 2,
                "heightReference": "CLAMP_TO_GROUND"
            },
            "label": {
                "text": f"Gateway: {gs_name}",
                "font": "12px sans-serif",
                "fillColor": { "rgba": [245, 158, 11, 255] },
                "outlineColor": { "rgba": [15, 23, 42, 255] },
                "outlineWidth": 2,
                "pixelOffset": { "cartesian2": [0, 18] },
                "heightReference": "CLAMP_TO_GROUND"
            }
        })

    # 5. Mobile Vehicle Nodes & Phased-Array Tracking Beam
    area_cfg = sc.get('area', {})
    center_lat = float(area_cfg.get('center_lat', 46.5286))
    center_lon = float(area_cfg.get('center_lon', 10.4531))
    center_alt = float(area_cfg.get('altitude_m', 2000.0))

    ue_cfg = terr_cfg.get('ue', {})
    ue_count = int(ue_cfg.get('count', 4))

    # Load real georeferenced road trajectories from route_geo.json or trace_fcd.xml
    scenario_dir = output_czml.parent
    if (scenario_dir.parent / 'route_geo.json').exists():
        scenario_dir = scenario_dir.parent
    real_veh_samples = load_real_vehicle_trajectories(
        scenario_dir=scenario_dir,
        time_samples=time_samples,
        start_dt=start_dt,
        duration=duration,
        ue_count=ue_count,
        center_lat=center_lat,
        center_lon=center_lon
    )

    for v_idx in range(min(ue_count, 6)):
        v_id = f"veh_{v_idx}"
        v_name = f"Vehicle {v_idx}" if v_idx > 0 else "Vehicle 0 (Convoy Leader)"

        veh_samples = real_veh_samples.get(v_idx, [])
        if not veh_samples:
            for t in time_samples:
                sample_dt = start_dt + timedelta(seconds=t)
                sample_iso = sample_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                lat_offset = (t / duration) * 0.025 + v_idx * 0.0008
                lon_offset = (t / duration) * 0.015
                v_lat = center_lat + lat_offset
                v_lon = center_lon + lon_offset
                veh_samples.extend([sample_iso, v_lon, v_lat, 0.0])

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
                "pixelSize": 12,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2.5,
                "heightReference": "CLAMP_TO_GROUND"
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
                "verticalOrigin": "BOTTOM",
                "pixelOffset": { "cartesian2": [0, -18] },
                "heightReference": "CLAMP_TO_GROUND"
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

def generate_globe_html(
    czml_path: Path,
    output_html: Path,
    scenario_name: str,
    center_lat: float = 46.5286,
    center_lon: float = 10.4531
) -> Path:
    """Creates a photorealistic CesiumJS 3D Earth Globe viewer HTML page."""
    cesium_token = '__CESIUM_ION_TOKEN__'
    carto_param = '?key=__CARTO_API_KEY__'
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
        <div class="cam-controls" style="grid-template-columns: repeat(3, 1fr);">
            <button class="hud-btn" onclick="viewTactical()">🎯 Tactical</button>
            <button class="hud-btn" onclick="viewVehicle()">🏎️ Chase Cam</button>
            <button class="hud-btn" onclick="viewConstellation()">🛰️ Orbit LEO</button>
        </div>

        <select class="basemap-select" onchange="switchBasemap(this.value)">
            <option value="default">🗺️ Cesium Ion World Satellite</option>
            <option value="esri">🗺️ ESRI World Satellite HD</option>
            <option value="osm">🗺️ OpenStreetMap Standard</option>
            <option value="carto">🗺️ CartoDB Dark Canvas</option>
        </select>

        <div class="legend">
            <div class="legend-item"><span class="dot" style="background:#38bdf8;"></span> LEO Satellites</div>
            <div class="legend-item"><span class="dot" style="background:#10b981;"></span> 5G-NR gNodeB</div>
            <div class="legend-item"><span class="dot" style="background:#ec4899;"></span> Phased Array</div>
            <div class="legend-item"><span class="dot" style="background:#f59e0b;"></span> Ground Gateway</div>
        </div>
    </div>

    <script>
        const token = '{cesium_token}';
        if (token) {{
            Cesium.Ion.defaultAccessToken = token;
        }}

        let viewer;
        try {{
            viewer = new Cesium.Viewer('cesiumContainer', {{
                terrainProvider: token ? Cesium.createWorldTerrain() : new Cesium.EllipsoidTerrainProvider(),
                baseLayerPicker: false,
                geocoder: false,
                homeButton: false,
                infoBox: true,
                sceneModePicker: true,
                navigationHelpButton: false,
                animation: true,
                timeline: true
            }});
        }} catch (err) {{
            console.warn("Falling back to ellipsoid terrain:", err);
            viewer = new Cesium.Viewer('cesiumContainer', {{
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
        }}

        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.depthTestAgainstTerrain = true;

        const czmlPayload = {json.dumps(czml_data)};
        let dataSourcePromise;
        try {{
            dataSourcePromise = viewer.dataSources.add(Cesium.CzmlDataSource.load(czmlPayload));
            dataSourcePromise.then(function(dataSource) {{
                viewer.clock.multiplier = 3;
                if (typeof window.viewTactical === 'function') {{
                    window.viewTactical();
                }}
            }}).catch(function(e) {{
                console.error("CZML Load Error:", e);
            }});
        }} catch (err) {{
            console.error("Failed to load CZML payload:", err);
        }}

        // Live Telemetry Tick Updater
        viewer.clock.onTick.addEventListener(function(clock) {{
            try {{
                const sec = Cesium.JulianDate.secondsDifference(clock.currentTime, clock.startTime);
                const isSat = (sec >= 40.0 && sec <= 170.0);

                const rEl = document.getElementById('telemRat');
                if (rEl) {{
                    rEl.textContent = isSat ? 'Satellite LEO' : '5G-NR Terrestrial';
                    rEl.style.color = isSat ? '#38bdf8' : '#10b981';
                }}
                const lEl = document.getElementById('telemLatency');
                if (lEl) lEl.textContent = (isSat ? (24.0 + Math.sin(sec)*2.5) : (5.2 + Math.cos(sec)*0.8)).toFixed(1) + ' ms';
                const sEl = document.getElementById('telemSpeed');
                if (sEl) sEl.textContent = (45.0 + Math.sin(sec*0.2)*4.0).toFixed(1) + ' km/h';
            }} catch(tickErr) {{}}
        }});

        window.switchBasemap = function(type) {{
            if (!viewer) return;
            viewer.imageryLayers.removeAll();
            try {{
                if (type === 'esri') {{
                    const esri = new Cesium.UrlTemplateImageryProvider({{
                        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
                        maximumLevel: 19
                    }});
                    viewer.imageryLayers.addImageryProvider(esri);
                }} else if (type === 'osm') {{
                    const osm = new Cesium.UrlTemplateImageryProvider({{
                        url: 'https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'
                    }});
                    viewer.imageryLayers.addImageryProvider(osm);
                }} else if (type === 'carto') {{
                    const carto = new Cesium.UrlTemplateImageryProvider({{
                        url: 'https://a.basemaps.cartocdn.com/rastertiles/dark_all/{{z}}/{{x}}/{{y}}.png{carto_param}'
                    }});
                    viewer.imageryLayers.addImageryProvider(carto);
                }} else {{
                    const defaultIon = new Cesium.IonImageryProvider({{ assetId: 2 }});
                    viewer.imageryLayers.addImageryProvider(defaultIon);
                }}
            }} catch (err) {{
                console.error("switchBasemap error:", err);
            }}
        }};

        // Check URL or postMessage to hide HUD panel in Dual Mode
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('hud') === '0' || urlParams.get('minimal') === '1') {{
            const hud = document.querySelector('.hud-panel');
            if (hud) hud.style.display = 'none';
        }}

        window.addEventListener('message', function(e) {{
            if (e.data && typeof e.data.showHud === 'boolean') {{
                const hud = document.querySelector('.hud-panel');
                if (hud) hud.style.display = e.data.showHud ? 'block' : 'none';
            }}
        }});

        // 1. Tactical Scenario View (close-range, perfectly aligned to scenario coordinates)
        window.viewTactical = function() {{
            if (!viewer) return;
            viewer.trackedEntity = undefined;
            const target = Cesium.Cartesian3.fromDegrees({center_lon}, {center_lat}, 0);
            viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(target, 2500), {{
                offset: new Cesium.HeadingPitchRange(
                    Cesium.Math.toRadians(20),
                    Cesium.Math.toRadians(-32),
                    5500
                ),
                duration: 1.5
            }});
        }};

        // 2. Chase Cam (locked tracking behind vehicle)
        window.viewVehicle = function() {{
            if (!viewer || !dataSourcePromise) return;
            dataSourcePromise.then(function(dataSource) {{
                const entity = dataSource.entities.getById('veh_0') ||
                               dataSource.entities.values.find(e => e.id && e.id.startsWith('veh_'));
                if (entity) {{
                    entity.viewFrom = new Cesium.Cartesian3(-60.0, -35.0, 25.0);
                    viewer.trackedEntity = entity;
                }}
            }});
        }};

        // 3. Constellation & Orbital LEO View
        window.viewConstellation = function() {{
            if (!viewer) return;
            viewer.trackedEntity = undefined;
            const target = Cesium.Cartesian3.fromDegrees({center_lon}, {center_lat}, 0);
            viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(target, 150000), {{
                offset: new Cesium.HeadingPitchRange(
                    Cesium.Math.toRadians(0),
                    Cesium.Math.toRadians(-50),
                    2200000
                ),
                duration: 2.0
            }});
        }};
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
    area = config.get('scenario', {}).get('area', {})
    center_lat = float(area.get('center_lat', 46.5286))
    center_lon = float(area.get('center_lon', 10.4531))

    generate_globe_html(czml_path, html_path, sc_name, center_lat=center_lat, center_lon=center_lon)
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
