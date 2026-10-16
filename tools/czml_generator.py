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
import bisect
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

def _geodetic_to_ecef_km(lon_deg: float, lat_deg: float, alt_m: float) -> Tuple[float, float, float]:
    """Geodetic (deg, deg, m) -> ECEF kilometres (spherical Earth, sufficient for link geometry)."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    r = R_EARTH_KM + alt_m / 1000.0
    return (
        r * math.cos(lat) * math.cos(lon),
        r * math.cos(lat) * math.sin(lon),
        r * math.sin(lat),
    )

def _enu_basis(lat_deg: float, lon_deg: float) -> Tuple[Tuple[float, float, float], ...]:
    """East/North/Up unit vectors (ECEF) of the local frame at (lat, lon)."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    east = (-math.sin(lon), math.cos(lon), 0.0)
    north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))
    up = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
    return east, north, up

C_KM_S = 299792.458  # speed of light

def compute_link_geometry(
    sat_positions: Dict[Any, Any],
    vehicle_paths: Dict[int, List[Any]],
    time_samples: List[float],
    carrier_ghz: float,
    veh_count: int = 6
) -> Optional[Dict[str, Any]]:
    """Ephemeris-derived link geometry between the convoy and the constellation.

    For every time sample the geometrically best satellite (maximum elevation
    above the local horizon) is selected per vehicle, and its elevation angle,
    slant range and Doppler shift are computed from the actual propagated
    coordinates. This is real orbital geometry, not synthesized telemetry:
    the same numbers a link-budget model would consume at that instant.
    """
    if not sat_positions or not time_samples:
        return None

    # Pre-compute satellite ECEF tracks aligned with time_samples
    sat_tracks: List[Tuple[str, List[Tuple[float, float, float]]]] = []
    for (p, s), (sat_id, positions) in sat_positions.items():
        ecef_track = [
            _geodetic_to_ecef_km(lon, lat, alt_m) for (lon, lat, alt_m) in positions[: len(time_samples)]
        ]
        if len(ecef_track) == len(time_samples):
            sat_tracks.append((sat_id, ecef_track))

    if not sat_tracks:
        return None

    leader = {"server": [], "elevation_deg": [], "slant_km": [], "doppler_khz": []}
    beams: Dict[str, List[str]] = {}

    for v_idx in range(max(1, veh_count)):
        flat = vehicle_paths.get(v_idx) or vehicle_paths.get(0) or []
        if len(flat) < 4 * len(time_samples):
            continue
        veh_ecef = [
            _geodetic_to_ecef_km(flat[4 * i + 1], flat[4 * i + 2], flat[4 * i + 3])
            for i in range(len(time_samples))
        ]
        server_ids: List[str] = []
        elevations: List[float] = []
        slants: List[float] = []
        dopplers: List[float] = []
        track_lookup = {sat_id: track for sat_id, track in sat_tracks}

        def _slant_at(track: List[Tuple[float, float, float]], idx: int, veh: Tuple[float, float, float]) -> float:
            sx, sy, sz = track[idx]
            return math.sqrt((sx - veh[0]) ** 2 + (sy - veh[1]) ** 2 + (sz - veh[2]) ** 2)

        for i, t in enumerate(time_samples):
            vx, vy, vz = veh_ecef[i]
            v_lon = flat[4 * i + 1]
            v_lat = flat[4 * i + 2]
            east, north, up = _enu_basis(v_lat, v_lon)

            best_sat = None
            best_elev = -90.0
            best_slant = 0.0
            best_visible_sat = None
            best_visible_elev = -90.0
            best_visible_slant = 0.0

            for sat_id, track in sat_tracks:
                sx, sy, sz = track[i]
                dx, dy, dz = sx - vx, sy - vy, sz - vz
                slant = math.sqrt(dx * dx + dy * dy + dz * dz)
                up_c = dx * up[0] + dy * up[1] + dz * up[2]
                east_c = dx * east[0] + dy * east[1] + dz * east[2]
                north_c = dx * north[0] + dy * north[1] + dz * north[2]
                horiz = math.sqrt(east_c * east_c + north_c * north_c)
                elev = math.degrees(math.atan2(up_c, max(1.0e-9, horiz)))
                if elev > best_elev:
                    best_elev = elev
                    best_sat = sat_id
                    best_slant = slant
                if elev >= 0.0 and elev > best_visible_elev:
                    best_visible_elev = elev
                    best_visible_sat = sat_id
                    best_visible_slant = slant

            # Prefer a satellite above the local horizon; degrade gracefully
            # to the least-bad candidate when the constellation is sparse.
            if best_visible_sat is not None:
                best_sat = best_visible_sat
                best_elev = best_visible_elev
                best_slant = best_visible_slant

            if best_sat is None:
                continue

            # Radial velocity via central difference of the slant range to the
            # selected satellite (each sample uses its own vehicle position)
            track = track_lookup[best_sat]
            i_prev = max(0, i - 1)
            i_next = min(len(time_samples) - 1, i + 1)
            dt = time_samples[i_next] - time_samples[i_prev]
            if dt <= 1.0e-6:
                dt = 1.0
            r_prev = _slant_at(track, i_prev, veh_ecef[i_prev])
            r_next = _slant_at(track, i_next, veh_ecef[i_next])
            v_radial_km_s = (r_next - r_prev) / dt

            server_ids.append(best_sat)
            elevations.append(round(best_elev, 2))
            slants.append(round(best_slant, 2))
            dopplers.append(round(-v_radial_km_s * carrier_ghz / C_KM_S * 1.0e6, 2))

        if server_ids:
            beams[str(v_idx)] = server_ids
            if v_idx == 0:
                leader = {
                    "server": server_ids,
                    "elevation_deg": elevations,
                    "slant_km": slants,
                    "doppler_khz": dopplers,
                }

    if not beams:
        return None

    return {
        "times_s": time_samples,
        "carrier_ghz": carrier_ghz,
        "leader": leader,
        "beams": beams,
    }

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
                        # Fast O(log N) lookup using bisect
                        idx = bisect.bisect_left(sorted_times, t)
                        if idx == 0:
                            closest_t = sorted_times[0]
                        elif idx >= len(sorted_times):
                            closest_t = sorted_times[-1]
                        else:
                            t_prev = sorted_times[idx - 1]
                            t_curr = sorted_times[idx]
                            closest_t = t_prev if (t - t_prev) <= (t_curr - t) else t_curr
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

def load_vehicle_rat_map(results_dir: Path) -> Dict[int, str]:
    """Per-vehicle dominant link state recorded by the run.

    Source precedence matches the Studio: newest ``*.vec`` first, then the
    ``exported_vectors.csv`` export (``activeInterface`` -> last sample,
    ``>= 0.5`` means LEO). When those vectors were not recorded, falls back to
    the per-node ``activeInterface:last`` scalar statistic emitted by the
    hybrid manager (finite values only — aborted runs record ``nan``).
    Vehicles with no recorded link state at all are absent from the map and
    the 3D view renders them neutral slate — the state is never guessed.
    """
    if not results_dir.exists():
        return {}
    try:
        try:
            from tools.dashboard import parse_vector_file, parse_csv_file, parse_scalar_rat_map
        except ImportError:
            from dashboard import parse_vector_file, parse_csv_file, parse_scalar_rat_map  # type: ignore
    except ImportError:
        return {}

    source: Optional[Path] = None
    vec_files = [p for p in results_dir.glob('*.vec') if p.is_file()]
    if vec_files:
        source = max(vec_files, key=lambda p: p.stat().st_mtime)
    else:
        csv_files = [p for p in results_dir.glob('*.csv') if 'vector' in p.name.lower()]
        if csv_files:
            source = max(csv_files, key=lambda p: p.stat().st_mtime)

    rat_map: Dict[int, str] = {}
    if source is not None:
        try:
            structured = (
                parse_vector_file(source) if source.suffix == '.vec' else parse_csv_file(source)
            )
        except Exception:
            structured = {}
        for node_label, metrics in structured.items():
            entry = metrics.get('activeInterface') or {}
            ys = entry.get('y') or []
            if not ys:
                continue
            last = float(ys[-1])
            parts = node_label.split()
            if len(parts) >= 2 and parts[1].isdigit():
                rat_map[int(parts[1])] = 'LEO' if last >= 0.5 else '5G'

    if not rat_map:
        # Fallback: dominant link from the recorded hybridManager scalars
        sca_files = [p for p in results_dir.glob('*.sca') if p.is_file()]
        if sca_files:
            try:
                rat_map = parse_scalar_rat_map(max(sca_files, key=lambda p: p.stat().st_mtime))
            except Exception:
                rat_map = {}
    return rat_map


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

    # Dynamic adaptive time step based on duration and constellation size
    total_sats = sum(int(s.get('num_planes', 1)) * int(s.get('sats_per_plane', 1)) for s in shells)
    if total_sats > 100 or duration > 3600:
        time_step = max(time_step, 15.0)
    elif total_sats > 40 and duration > 600:
        time_step = max(time_step, 10.0)

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
                        "font": "10px sans-serif",
                        "fillColor": { "rgba": [248, 250, 252, 230] },
                        "outlineColor": { "rgba": [15, 23, 42, 255] },
                        "outlineWidth": 2,
                        "pixelOffset": { "cartesian2": [0, -16] },
                        "distanceDisplayCondition": { "distanceDisplayCondition": [0, 600000] }
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
                                    "color": { "rgba": [56, 189, 248, 130] },
                                    "glowPower": 0.15,
                                    "taperPower": 1.0
                                }
                            },
                            "width": 1.2
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
            }
        })

        # Volumetric 5G coverage lobe: an upward-tapering cone whose base
        # matches the cell footprint radius on the ground; tall enough to be
        # readable as an antenna lobe without dwarfing the terrain scene.
        lobe_len = max(150.0, radius * 0.7)
        czml.append({
            "id": f"gnb_lobe_{idx}",
            "name": f"5G Coverage Lobe: {g_name}",
            "position": {
                "cartographicDegrees": [lon, lat, lobe_len / 2.0]
            },
            "cylinder": {
                "length": lobe_len,
                "topRadius": radius * 0.08,
                "bottomRadius": radius,
                "material": {
                    "solidColor": {
                        "color": { "rgba": [16, 185, 129, 30] }
                    }
                },
                "outline": True,
                "outlineColor": { "rgba": [16, 185, 129, 80] },
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
                "color": { "rgba": [251, 146, 60, 255] },
                "pixelSize": 11,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2,
                "heightReference": "CLAMP_TO_GROUND"
            },
            "label": {
                "text": f"Gateway: {gs_name}",
                "font": "12px sans-serif",
                "fillColor": { "rgba": [251, 146, 60, 255] },
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

    # Per-vehicle RAT colours from the recorded activeInterface vectors (the
    # 3D view then matches the Studio fleet table / 2D map exactly). Vehicles
    # without recorded link state stay neutral slate.
    vehicle_rat_map = load_vehicle_rat_map(output_czml.parent)

    vehicle_path_samples: Dict[int, List[Any]] = {}
    for v_idx in range(min(ue_count, 6)):
        v_id = f"veh_{v_idx}"
        v_name = f"Vehicle {v_idx}" if v_idx > 0 else "Vehicle 0 (Convoy Leader)"

        v_rat = vehicle_rat_map.get(v_idx)
        if v_rat == '5G':
            v_rgba, v_path_rgba = [16, 185, 129, 255], [16, 185, 129, 150]
        elif v_rat == 'LEO':
            v_rgba, v_path_rgba = [56, 189, 248, 255], [56, 189, 248, 150]
        else:
            # Link state not recorded in this run -> neutral slate, never guessed
            v_rgba, v_path_rgba = [100, 116, 139, 255], [100, 116, 139, 130]

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

        vehicle_path_samples[v_idx] = veh_samples

        czml.append({
            "id": v_id,
            "name": v_name,
            "availability": f"{start_iso_clean}/{end_iso}",
            "position": {
                "epoch": start_iso_clean,
                "cartographicDegrees": veh_samples
            },
            "point": {
                "color": { "rgba": v_rgba },
                "pixelSize": 12,
                "outlineColor": { "rgba": [255, 255, 255, 255] },
                "outlineWidth": 2.5,
                "heightReference": "CLAMP_TO_GROUND"
            },
            "path": {
                "material": {
                    "solidColor": { "color": { "rgba": v_path_rgba } }
                },
                "width": 2.5,
                "leadTime": 0,
                "trailTime": 30
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

    # 5b. Ephemeris-derived link geometry + serving-satellite table.
    # The viewer builds pulsating volumetric phased-array ray cylinders from
    # this table; the cockpit HUD reads elevation/slant/Doppler from it.
    sat_carrier_ghz = 28.0
    for gs in const_cfg.get('ground_stations', []):
        if gs.get('frequency_ghz') is not None:
            sat_carrier_ghz = float(gs['frequency_ghz'])
            break
    link_geometry = compute_link_geometry(
        sat_positions=all_sat_positions,
        vehicle_paths=vehicle_path_samples,
        time_samples=time_samples,
        carrier_ghz=sat_carrier_ghz,
        veh_count=min(ue_count, 6)
    )
    if link_geometry is not None:
        link_geometry["elevation_mask_deg"] = float(area_cfg.get('elevation_mask_deg', 25.0))
        czml.append({
            "id": "nexasim_link_geometry",
            "name": "NexaSim Ephemeris-Derived Link Geometry",
            "nexasim": link_geometry
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
    """Creates a photorealistic CesiumJS 3D Earth Globe viewer HTML page with
    a bi-directional postMessage bridge to NexaSim Studio and an aerospace HUD."""
    cesium_token = '__CESIUM_ION_TOKEN__'
    carto_param = '?key=__CARTO_API_KEY__'
    with open(czml_path, 'r', encoding='utf-8') as f:
        czml_data = json.load(f)

    # The link-geometry packet is generator metadata, not a CZML entity:
    # extract it for the HUD / beam renderer and keep it away from Cesium.
    link_geometry = None
    filtered_czml = []
    for packet in czml_data:
        if isinstance(packet, dict) and packet.get('id') == 'nexasim_link_geometry':
            link_geometry = packet.get('nexasim')
        else:
            filtered_czml.append(packet)
    czml_data = filtered_czml
    link_geometry_js = json.dumps(link_geometry) if link_geometry else 'null'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaSim 3D Space-Ground Digital Twin | {scenario_name}</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- CesiumJS Official CDN -->
    <script src="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Cesium.js"></script>
    <link href="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
    <style>
        html, body, #cesiumContainer {{
            width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden;
            background-color: #030712; font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
            -webkit-font-smoothing: antialiased;
        }}
        .hud-panel {{
            position: absolute;
            top: 14px;
            left: 14px;
            background: rgba(11, 17, 24, 0.94);
            border: 1px solid #1c2838;
            border-top: 3px solid #38bdf8;
            border-radius: 6px;
            padding: 12px 14px;
            color: #f8fafc;
            backdrop-filter: blur(12px);
            z-index: 999;
            width: 330px;
            box-shadow: 0 12px 28px rgba(0,0,0,0.6);
            transition: all 0.2s ease;
        }}
        .hud-panel.collapsed .hud-body {{ display: none; }}
        .hud-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .hud-title {{
            font-size: 13px;
            font-weight: 700;
            color: #38bdf8;
            letter-spacing: -0.1px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .hud-badge {{
            font-size: 10px;
            font-weight: 700;
            font-family: 'IBM Plex Mono', monospace;
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 1px 6px;
            border-radius: 3px;
        }}
        .hud-toggle-btn {{
            background: transparent;
            border: 1px solid #1c2838;
            color: #94a3b8;
            border-radius: 3px;
            padding: 1px 6px;
            font-size: 11px;
            cursor: pointer;
            font-family: monospace;
            margin-left: 6px;
        }}
        .hud-toggle-btn:hover {{ color: #f8fafc; border-color: #38bdf8; }}
        .hud-scenario {{
            font-size: 11px;
            color: #94a3b8;
            margin-bottom: 10px;
            font-family: 'IBM Plex Mono', monospace;
        }}
        .telemetry-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            background: rgba(19, 28, 40, 0.6);
            border: 1px solid #1c2838;
            border-radius: 4px;
            padding: 8px 10px;
            margin-bottom: 10px;
        }}
        .telem-item {{ display: flex; flex-direction: column; }}
        .telem-label {{ font-size: 9px; color: #64748b; text-transform: uppercase; font-weight: 700; font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.5px; }}
        .telem-val {{ font-size: 13px; font-weight: 700; color: #f8fafc; font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }}
        .telem-val.warn {{ color: #f59e0b; }}
        .telem-val.caution {{ color: #ef4444; }}

        .cam-controls {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            margin-top: 6px;
        }}
        .layer-controls {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            margin-top: 6px;
        }}
        .hud-btn {{
            background: #131c28;
            border: 1px solid #1c2838;
            color: #f8fafc;
            padding: 6px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
        }}
        .hud-btn:hover {{
            background: #1a2636;
            border-color: #38bdf8;
            color: #38bdf8;
        }}
        .hud-btn.active {{ background: rgba(56,189,248,0.15); border-color: #38bdf8; color: #38bdf8; }}
        .basemap-select {{
            width: 100%;
            background: #131c28;
            border: 1px solid #1c2838;
            color: #f8fafc;
            padding: 6px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-family: inherit;
            margin-top: 8px;
            outline: none;
            cursor: pointer;
        }}
        .basemap-select:focus {{ border-color: #38bdf8; }}
        .legend {{
            margin-top: 10px;
            font-size: 10px;
            color: #94a3b8;
            font-family: 'IBM Plex Mono', monospace;
            border-top: 1px solid #1c2838;
            padding-top: 8px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}

        /* Link status indicator */
        .link-status {{
            margin-top: 10px;
            font-size: 10px;
            font-family: 'IBM Plex Mono', monospace;
            padding: 6px 8px;
            background: rgba(19, 28, 40, 0.6);
            border: 1px solid #1c2838;
            border-radius: 4px;
            display: flex; align-items: center; gap: 6px;
        }}
        .link-dot {{ width: 6px; height: 6px; border-radius: 50%; background: #ef4444; box-shadow: 0 0 6px #ef4444; animation: pulse 2s infinite; }}
        .link-dot.online {{ background: #10b981; box-shadow: 0 0 6px #10b981; }}
        @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} 100% {{ opacity: 1; }} }}

        /* Dark-theme the stock Cesium widgets (timeline / animation / infoBox) */
        .cesium-viewer .cesium-button {{
            background-color: #131c28;
            color: #e2e8f0;
            border: 1px solid #1c2838;
            fill: #e2e8f0;
        }}
        .cesium-viewer .cesium-button:hover {{
            background-color: #1a2636;
            color: #38bdf8;
            fill: #38bdf8;
        }}
        .cesium-viewer-animationContainer, .cesium-viewer-timelineContainer {{
            background: rgba(11, 17, 24, 0.88);
        }}
        .cesium-viewer-bottom {{ background: transparent; }}
        .cesium-timeline-main {{ border-color: #1c2838; }}
        .cesium-timeline-trackContainer {{ border-top-color: #1c2838; }}
        .cesium-timeline-ticLabel {{ color: #94a3b8; font-family: 'IBM Plex Mono', monospace; font-size: 10px; }}
        .cesium-timeline-ticMain {{ background: #475569; }}
        .cesium-timeline-ticSub {{ background: #334155; }}
        .cesium-timeline-ticTiny {{ background: #293548; }}
        .cesium-timeline-icon {{ fill: #94a3b8; }}
        .cesium-timeline-needle {{ background: #38bdf8; }}
        .cesium-infoBox {{
            background: rgba(11, 17, 24, 0.96);
            border: 1px solid #27374d;
            color: #e2e8f0;
        }}
        .cesium-infoBox-title {{ background: #0f1620; color: #f8fafc; }}
        .cesium-infoBox-description {{ color: #cbd5e1; }}
        .cesium-infoBox-close {{ background: #1c2838; color: #e2e8f0; }}
        .cesium-selection-wrapper svg {{ fill: #38bdf8; }}
    </style>
</head>
<body>
    <div id="cesiumContainer"></div>

    <div class="hud-panel" id="hudPanel">
        <div class="hud-header">
            <span class="hud-title">🛰️ 3D Digital Twin</span>
            <div>
                <span class="hud-badge">NexaSphere</span>
                <button class="hud-toggle-btn" id="hudToggleBtn" onclick="toggleHud()" title="Collapse / Expand HUD">—</button>
            </div>
        </div>
        <div class="hud-body" id="hudBody">
            <div class="hud-scenario">Scenario: <strong>{scenario_name}</strong></div>

            <!-- Studio sync status -->
            <div class="link-status">
                <span class="link-dot" id="linkDot"></span>
                <span id="linkText" style="font-size:10px; color:#94a3b8;">Studio Link: <strong id="linkStatusText">INIT</strong></span>
            </div>

            <!-- Cockpit Telemetry (values filled from real telemetry / ephemeris; "—" = not recorded) -->
            <div class="telemetry-grid">
                <div class="telem-item">
                    <span class="telem-label">Active RAT</span>
                    <span class="telem-val" id="telemRat" style="color: #38bdf8;">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">Overhead Sat</span>
                    <span class="telem-val" id="telemSat">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">Vehicle Speed</span>
                    <span class="telem-val" id="telemSpeed">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">MEC Latency</span>
                    <span class="telem-val" id="telemLatency" style="color: #ec4899;">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">Elevation (Zenith)</span>
                    <span class="telem-val" id="telemElev">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">Slant Range</span>
                    <span class="telem-val" id="telemRange">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">Doppler Shift</span>
                    <span class="telem-val" id="telemDoppler" class="warn">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">Carrier Freq</span>
                    <span class="telem-val" id="telemCarrier">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">QoS Score</span>
                    <span class="telem-val" id="telemQos">—</span>
                </div>
                <div class="telem-item">
                    <span class="telem-label">Battery SoC</span>
                    <span class="telem-val" id="telemBatt">—</span>
                </div>
            </div>

            <div style="font-size: 10px; color: #64748b; font-weight: 700; text-transform: uppercase; font-family:'IBM Plex Mono', monospace; letter-spacing:0.5px;">Camera View Presets</div>
            <div class="cam-controls">
                <button class="hud-btn" onclick="viewTactical()">🎯 Tactical</button>
                <button class="hud-btn" onclick="viewVehicle()">🏎️ Chase</button>
                <button class="hud-btn" onclick="viewConstellation()">🛰️ Orbit</button>
            </div>

            <div style="font-size: 10px; color: #64748b; font-weight: 700; text-transform: uppercase; font-family:'IBM Plex Mono', monospace; letter-spacing:0.5px;">Layer Controls</div>
            <div class="layer-controls">
                <button class="hud-btn active" id="btnLayerIsl" onclick="toggleLayer('isl')" title="Inter-satellite laser links (dimmed mesh)">ISL</button>
                <button class="hud-btn active" id="btnLayerLobes" onclick="toggleLayer('lobes')" title="Volumetric 5G cell coverage lobes">Lobes</button>
                <button class="hud-btn active" id="btnLayerFootprints" onclick="toggleLayer('footprints')" title="Coverage footprint of the serving satellite only (auto)">Footprints</button>
            </div>

            <select class="basemap-select" onchange="switchBasemap(this.value)">
                <option value="default">🗺️ Cesium Ion Satellite</option>
                <option value="esri">🗺️ ESRI World Satellite HD</option>
                <option value="osm">🗺️ OpenStreetMap Standard</option>
                <option value="carto">🗺️ CartoDB Dark Canvas</option>
            </select>

            <div class="legend">
                <div class="legend-item"><span class="dot" style="background:#38bdf8;"></span> LEO sat / ISL / beam</div>
                <div class="legend-item"><span class="dot" style="background:#10b981;"></span> 5G-NR gNodeB</div>
                <div class="legend-item"><span class="dot" style="background:#fb923c;"></span> Ground gateway</div>
                <div class="legend-item"><span class="dot" style="background:#10b981;"></span> Vehicle — 5G link</div>
                <div class="legend-item"><span class="dot" style="background:#38bdf8;"></span> Vehicle — LEO link</div>
                <div class="legend-item"><span class="dot" style="background:#64748b;"></span> Vehicle — link n/r</div>
            </div>
        </div>
    </div>

    <script>
        const token = '{cesium_token}';
        if (token) {{
            Cesium.Ion.defaultAccessToken = token;
        }}

        let viewer;
        let dataSourcePromise = null;
        let studioLinked = false;
        let studioPlayback = false;
        let studioSpeed = 1.0;
        let studioSimTime = 0.0;
        let studioHud = null;

        // Ephemeris-derived link geometry (best satellite, elevation, slant
        // range, Doppler) computed by the Python generator from the actual
        // propagated constellation — never synthesized in the browser.
        const linkGeometry = {link_geometry_js};

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
                timeline: true,
                clock: new Cesium.Clock({{ shouldAnimate: false }})
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
                timeline: true,
                clock: new Cesium.Clock({{ shouldAnimate: false }})
            }});
        }}

        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.depthTestAgainstTerrain = true;

        // Metric scale bar (bottom of the screen). The ScaleBar API differs
        // slightly across Cesium builds — degrade gracefully if unavailable.
        try {{
            viewer.scaleBar = new Cesium.ScaleBar(viewer.bottomContainer);
        }} catch (scaleErr) {{
            try {{
                viewer.scaleBar = new Cesium.ScaleBar({{ container: viewer.bottomContainer }});
            }} catch (scaleErr2) {{
                console.warn('Cesium ScaleBar unavailable:', scaleErr2);
            }}
        }}

        const czmlPayload = {json.dumps(czml_data)};
        try {{
            dataSourcePromise = viewer.dataSources.add(Cesium.CzmlDataSource.load(czmlPayload));
            dataSourcePromise.then(function(dataSource) {{
                viewer.clock.multiplier = studioSpeed;
                if (typeof window.viewTactical === 'function') {{
                    window.viewTactical();
                }}
                // Build the pulsating volumetric phased-array ray cylinders
                // from the ephemeris-derived serving-satellite table.
                createBeamRays(dataSource);
                updateHudTelemetry(currentStudioSeconds());
                // Prime the serving-satellite highlight + footprint declutter
                updateServingHighlight(currentStudioSeconds());
                updateFootprintFocus(true);
                // Signal readiness to Studio
                notifyStudio({{ action: 'GLOBE_READY' }});
            }}).catch(function(e) {{
                console.error("CZML Load Error:", e);
                notifyStudio({{ action: 'GLOBE_READY' }});
            }});
        }} catch (err) {{
            console.error("Failed to load CZML payload:", err);
            notifyStudio({{ action: 'GLOBE_READY' }});
        }}

        // ---------------------------------------------------------------
        // Studio <-> Cesium postMessage bridge
        // ---------------------------------------------------------------
        function notifyStudio(payload) {{
            try {{
                if (window.parent && window.parent !== window) {{
                    window.parent.postMessage(payload, '*');
                }}
            }} catch (e) {{
                console.warn('postMessage to studio failed:', e);
            }}
        }}

        function updateLinkStatus(online) {{
            studioLinked = online;
            const dot = document.getElementById('linkDot');
            const txt = document.getElementById('linkStatusText');
            if (dot) dot.className = 'link-dot' + (online ? ' online' : '');
            if (txt) txt.textContent = online ? 'LINKED' : 'STANDALONE';
        }}

        // Track which entity layers are visible
        const layerVisibility = {{ isl: true, lobes: true, footprints: true }};

        function toggleLayer(layer, visible) {{
            // `visible` (boolean) makes the command idempotent; toggling is the fallback
            layerVisibility[layer] = (typeof visible === 'boolean') ? visible : !layerVisibility[layer];
            const btn = document.getElementById('btnLayer' + layer.charAt(0).toUpperCase() + layer.slice(1));
            if (btn) btn.classList.toggle('active', layerVisibility[layer]);
            if (layer === 'footprints') {{
                // Decluttered mode: while enabled only the serving satellite's
                // footprint is drawn (auto-tracked from the ephemeris table).
                updateFootprintFocus(true);
                return;
            }}
            if (!dataSourcePromise) return;
            dataSourcePromise.then(function(dataSource) {{
                const entities = dataSource.entities.values;
                entities.forEach(function(entity) {{
                    const id = entity.id || '';
                    let show = null;
                    if (layer === 'isl' && id.startsWith('isl_')) show = layerVisibility.isl;
                    if (layer === 'lobes' && id.startsWith('gnb_lobe_')) show = layerVisibility.lobes;
                    if (show === null) return;
                    if (entity.isShowing !== undefined) {{
                        try {{ entity.show = show; }} catch {{}}
                    }}
                    if (entity.polyline && entity.polyline.show !== undefined) {{ entity.polyline.show = show; }}
                    if (entity.cylinder && entity.cylinder.show !== undefined) {{ entity.cylinder.show = show; }}
                    if (entity.ellipse && entity.ellipse.show !== undefined) {{ entity.ellipse.show = show; }}
                }});
            }});
        }}

        // ---------------------------------------------------------------
        // Serving-satellite declutter (ephemeris-derived, not synthesized)
        //  - only the serving satellite of the convoy leader is highlighted
        //  - only its ground footprint is drawn while "Footprints" is on
        // ---------------------------------------------------------------
        let currentServingSatId = null;
        let currentServingFootprintId = null;

        function leaderServingIdAt(seconds) {{
            const idx = geometryIndexAt(seconds);
            if (idx < 0 || !linkGeometry || !linkGeometry.leader) return null;
            return linkGeometry.leader.server[idx] || null;
        }}

        function updateFootprintFocus(force) {{
            if (!dataSourcePromise) return;
            const serverId = leaderServingIdAt(currentStudioSeconds());
            const newFootprintId = serverId ? serverId + '_footprint' : null;
            if (!force && newFootprintId === currentServingFootprintId) return;
            currentServingFootprintId = newFootprintId;
            dataSourcePromise.then(function(dataSource) {{
                dataSource.entities.values.forEach(function(entity) {{
                    const id = entity.id || '';
                    if (!id.endsWith('_footprint')) return;
                    const show = layerVisibility.footprints && id === currentServingFootprintId;
                    try {{ entity.show = show; }} catch (e) {{}}
                    if (entity.ellipse && entity.ellipse.show !== undefined) {{ entity.ellipse.show = show; }}
                }});
            }});
        }}

        function updateServingHighlight(seconds) {{
            if (!dataSourcePromise) return;
            const serverId = leaderServingIdAt(seconds);
            if (serverId === currentServingSatId) return;
            currentServingSatId = serverId;
            const cyan = Cesium.Color.fromCssColorString('#38bdf8');
            const white = Cesium.Color.WHITE;
            const softWhite = Cesium.Color.fromCssColorString('rgba(255,255,255,0.86)');
            dataSourcePromise.then(function(dataSource) {{
                dataSource.entities.values.forEach(function(entity) {{
                    const id = entity.id || '';
                    if (!id.startsWith('sat_') || !entity.point) return;
                    if (id === currentServingSatId) {{
                        entity.point.pixelSize = new Cesium.ConstantProperty(13);
                        entity.point.color = new Cesium.ConstantProperty(white);
                        entity.point.outlineColor = new Cesium.ConstantProperty(cyan);
                        entity.point.outlineWidth = new Cesium.ConstantProperty(3);
                    }} else {{
                        entity.point.pixelSize = new Cesium.ConstantProperty(7);
                        entity.point.color = new Cesium.ConstantProperty(cyan);
                        entity.point.outlineColor = new Cesium.ConstantProperty(softWhite);
                        entity.point.outlineWidth = new Cesium.ConstantProperty(2);
                    }}
                }});
            }});
        }}

        // Set the Cesium clock from a studio simTime (seconds since scenario start)
        function setCesiumClockFromSimTime(simSeconds) {{
            if (!viewer) return;
            const start = viewer.clock.startTime;
            if (!start) return;
            const target = Cesium.JulianDate.addSeconds(start, simSeconds, new Cesium.JulianDate());
            viewer.clock.currentTime = target;
            // Animate the timeline to the new time
            try {{
                viewer.timeline?.tick?.();
            }} catch {{}}
        }}

        function seekStudioTime(simSeconds) {{
            studioSimTime = simSeconds;
            setCesiumClockFromSimTime(simSeconds);
        }}

        function currentStudioSeconds() {{
            if (!viewer || !viewer.clock || !viewer.clock.startTime) return 0.0;
            try {{
                const sec = Cesium.JulianDate.secondsDifference(viewer.clock.currentTime, viewer.clock.startTime);
                return Math.max(0.0, sec);
            }} catch (e) {{
                return 0.0;
            }}
        }}

        // Index of the geometry sample closest to (but not after) `seconds`
        function geometryIndexAt(seconds) {{
            if (!linkGeometry || !linkGeometry.times_s || !linkGeometry.times_s.length) return -1;
            const times = linkGeometry.times_s;
            if (seconds <= times[0]) return 0;
            if (seconds >= times[times.length - 1]) return times.length - 1;
            let lo = 0;
            let hi = times.length - 1;
            while (hi - lo > 1) {{
                const mid = (lo + hi) >> 1;
                if (times[mid] <= seconds) lo = mid; else hi = mid;
            }}
            return lo;
        }}

        // ---------------------------------------------------------------
        // Pulsating volumetric phased-array ray cylinders
        // ---------------------------------------------------------------
        const beamEntities = [];

        function beamPulse(time) {{
            const period = 1.6;
            const sec = currentStudioSeconds();
            return (sec % period) / period; // 0..1
        }}

        function createBeamRays(dataSource) {{
            if (!linkGeometry || !linkGeometry.beams) return;
            Object.keys(linkGeometry.beams).forEach(function(vKey) {{
                const vehEntity = dataSource.entities.getById('veh_' + vKey);
                if (!vehEntity || !vehEntity.position) return;
                const servingIds = linkGeometry.beams[vKey];
                if (!servingIds || !servingIds.length) return;

                const startScratch = new Cesium.Cartesian3();
                const endScratch = new Cesium.Cartesian3();
                const midScratch = new Cesium.Cartesian3();
                const dirScratch = new Cesium.Cartesian3();
                const axisScratch = new Cesium.Cartesian3();
                const quatScratch = new Cesium.Quaternion();

                function bestSatEntity(seconds) {{
                    const idx = geometryIndexAt(seconds);
                    if (idx < 0) return null;
                    const satId = servingIds[Math.min(idx, servingIds.length - 1)];
                    return satId ? dataSource.entities.getById(satId) : null;
                }}

                function resolveEndpoints(time) {{
                    const satEntity = bestSatEntity(currentStudioSeconds());
                    if (!satEntity || !satEntity.position) return false;
                    const a = vehEntity.position.getValue(time, startScratch);
                    const b = satEntity.position.getValue(time, endScratch);
                    return Cesium.defined(a) && Cesium.defined(b);
                }}

                const beamEntity = dataSource.entities.add({{
                    id: 'beam_ray_' + vKey,
                    name: 'Phased-Array Ray (veh_' + vKey + ')',
                    position: new Cesium.CallbackProperty(function(time, result) {{
                        if (!resolveEndpoints(time)) return undefined;
                        return Cesium.Cartesian3.midpoint(startScratch, endScratch, result || midScratch);
                    }}, false),
                    orientation: new Cesium.CallbackProperty(function(time, result) {{
                        if (!resolveEndpoints(time)) return undefined;
                        const dir = Cesium.Cartesian3.normalize(
                            Cesium.Cartesian3.subtract(endScratch, startScratch, dirScratch), dirScratch);
                        const dot = Math.max(-1, Math.min(1, Cesium.Cartesian3.dot(Cesium.Cartesian3.UNIT_Z, dir)));
                        const angle = Math.acos(dot);
                        let axis = Cesium.Cartesian3.UNIT_X;
                        if (angle > 1.0e-6) {{
                            axis = Cesium.Cartesian3.normalize(
                                Cesium.Cartesian3.cross(Cesium.Cartesian3.UNIT_Z, dir, axisScratch), axisScratch);
                        }}
                        return Cesium.Quaternion.fromAxisAngle(axis, angle, result || quatScratch);
                    }}, false),
                    cylinder: {{
                        length: new Cesium.CallbackProperty(function(time) {{
                            if (!resolveEndpoints(time)) return 0.0;
                            return Cesium.Cartesian3.distance(startScratch, endScratch);
                        }}, false),
                        topRadius: new Cesium.CallbackProperty(function(time) {{
                            return 2600.0 * (0.72 + 0.40 * Math.sin(beamPulse(time) * Math.PI));
                        }}, false),
                        bottomRadius: new Cesium.CallbackProperty(function(time) {{
                            return 1400.0 * (0.72 + 0.40 * Math.sin(beamPulse(time) * Math.PI));
                        }}, false),
                        material: new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty(function(time) {{
                            const alpha = 0.10 + 0.12 * Math.sin(beamPulse(time) * Math.PI);
                            // Cyan beam — matches the space-segment colour language
                            return new Cesium.Color(0.22, 0.74, 0.97, alpha);
                        }}, false)),
                        outline: false,
                        slices: 12
                    }}
                }});
                beamEntities.push(beamEntity);
            }});
        }}

        // Live per-vehicle RAT colours forwarded by Studio — keeps the 3D
        // view colour-consistent with the 2D map (green 5G / cyan LEO /
        // purple V2X / slate when the link state was not recorded).
        function applyVehicleStates(list) {{
            if (!list || !list.length || !dataSourcePromise) return;
            dataSourcePromise.then(function(dataSource) {{
                list.forEach(function(v) {{
                    const entity = dataSource.entities.getById('veh_' + v.id);
                    if (!entity) return;
                    const css = v.rat === '5G' ? '#10b981'
                        : v.rat === 'LEO' ? '#38bdf8'
                        : v.rat === 'V2X' ? '#a855f7'
                        : '#64748b';
                    const color = Cesium.Color.fromCssColorString(css);
                    if (entity.point) {{
                        entity.point.color = new Cesium.ConstantProperty(color);
                    }}
                    if (entity.path) {{
                        entity.path.material = new Cesium.ColorMaterialProperty(color.withAlpha(0.55));
                    }}
                }});
            }});
        }}

        function handleStudioCommand(cmd) {{
            const action = cmd.action;
            if (action === 'PLAY') {{
                studioPlayback = true;
                viewer.clock.shouldAnimate = true;
                notifyStudio({{ action: 'VIEWER_TIME', time: currentStudioSeconds() }});
            }} else if (action === 'PAUSE') {{
                studioPlayback = false;
                viewer.clock.shouldAnimate = false;
                notifyStudio({{ action: 'VIEWER_TIME', time: currentStudioSeconds() }});
            }} else if (action === 'SEEK') {{
                // Time lock: move the clock without touching the play state
                seekStudioTime(cmd.simTime);
            }} else if (action === 'SET_SPEED') {{
                studioSpeed = cmd.multiplier || 1.0;
                viewer.clock.multiplier = studioSpeed;
                if (studioPlayback) viewer.clock.shouldAnimate = true;
            }} else if (action === 'HUD_UPDATE') {{
                // Real per-vehicle telemetry forwarded by NexaSim Studio
                studioHud = cmd.vehicle || null;
                updateHudTelemetry(currentStudioSeconds());
            }} else if (action === 'VEHICLE_STATE') {{
                // Recorded per-vehicle RAT colours (2D <-> 3D consistency)
                applyVehicleStates(cmd.vehicles);
            }} else if (action === 'TRACK_NODE') {{
                const id = cmd.id;
                if (!id || !dataSourcePromise) return;
                dataSourcePromise.then(function(dataSource) {{
                    const entity = dataSource.entities.getById(id);
                    if (entity) {{
                        viewer.trackedEntity = entity;
                        viewer.clock.shouldAnimate = studioPlayback;
                    }}
                }});
            }} else if (action === 'RESET_CAMERA') {{
                viewer.trackedEntity = undefined;
                if (typeof window.viewTactical === 'function') window.viewTactical();
            }} else if (action === 'TOGGLE_LAYER') {{
                toggleLayer(cmd.layer, cmd.visible);
            }}
        }}

        window.addEventListener('message', function(e) {{
            if (!e.data) return;
            if (typeof e.data.showHud === 'boolean') {{
                const hud = document.querySelector('.hud-panel');
                if (hud) hud.style.display = e.data.showHud ? 'block' : 'none';
            }}
            if (e.data.action === 'syncCamera' && typeof e.data.lat === 'number' && typeof e.data.lon === 'number') {{
                if (viewer) {{
                    viewer.camera.flyTo({{
                        destination: Cesium.Cartesian3.fromDegrees(e.data.lon, e.data.lat, e.data.altitude || 6000),
                        duration: 0.5
                    }});
                }}
            }}
            // Commands from Studio
            if (e.data.action) {{
                updateLinkStatus(true);
                handleStudioCommand(e.data);
            }}
        }});

        // Heartbeat: tell Studio we are alive (in case Studio reconnects)
        setInterval(function() {{
            if (viewer && dataSourcePromise) {{
                notifyStudio({{ action: 'VIEWER_TIME', time: studioSimTime }});
            }}
        }}, 2000);

        window.toggleHud = function() {{
            const panel = document.getElementById('hudPanel');
            const btn = document.getElementById('hudToggleBtn');
            if (panel) {{
                panel.classList.toggle('collapsed');
                if (btn) btn.textContent = panel.classList.contains('collapsed') ? '＋' : '—';
            }}
        }};

        // ---------------------------------------------------------------
        // Clock synchronization: keep studioSimTime in step with Cesium
        // ---------------------------------------------------------------
        let lastSyncBroadcast = 0;
        viewer.clock.onTick.addEventListener(function(clock) {{
            try {{
                const sec = Cesium.JulianDate.secondsDifference(clock.currentTime, clock.startTime);
                studioSimTime = Math.max(0, sec);

                // Broadcast viewer time + refresh HUD at 4 Hz (not per frame)
                const nowMs = performance.now();
                if (nowMs - lastSyncBroadcast >= 250) {{
                    lastSyncBroadcast = nowMs;
                    notifyStudio({{ action: 'VIEWER_TIME', time: studioSimTime }});
                    updateHudTelemetry(sec);
                    // Declutter: follow the serving satellite (highlight + footprint)
                    updateFootprintFocus(false);
                    updateServingHighlight(sec);
                }}
            }} catch(tickErr) {{}}
        }});

        // ---------------------------------------------------------------
        // Camera feedback: broadcast camera pose to the Studio (throttled)
        // ---------------------------------------------------------------
        let lastCameraBroadcast = 0;
        viewer.camera.changed.addEventListener(function() {{
            const camNowMs = performance.now();
            if (camNowMs - lastCameraBroadcast < 500) return;
            lastCameraBroadcast = camNowMs;
            try {{
                const carto = viewer.camera.positionCartographic;
                notifyStudio({{
                    action: 'CAMERA_UPDATE',
                    lat: Cesium.Math.toDegrees(carto.latitude),
                    lon: Cesium.Math.toDegrees(carto.longitude),
                    altitude: carto.height,
                    heading: Cesium.Math.toDegrees(viewer.camera.heading),
                    pitch: Cesium.Math.toDegrees(viewer.camera.pitch)
                }});
            }} catch (camErr) {{}}
        }});

        // ---------------------------------------------------------------
        // Entity click -> notify Studio (select node in store)
        // ---------------------------------------------------------------
        let clickHandlerAttached = false;
        viewer.scene.screenSpaceEventHandler.setInputAction(function(click) {{
            if (!viewer || !dataSourcePromise) return;
            const pickedObject = viewer.scene.pick(click.position);
            if (!pickedObject || !pickedObject.id) return;
            const entity = pickedObject.id;
            const id = entity.id || '';
            if (id.startsWith('veh_') || id.startsWith('sat_') || id.startsWith('gnb_') || id.startsWith('gs_')) {{
                notifyStudio({{ action: 'NODE_CLICKED', nodeId: id }});
            }}
        }}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        // ---------------------------------------------------------------
        // Cockpit HUD telemetry
        //  - vehicle kinematics / QoS: real telemetry forwarded by Studio
        //    (HUD_UPDATE), "—" when the metric was not recorded
        //  - elevation / slant / Doppler: ephemeris-derived geometry table
        // ---------------------------------------------------------------
        function updateHudTelemetry(sec) {{
            const rEl = document.getElementById('telemRat');
            const sEl = document.getElementById('telemSpeed');
            const lEl = document.getElementById('telemLatency');
            const satEl = document.getElementById('telemSat');
            const elevEl = document.getElementById('telemElev');
            const rangeEl = document.getElementById('telemRange');
            const dopEl = document.getElementById('telemDoppler');
            const carEl = document.getElementById('telemCarrier');
            const qosEl = document.getElementById('telemQos');
            const battEl = document.getElementById('telemBatt');

            // --- Real per-vehicle telemetry forwarded by the Studio
            const hud = studioHud;
            const rat = hud && hud.active_rat ? hud.active_rat : null;

            if (rEl) {{
                rEl.textContent = rat === 'LEO' ? 'Satellite LEO' : rat === '5G' ? '5G-NR Terrestrial' : rat === 'V2X' ? 'V2X Sidelink' : '—';
                rEl.style.color = rat === 'LEO' ? '#38bdf8' : rat === '5G' ? '#10b981' : rat === 'V2X' ? '#a855f7' : '#94a3b8';
            }}
            if (sEl) sEl.textContent = hud && hud.speed_kmh != null ? hud.speed_kmh.toFixed(1) + ' km/h' : '—';
            if (lEl) lEl.textContent = hud && hud.mec_latency_ms != null ? hud.mec_latency_ms.toFixed(1) + ' ms' : '—';
            if (qosEl) qosEl.textContent = hud && hud.qos_score != null ? hud.qos_score.toFixed(3) : '—';
            if (battEl) battEl.textContent = hud && hud.battery_soc_pct != null ? hud.battery_soc_pct.toFixed(1) + '%' : '—';

            // --- Ephemeris-derived geometry of the serving satellite
            let elev = null, slant = null, doppler = null, serverId = null;
            const idx = geometryIndexAt(sec);
            if (idx >= 0 && linkGeometry && linkGeometry.leader) {{
                serverId = linkGeometry.leader.server[idx];
                elev = linkGeometry.leader.elevation_deg[idx];
                slant = linkGeometry.leader.slant_km[idx];
                doppler = linkGeometry.leader.doppler_khz[idx];
            }}
            if (satEl) {{
                if (serverId) {{
                    const parts = serverId.split('_');
                    satEl.textContent = (parts.length >= 3) ? ('Sat P' + parts[1] + ' S' + parts[2]) : serverId;
                }} else {{
                    satEl.textContent = '—';
                }}
            }}
            if (elevEl) {{
                if (elev != null) {{
                    const mask = (linkGeometry && linkGeometry.elevation_mask_deg) || 25.0;
                    elevEl.textContent = elev.toFixed(1) + '°' + (elev < mask ? ' (masked)' : '');
                    elevEl.className = 'telem-val' + (elev < mask ? ' caution' : '');
                }} else {{
                    elevEl.textContent = '—';
                    elevEl.className = 'telem-val';
                }}
            }}
            if (rangeEl) rangeEl.textContent = slant != null ? slant.toFixed(0) + ' km' : '—';
            if (dopEl) {{
                if (doppler != null) {{
                    dopEl.textContent = (doppler >= 0 ? '+' : '') + doppler.toFixed(2) + ' kHz';
                    dopEl.className = 'telem-val' + (Math.abs(doppler) > 300.0 ? ' warn' : '');
                }} else {{
                    dopEl.textContent = '—';
                    dopEl.className = 'telem-val';
                }}
            }}
            if (carEl) carEl.textContent = (linkGeometry && linkGeometry.carrier_ghz) ? linkGeometry.carrier_ghz.toFixed(1) + ' GHz' : '—';
        }}

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
    try:
        from tools.html_assets import externalize_html_assets
    except ImportError:
        from html_assets import externalize_html_assets

    html = externalize_html_assets(html, output_html, 'globe.css', 'globe.js')
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
