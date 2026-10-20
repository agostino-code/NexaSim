#!/usr/bin/env python3
"""
NexaSim Studio Next-Gen - Aerospace-Grade 2D/3D Control Center & Visual Scenario Builder
Horizon Europe NexaSphere Research Project

Features:
- Dual-Engine View: Interactive 2D Tactical Map (Leaflet) + 3D Space-Ground Globe (CesiumJS) with continuous draggable split
- Visual No-Code Editor: Point-and-click placement, drag-and-drop repositioning, and Inspector for 5G-NR gNodeBs, Gateways, Blind Spots
- Multi-Tab Lower Deck: Executive Dashboard, Fleet Multi-RAT Telemetry, Scenario Parameters, Terminal Stream
- Real-time WebSocket Log and Telemetry Streaming (/ws/logs, /ws/telemetry)
- In-Studio Simulation Runner with real-time log streaming and automatic results integration
- Powered by FastAPI for high performance and security
"""

import os
import sys
import json
import yaml
import bisect
import asyncio
import argparse
import statistics
import threading
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

try:
    import uvicorn
    from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("Error: FastAPI or Uvicorn not installed. Please install them or rebuild the Docker container.")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
LIBRARY_DIR = REPO_ROOT / 'scenarios' / 'library'
GENERATED_DIR = REPO_ROOT / 'scenarios' / 'generated'
STATIC_DIR = REPO_ROOT / 'tools' / 'static'
STUDIO_DIST_DIR = REPO_ROOT / 'studio' / 'dist'

# Application State
SIM_STATE = {
    "running": False,
    "run_id": None,
    "current_scenario": None,
    "started_at": None,
    "logs": [],
    "exit_code": None
}
SIM_LOCK = threading.Lock()
MAX_LOG_LINES = 2000

# WebSocket Telemetry & Log Broadcaster
class TelemetryBroadcaster:
    def __init__(self):
        self.log_clients: List[WebSocket] = []
        self.telemetry_clients: List[WebSocket] = []

    async def connect_logs(self, ws: WebSocket):
        await ws.accept()
        self.log_clients.append(ws)

    def disconnect_logs(self, ws: WebSocket):
        if ws in self.log_clients:
            self.log_clients.remove(ws)

    async def connect_telemetry(self, ws: WebSocket):
        await ws.accept()
        self.telemetry_clients.append(ws)

    def disconnect_telemetry(self, ws: WebSocket):
        if ws in self.telemetry_clients:
            self.telemetry_clients.remove(ws)

    async def broadcast_log(self, text: str):
        dead = []
        for ws in self.log_clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_logs(ws)

    async def broadcast_telemetry(self, data: dict):
        dead = []
        for ws in self.telemetry_clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_telemetry(ws)

BROADCASTER = TelemetryBroadcaster()
ASYNC_LOOP = None

def append_sim_log(message: str):
    """Append a bounded simulation log entry; callers must hold SIM_LOCK."""
    SIM_STATE["logs"].append(message)
    if len(SIM_STATE["logs"]) > MAX_LOG_LINES:
        del SIM_STATE["logs"][:-MAX_LOG_LINES]
    if ASYNC_LOOP and ASYNC_LOOP.is_running():
        try:
            asyncio.run_coroutine_threadsafe(BROADCASTER.broadcast_log(message), ASYNC_LOOP)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Real-time telemetry frame generation (from parsed .vec / KPI data)
# ---------------------------------------------------------------------------
_TELEMETRY_CACHE: Dict[str, Dict[str, Any]] = {}
_TELEMETRY_CACHE_MTIME: Dict[str, float] = {}
_RAT_SCALAR_CACHE: Dict[str, Any] = {}

def _latest_data_source(results_dir: Path) -> Optional[Path]:
    """Pick the most recent vector source: *.vec first, then the CSV-R export."""
    if not results_dir.exists():
        return None
    vec_files = [p for p in results_dir.glob("*.vec") if p.is_file()]
    if vec_files:
        return max(vec_files, key=lambda p: p.stat().st_mtime)
    csv_file = results_dir / "exported_vectors.csv"
    if csv_file.is_file():
        return csv_file
    return None


def _scalar_rat_map(results_dir: Path) -> Dict[int, str]:
    """Per-vehicle link state from the recorded ``activeInterface:last`` scalar.

    Fallback used when the ``activeInterface`` vectors are not recorded:
    the hybrid manager emits this scalar per node in the ``.sca`` file (same
    semantics as the vector). Cached by file mtime; nodes without a finite
    recorded value stay absent (rendered as "not recorded").
    """
    if not results_dir.exists():
        return {}
    sca_files = [p for p in results_dir.glob("*.sca") if p.is_file()]
    if not sca_files:
        return {}
    source = max(sca_files, key=lambda p: p.stat().st_mtime)
    try:
        mtime = source.stat().st_mtime
    except OSError:
        return {}
    key = str(source.resolve())
    cached = _RAT_SCALAR_CACHE.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    from tools.dashboard import parse_scalar_rat_map
    rat_map = parse_scalar_rat_map(source)
    _RAT_SCALAR_CACHE[key] = (mtime, rat_map)
    return rat_map


def _cached_vector_series(results_dir: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Return parsed vector series, re-parsing only when the source file changes.

    Supports both native OMNeT++ ``*.vec`` recordings and the scavetool
    ``exported_vectors.csv`` export (same fallback order as dashboard.py).
    """
    source = _latest_data_source(results_dir)
    if source is None:
        return {}
    try:
        mtime = source.stat().st_mtime
    except OSError:
        return {}
    key = str(source.resolve())
    if _TELEMETRY_CACHE.get(key) and _TELEMETRY_CACHE_MTIME.get(key) == mtime:
        return _TELEMETRY_CACHE[key]
    from tools.dashboard import parse_vector_file, parse_csv_file
    if source.suffix == '.csv':
        series = parse_csv_file(source)
    else:
        series = parse_vector_file(source)
    _TELEMETRY_CACHE[key] = series
    _TELEMETRY_CACHE_MTIME[key] = mtime
    return series


def _interpolate_at(series_points: List[Tuple[float, float]], t: float) -> Optional[float]:
    """Linear interpolation of (x, y) points at time t; None if no data."""
    if not series_points:
        return None
    xs = [p[0] for p in series_points]
    ys = [p[1] for p in series_points]
    if t <= xs[0]:
        return ys[0]
    if t >= xs[-1]:
        return ys[-1]
    # binary search
    import bisect
    idx = bisect.bisect_left(xs, t)
    if idx == 0:
        return ys[0]
    if idx >= len(xs):
        return ys[-1]
    x0, x1 = xs[idx - 1], xs[idx]
    y0, y1 = ys[idx - 1], ys[idx]
    if x1 == x0:
        return y0
    frac = (t - x0) / (x1 - x0)
    return y0 + frac * (y1 - y0)


def _vehicle_sort_key(label: str):
    parts = label.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return (0, int(parts[-1]), label)
    return (1, 0, label)


def _series_points(metrics: Dict[str, Any], metric: str) -> List[Tuple[float, float]]:
    """(time, value) samples of a recorded metric; [] when it is not recorded."""
    entry = metrics.get(metric) or {}
    xs = entry.get('x') or []
    ys = entry.get('y') or []
    return [(float(x), float(y)) for x, y in zip(xs, ys)]


def _value_at(metrics: Dict[str, Any], metric: str, sim_time: Optional[float]) -> Optional[float]:
    """Interpolated metric value at sim_time; latest sample when sim_time is None."""
    points = _series_points(metrics, metric)
    if not points:
        return None
    if sim_time is None:
        return points[-1][1]
    return _interpolate_at(points, sim_time)


def _median_of(points: List[Tuple[float, float]]) -> Optional[float]:
    values = [v for _, v in points if v is not None]
    return statistics.median(values) if values else None


def _datarate_mbps(raw: Optional[float]) -> Optional[float]:
    """datarateSelected is recorded in bit/s (12e6 => 12 Mbps)."""
    if raw is None:
        return None
    return round(raw / 1.0e6, 4) if raw > 1000.0 else raw


def _mec_latency_ms(raw: Optional[float], typical_raw: Optional[float]) -> Optional[float]:
    """mecTaskLatency unit detection: the model emits seconds, older runs ms."""
    if raw is None:
        return None
    scale = 1.0 if (typical_raw is not None and typical_raw >= 1.0) else 1000.0
    return round(raw * scale, 3)


def _battery_pct(raw: Optional[float]) -> Optional[float]:
    if raw is None:
        return None
    return round(raw * 100.0, 2) if raw <= 1.0 else raw


# Incremental Live Telemetry Streaming (O(1) seek offset)
_LIVE_STREAM_OFFSETS: Dict[str, int] = {}
_LAST_LIVE_FRAMES: Dict[str, Dict[str, Any]] = {}

def read_incremental_live_stream(results_dir: Path) -> Optional[Dict[str, Any]]:
    """O(1) tail of live_stream.jsonl emitted during simulation.
    Reads only newly appended bytes since last read, without reparsing large .vec files.
    """
    stream_file = results_dir / "live_stream.jsonl"
    if not stream_file.is_file():
        return None
    key = str(stream_file.resolve())
    last_offset = _LIVE_STREAM_OFFSETS.get(key, 0)
    try:
        size = stream_file.stat().st_size
        if size <= last_offset:
            # No new data appended
            return _LAST_LIVE_FRAMES.get(key)
        
        last_valid_frame = None
        with open(stream_file, 'r', encoding='utf-8') as f:
            f.seek(last_offset)
            for line in f:
                line = line.strip()
                if line:
                    try:
                        last_valid_frame = json.loads(line)
                    except Exception:
                        pass
            _LIVE_STREAM_OFFSETS[key] = f.tell()
        
        if last_valid_frame:
            _LAST_LIVE_FRAMES[key] = last_valid_frame
            return last_valid_frame
    except Exception:
        pass
    return _LAST_LIVE_FRAMES.get(key)


def build_live_telemetry_frame(scenario_name: str, sim_time: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Build a live telemetry frame at sim_time from recorded vectors/KPIs.

    Prioritizes O(1) incremental live_stream.jsonl if present; falls back to
    cached vector interpolation. Only genuinely recorded values are reported.
    """
    from tools.nexasim import resolve_generated_dir
    target_dir = resolve_generated_dir(scenario_name)
    results_dir = target_dir / 'results'

    # Check for incremental live stream first (O(1) streaming)
    live_stream_frame = read_incremental_live_stream(results_dir)
    if live_stream_frame and sim_time is None:
        return live_stream_frame

    series = _cached_vector_series(results_dir)

    kpi_file = results_dir / 'kpi_summary.json'
    kpis: Dict[str, Any] = {}
    if kpi_file.exists():
        try:
            with open(kpi_file, 'r', encoding='utf-8') as f:
                kpis = json.load(f)
        except Exception:
            pass

    if not series and not kpis:
        return None

    scalar_rat = _scalar_rat_map(results_dir)

    vehicles: List[Dict[str, Any]] = []
    for node_label in sorted(series.keys(), key=_vehicle_sort_key):
        metrics = series[node_label]
        if not metrics:
            continue

        vidx = 0
        parts = node_label.split()
        if len(parts) >= 2 and parts[1].isdigit():
            vidx = int(parts[1])

        active_raw = _value_at(metrics, 'activeInterface', sim_time)
        switch_raw = _value_at(metrics, 'switchCount', sim_time)
        latency_raw = _value_at(metrics, 'mecTaskLatency', sim_time)
        latency_typical = _median_of(_series_points(metrics, 'mecTaskLatency'))

        active_rat = None if active_raw is None else ("V2X" if active_raw >= 1.5 else ("LEO" if active_raw >= 0.5 else "5G"))
        if active_rat is None:
            # Fallback: dominant link from the recorded hybridManager usage
            # ratio scalars (run aggregate) — recorded data, never guessed.
            active_rat = scalar_rat.get(vidx)

        vehicles.append({
            "id": vidx,
            "name": node_label,
            "lat": None,
            "lon": None,
            "speed_kmh": _value_at(metrics, 'speedKmh', sim_time),
            "throughput_mbps": _datarate_mbps(_value_at(metrics, 'datarateSelected', sim_time)),
            "mec_latency_ms": _mec_latency_ms(latency_raw, latency_typical),
            "qos_score": _value_at(metrics, 'qosScore', sim_time),
            "battery_soc_pct": _battery_pct(_value_at(metrics, 'batterySoC', sim_time)),
            "vho_count": int(switch_raw) if switch_raw is not None else None,
            "active_rat": active_rat,
            "in_blind": False,
            "elevation_deg": _value_at(metrics, 'elevation', sim_time),
            "slant_range_km": _value_at(metrics, 'slantRangeKm', sim_time),
            "doppler_khz": _value_at(metrics, 'dopplerShiftKhz', sim_time),
            "carrier_ghz": _value_at(metrics, 'carrierFrequencyGhz', sim_time),
            "heading_deg": _value_at(metrics, 'headingDeg', sim_time),
            "last_updated_s": sim_time,
        })

    # Without per-vehicle vectors, expose the KPI scalars as a single aggregate row
    if not vehicles and kpis:
        sat_pct = kpis.get('sat_usage_pct')
        mean_qos = kpis.get('mean_qos_score')  # may legitimately be None
        final_soc = kpis.get('final_battery_soc')
        vehicles.append({
            "id": 0,
            "name": "Aggregate",
            "lat": None,
            "lon": None,
            "speed_kmh": None,
            "throughput_mbps": float(kpis['throughput_mbps']) if kpis.get('throughput_mbps') is not None else None,
            "mec_latency_ms": float(kpis['avg_latency_ms']) if kpis.get('avg_latency_ms') is not None else None,
            "qos_score": float(mean_qos) if mean_qos is not None else None,
            "battery_soc_pct": float(final_soc) if final_soc is not None else None,
            "vho_count": int(kpis['total_vho_switches']) if kpis.get('total_vho_switches') is not None else None,
            "active_rat": None if sat_pct is None else ("LEO" if float(sat_pct) > 50.0 else "5G"),
            "in_blind": False,
        })

    def fleet_mean(key: str) -> Optional[float]:
        values = [v[key] for v in vehicles if v.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    throughput = fleet_mean('throughput_mbps')
    latency = fleet_mean('mec_latency_ms')
    if throughput is None and kpis.get('throughput_mbps') is not None:
        throughput = float(kpis['throughput_mbps'])
    if latency is None and kpis.get('avg_latency_ms') is not None:
        latency = float(kpis['avg_latency_ms'])

    rat_votes = [v['active_rat'] for v in vehicles if v.get('active_rat')]
    if rat_votes:
        active_rat = max(set(rat_votes), key=rat_votes.count)
    elif kpis.get('sat_usage_pct') is not None:
        active_rat = "LEO" if float(kpis['sat_usage_pct']) > 50.0 else "5G"
    else:
        active_rat = "UNKNOWN"

    return {
        "type": "telemetry",
        "sim_time": sim_time,
        "throughput_mbps": throughput,
        "latency_ms": latency,
        "active_rat": active_rat,
        "vehicles": vehicles,
    }


# Background telemetry broadcast loop state
TELEMETRY_LOOP_TASK: Optional[asyncio.Task] = None
TELEMETRY_SIM_T: Dict[str, float] = {}  # scenario_name -> sim time progress

def _schedule_telemetry_loop():
    """Start the background telemetry broadcast loop if not running."""
    global TELEMETRY_LOOP_TASK
    if TELEMETRY_LOOP_TASK is None or TELEMETRY_LOOP_TASK.done():
        if ASYNC_LOOP and ASYNC_LOOP.is_running():
            TELEMETRY_LOOP_TASK = ASYNC_LOOP.create_task(_telemetry_broadcast_loop())


def _default_telemetry_scenario() -> Optional[str]:
    """Most recently updated generated scenario that actually has recordings."""
    candidates = []
    if GENERATED_DIR.exists():
        for entry in GENERATED_DIR.iterdir():
            if not entry.is_dir():
                continue
            results = entry / 'results'
            if (results / 'kpi_summary.json').exists() or _latest_data_source(results):
                try:
                    candidates.append((entry.stat().st_mtime, entry.name))
                except OSError:
                    pass
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None

async def _telemetry_broadcast_loop():
    """Periodically broadcast interpolated telemetry frames to connected clients."""
    while True:
        await asyncio.sleep(0.5)  # 2 Hz telemetry tick
        if not BROADCASTER.telemetry_clients:
            continue
        with SIM_LOCK:
            running = SIM_STATE["running"]
            sc = SIM_STATE["current_scenario"]
        if not sc:
            continue
        t = TELEMETRY_SIM_T.get(sc, 0.0)
        # Advance sim time while running; loop at scenario duration
        duration = 300.0
        try:
            import yaml as _yaml
            from tools.nexasim import resolve_scenario_yaml
            _ypath = resolve_scenario_yaml(sc)
            if _ypath:
                with open(_ypath, 'r', encoding='utf-8') as _f:
                    _doc = _yaml.safe_load(_f)
                duration = float((_doc.get('scenario', {}).get('time', {}) or {}).get('duration_s', 300.0))
        except Exception:
            pass
        if running:
            t += 0.5  # advance in step with tick
        frame = build_live_telemetry_frame(sc, t)
        if frame:
            TELEMETRY_SIM_T[sc] = t
            try:
                await BROADCASTER.broadcast_telemetry(frame)
            except Exception:
                pass
        if running and duration > 0 and t >= duration:
            TELEMETRY_SIM_T[sc] = 0.0

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ASYNC_LOOP
    try:
        ASYNC_LOOP = asyncio.get_running_loop()
    except Exception:
        pass
    _schedule_telemetry_loop()
    yield

app = FastAPI(
    title="NexaSim Studio API",
    description="Control Center for NexaSim",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class IdRequest(BaseModel):
    id: str

class SaveRequest(BaseModel):
    id: str
    yaml: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class NodeDeleteRequest(BaseModel):
    id: str
    type: str  # 'gnb', 'gs', 'blind'
    name: str

class ValidateRequest(BaseModel):
    yaml: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class SaveAndGenerateRequest(BaseModel):
    id: str
    yaml: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    generate_sumo: bool = False

class OsmSumoRequest(BaseModel):
    bbox: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    scenario_id: str
    area_name: Optional[str] = "custom_area"

# HTML rendering
def render_studio_html() -> str:
    html_file = STUDIO_DIST_DIR / 'index.html'
    if not html_file.exists():
        html_file = REPO_ROOT / 'studio' / 'index.html'
    if html_file.exists():
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = "<!doctype html><html><head><title>NexaSim Studio</title></head><body><h1>NexaSim Studio Enterprise</h1><p>Please compile the React Studio: 'cd studio && npm run build'</p></body></html>"

    carto_key = os.environ.get('CARTO_API_KEY', '')
    content = content.replace('__CARTO_API_KEY__', carto_key)
    return content

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def serve_studio_html():
    return render_studio_html()

@app.get("/api/scenarios")
async def get_scenarios():
    scenarios = []
    for yaml_file in sorted(LIBRARY_DIR.glob("*.yaml")):
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                doc = yaml.safe_load(f)
            sc = doc.get('scenario', {})
            name = sc.get('name', yaml_file.stem)
            desc = sc.get('description', '')
            time_cfg = sc.get('time', {})
            area = sc.get('area', {})
            const_cfg = sc.get('constellation', {})
            terr_cfg = sc.get('terrestrial', {})

            shells = const_cfg.get('shells', [])
            sats = sum(s.get('num_planes', 0) * s.get('sats_per_plane', 0) for s in shells)
            gnbs = terr_cfg.get('gnb', {}).get('sites', [])
            ues = terr_cfg.get('ue', {}).get('count', 0)
            gws = const_cfg.get('ground_stations', [])
            blind_spots = terr_cfg.get('blind_spots', [])
            switching_mode = terr_cfg.get('switching_mode') or terr_cfg.get('integration', {}).get('handover', {}).get('mode', 'coverage-based')
            rain_rate = terr_cfg.get('alpine_weather', {}).get('rain_rate_mm_hr', 15.0)

            from tools.nexasim import resolve_generated_dir
            gen_dir = resolve_generated_dir(yaml_file.stem)
            results_dir = gen_dir / 'results'
            short_name = gen_dir.name
            has_dashboard = (results_dir / 'dashboard.html').exists()
            has_globe = (results_dir / 'globe.html').exists()

            scenarios.append({
                "id": yaml_file.stem,
                "name": name,
                "description": desc,
                "duration_s": time_cfg.get('duration_s', 300),
                "area_name": area.get('name', 'Default Area'),
                "center": [area.get('center_lat', 46.5), area.get('center_lon', 10.5)],
                "bbox": area.get('bbox', [10.4, 46.5, 10.5, 46.56]),
                "elevation_mask_deg": area.get('elevation_mask_deg', 25.0),
                "switching_mode": switching_mode,
                "rain_rate": rain_rate,
                "satellites": sats,
                "gnbs": gnbs,
                "ground_stations": gws,
                "blind_spots": blind_spots,
                "vehicles": ues,
                "has_dashboard": has_dashboard,
                "has_globe": has_globe,
                "short_name": short_name
            })
        except Exception:
            pass
    return scenarios

@app.get("/api/scenario")
async def get_scenario(name: str):
    yaml_file = LIBRARY_DIR / f"{name}.yaml"
    if not yaml_file.exists():
        for f in LIBRARY_DIR.glob("*.yaml"):
            if name in f.stem:
                yaml_file = f
                break

    if not yaml_file.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")

    with open(yaml_file, 'r', encoding='utf-8') as f:
        raw_text = f.read()
        f.seek(0)
        parsed = yaml.safe_load(f)

    return {
        "id": yaml_file.stem,
        "yaml": raw_text,
        "data": parsed
    }

@app.get("/api/scenarios/schema")
async def get_scenarios_schema():
    schema_path = REPO_ROOT / "scenarios" / "schema" / "scenario.schema.json"
    if not schema_path.exists():
        schema_path = REPO_ROOT / "config" / "schemas" / "scenario.yaml"
    if schema_path.exists():
        with open(schema_path, 'r', encoding='utf-8') as f:
            if schema_path.suffix == '.json':
                return json.load(f)
            return yaml.safe_load(f)
    return {}

@app.get("/api/scenarios/{scenario_id}/raw")
async def get_scenario_raw(scenario_id: str):
    from tools.nexasim import resolve_scenario_yaml, resolve_generated_dir
    yaml_file = resolve_scenario_yaml(scenario_id)
    if not yaml_file or not yaml_file.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")

    with open(yaml_file, 'r', encoding='utf-8') as f:
        raw_text = f.read()
        f.seek(0)
        parsed = yaml.safe_load(f)

    gen_dir = resolve_generated_dir(scenario_id)
    tle_text = ""
    tle_file = gen_dir / "constellation.tle"
    if tle_file.exists():
        try:
            tle_text = tle_file.read_text(encoding='utf-8')
        except Exception:
            pass

    route_geo = None
    route_file = gen_dir / "route_geo.json"
    if route_file.exists():
        try:
            with open(route_file, 'r', encoding='utf-8') as rf:
                route_geo = json.load(rf)
        except Exception:
            pass

    kpis = None
    kpi_file = gen_dir / "results" / "kpi_summary.json"
    if kpi_file.exists():
        try:
            with open(kpi_file, 'r', encoding='utf-8') as kf:
                kpis = json.load(kf)
        except Exception:
            pass

    return {
        "id": yaml_file.stem,
        "yaml": raw_text,
        "data": parsed,
        "constellation_tle": tle_text,
        "route_geo": route_geo,
        "kpis": kpis
    }

@app.get("/api/status")
async def get_status():
    with SIM_LOCK:
        return {
            "running": SIM_STATE["running"],
            "run_id": SIM_STATE["run_id"],
            "scenario": SIM_STATE["current_scenario"],
            "started_at": SIM_STATE["started_at"],
            "logs": SIM_STATE["logs"][-200:],
            "exit_code": SIM_STATE["exit_code"]
        }

@app.get("/api/results")
async def get_results(name: str):
    from tools.nexasim import resolve_generated_dir
    target_dir = resolve_generated_dir(name)
    short_name = target_dir.name
    results_dir = target_dir / 'results'

    kpi_json = results_dir / 'kpi_summary.json'
    kpis = {}
    if kpi_json.exists():
        with open(kpi_json, 'r', encoding='utf-8') as f:
            kpis = json.load(f)

    has_dashboard = (results_dir / 'dashboard.html').exists()
    has_globe = (results_dir / 'globe.html').exists()

    return {
        "scenario": short_name,
        "kpis": kpis,
        "dashboard_url": f"/results/{short_name}/results/dashboard.html" if has_dashboard else None,
        "globe_url": f"/results/{short_name}/results/globe.html" if has_globe else None
    }

def build_telemetry_payload(results_dir: Path) -> Dict[str, Any]:
    """Build fleet-aggregated timeseries for the dashboard charts."""
    series = _cached_vector_series(results_dir)
    kpi_file = results_dir / 'kpi_summary.json'
    kpis: Dict[str, Any] = {}
    if kpi_file.exists():
        try:
            with open(kpi_file, 'r', encoding='utf-8') as f:
                kpis = json.load(f)
        except Exception:
            kpis = {}

    if series:
        master: List[float] = []
        for metric in ('datarateSelected', 'activeInterface', 'qosScore', 'switchCount', 'mecTaskLatency'):
            axis = set()
            for metrics in series.values():
                axis.update(x for x, _ in _series_points(metrics, metric))
            if axis:
                master = sorted(axis)
                break

        if master:
            stride = max(1, -(-len(master) // 600))  # ceil division: cap at ~600 points
            grid = master[::stride]
            vels = list(series.values())

            lat_samples = [v for m in vels for _, v in _series_points(m, 'mecTaskLatency')]
            lat_typical = statistics.median(lat_samples) if lat_samples else None

            def rate_scale(v: float) -> float:
                return v / 1.0e6 if v > 1000.0 else v

            def lat_scale(v: float) -> float:
                return v * 1000.0 if (lat_typical is not None and lat_typical < 1.0) else v

            def fleet_curve(metric: str, scale=None) -> List[Optional[float]]:
                per_vehicle = []
                for m in vels:
                    pts = _series_points(m, metric)
                    if not pts:
                        continue
                    if scale is not None:
                        pts = [(t, scale(v)) for t, v in pts]
                    per_vehicle.append(pts)
                if not per_vehicle:
                    return [None] * len(grid)
                out: List[Optional[float]] = []
                for t in grid:
                    vals = [_interpolate_at(pts, t) for pts in per_vehicle]
                    vals = [v for v in vals if v is not None]
                    out.append(round(sum(vals) / len(vals), 4) if vals else None)
                return out

            throughput_series = fleet_curve('datarateSelected', rate_scale)
            rtt_series = fleet_curve('mecTaskLatency', lat_scale)
            qos_series = fleet_curve('qosScore')

            # Handover events: prefer explicit switchCount, else count genuine
            # activeInterface transitions, else the scalar KPI total.
            handover_series: List[Optional[float]] = [None] * len(grid)
            switch_vehicles = [_series_points(m, 'switchCount') for m in vels]
            switch_vehicles = [pts for pts in switch_vehicles if pts]
            rat_vehicles = [_series_points(m, 'activeInterface') for m in vels]
            rat_vehicles = [pts for pts in rat_vehicles if pts]

            if switch_vehicles:
                for i, t in enumerate(grid):
                    total = 0.0
                    found = False
                    for pts in switch_vehicles:
                        val = _interpolate_at(pts, t)
                        if val is not None:
                            total += val
                            found = True
                    handover_series[i] = int(total) if found else None
            elif rat_vehicles:
                transition_times: List[float] = []
                for pts in rat_vehicles:
                    for (_, v0), (t1, v1) in zip(pts, pts[1:]):
                        if v1 != v0:
                            transition_times.append(t1)
                transition_times.sort()
                for i, t in enumerate(grid):
                    handover_series[i] = bisect.bisect_right(transition_times, t)
            elif kpis.get('total_vho_switches') is not None:
                handover_series = [int(kpis['total_vho_switches'])] * len(grid)

            # Active interface: fleet majority (0 = 5G, 1 = LEO) per timestep
            if rat_vehicles:
                active_series: List[Optional[int]] = []
                for t in grid:
                    votes = [_interpolate_at(pts, t) for pts in rat_vehicles]
                    votes = [v for v in votes if v is not None]
                    active_series.append(None if not votes else (1 if sum(votes) >= len(votes) / 2.0 else 0))
            elif kpis.get('sat_usage_pct') is not None:
                active_series = [1 if float(kpis['sat_usage_pct']) > 50.0 else 0] * len(grid)
            else:
                active_series = [None] * len(grid)

            return {
                "timestamps": grid,
                "throughput_mbps": throughput_series,
                "rtt_ms": rtt_series,
                "handover_events": handover_series,
                "active_interface": active_series,
                "qos_score": qos_series,
            }

    return {
        "timestamps": [0.0],
        "throughput_mbps": [float(kpis['throughput_mbps']) if kpis.get('throughput_mbps') is not None else None],
        "rtt_ms": [float(kpis['avg_latency_ms']) if kpis.get('avg_latency_ms') is not None else None],
        "handover_events": [int(kpis['total_vho_switches']) if kpis.get('total_vho_switches') is not None else None],
        "active_interface": [1 if float(kpis['sat_usage_pct']) > 50.0 else 0] if kpis.get('sat_usage_pct') is not None else [None],
        "qos_score": [float(kpis['mean_qos_score']) if kpis.get('mean_qos_score') is not None else None],
    }


@app.get("/api/telemetry")
async def get_telemetry(name: str):
    """Fleet-aggregated timeseries for the dashboard charts (real units)."""
    from tools.nexasim import resolve_generated_dir
    target_dir = resolve_generated_dir(name)
    results_dir = target_dir / 'results' if (target_dir / 'results').exists() else target_dir
    return build_telemetry_payload(results_dir)

@app.get("/api/fleet")
async def get_fleet(name: str, t: Optional[float] = None):
    """Latest per-vehicle telemetry snapshot for the Fleet Matrix table."""
    frame = build_live_telemetry_frame(name, t)
    if frame is None:
        return {"scenario": name, "sim_time": t, "vehicles": []}
    return {
        "scenario": name,
        "sim_time": frame.get("sim_time"),
        "active_rat": frame.get("active_rat"),
        "vehicles": frame.get("vehicles", []),
    }

@app.get("/api/fleet_timeline")
async def get_fleet_timeline(name: str, max_points: int = 150):
    """Sampled per-vehicle timeline entries for time-machine scrubbing."""
    from tools.nexasim import resolve_generated_dir
    target_dir = resolve_generated_dir(name)
    results_dir = target_dir / 'results' if (target_dir / 'results').exists() else target_dir
    series = _cached_vector_series(results_dir)
    if not series:
        return {"scenario": name, "timestamps": [], "vehicles_timeline": {}}

    all_times = set()
    for node_label, metrics in series.items():
        for mname in ('activeInterface', 'speedKmh', 'mecTaskLatency', 'qosScore', 'batterySoC', 'elevation'):
            pts = _series_points(metrics, mname)
            for pt_t, _ in pts:
                all_times.add(round(pt_t, 2))

    sorted_times = sorted(all_times)
    if not sorted_times:
        return {"scenario": name, "timestamps": [], "vehicles_timeline": {}}

    if len(sorted_times) > max_points:
        step = len(sorted_times) / max_points
        sampled_times = [sorted_times[int(i * step)] for i in range(max_points)]
        if sorted_times[-1] not in sampled_times:
            sampled_times.append(sorted_times[-1])
    else:
        sampled_times = sorted_times

    vehicles_timeline: Dict[str, List[Dict[str, Any]]] = {}
    scalar_rat = _scalar_rat_map(results_dir)

    for node_label in sorted(series.keys(), key=_vehicle_sort_key):
        metrics = series[node_label]
        vidx = 0
        parts = node_label.split()
        if len(parts) >= 2 and parts[1].isdigit():
            vidx = int(parts[1])

        lat_samples = [v for _, v in _series_points(metrics, 'mecTaskLatency')]
        latency_typical = statistics.median(lat_samples) if lat_samples else None
        node_timeline = []

        for st in sampled_times:
            active_raw = _value_at(metrics, 'activeInterface', st)
            active_rat = None if active_raw is None else ("V2X" if active_raw >= 1.5 else ("LEO" if active_raw >= 0.5 else "5G"))
            if active_rat is None:
                active_rat = scalar_rat.get(vidx)

            latency_raw = _value_at(metrics, 'mecTaskLatency', st)
            switch_raw = _value_at(metrics, 'switchCount', st)

            node_timeline.append({
                "t": st,
                "speed_kmh": _value_at(metrics, 'speedKmh', st),
                "throughput_mbps": _datarate_mbps(_value_at(metrics, 'datarateSelected', st)),
                "mec_latency_ms": _mec_latency_ms(latency_raw, latency_typical),
                "qos_score": _value_at(metrics, 'qosScore', st),
                "battery_soc_pct": _battery_pct(_value_at(metrics, 'batterySoC', st)),
                "vho_count": int(switch_raw) if switch_raw is not None else None,
                "active_rat": active_rat,
                "elevation_deg": _value_at(metrics, 'elevation', st),
                "slant_range_km": _value_at(metrics, 'slantRangeKm', st),
                "doppler_khz": _value_at(metrics, 'dopplerShiftKhz', st),
                "carrier_ghz": _value_at(metrics, 'carrierFrequencyGhz', st),
                "heading_deg": _value_at(metrics, 'headingDeg', st)
            })
        vehicles_timeline[str(vidx)] = node_timeline

    return {
        "scenario": name,
        "timestamps": sampled_times,
        "vehicles_timeline": vehicles_timeline
    }

@app.get("/api/compare")
async def get_compare(name: str):
    """
    Returns comparative benchmark run (e.g. baseline or alternative strategy) for A/B comparison.
    """
    from tools.nexasim import resolve_generated_dir
    target_dir = resolve_generated_dir(name)
    results_dir = target_dir / 'results' if (target_dir / 'results').exists() else target_dir

    # 1. Direct compare baseline JSON if saved
    compare_file = results_dir / 'compare_baseline.json'
    if compare_file.exists():
        try:
            with open(compare_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    # 2. Check for alternative baseline / comparative directories
    parent = target_dir.parent
    baseline_dirs = list(parent.glob(f"{target_dir.name}_baseline*")) + list(parent.glob(f"{name}_baseline*"))
    for b_dir in baseline_dirs:
        b_res = b_dir / 'results' if (b_dir / 'results').exists() else b_dir
        b_kpi_file = b_res / 'kpi_summary.json'
        if b_kpi_file.exists():
            try:
                with open(b_kpi_file, 'r', encoding='utf-8') as f:
                    b_kpis = json.load(f)
                return {
                    "available": True,
                    "scenario": name,
                    "baseline_strategy": "Coverage-Based (Hard VHO)",
                    "kpis": b_kpis,
                    "telemetry": build_telemetry_payload(b_res)
                }
            except Exception:
                pass

    return {
        "available": False,
        "scenario": name,
        "baseline_strategy": None,
        "kpis": None,
        "telemetry": None
    }

@app.get("/api/route")
async def get_route(name: str):
    from tools.nexasim import resolve_generated_dir
    target_dir = resolve_generated_dir(name)
    geo_file = target_dir / 'route_geo.json'
    if not geo_file.exists():
        geo_file = target_dir.parent / 'route_geo.json'

    if geo_file.exists():
        with open(geo_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    return {"scenario": name, "coordinates": []}

@app.post("/api/save")
async def post_save(req: SaveRequest):
    target_file = (LIBRARY_DIR / f"{req.id}.yaml").resolve()
    if LIBRARY_DIR.resolve() not in target_file.parents:
        raise HTTPException(status_code=403, detail="Invalid scenario ID")

    content_to_write = ""
    if req.yaml is not None:
        try:
            parsed = yaml.safe_load(req.yaml)
            from tools.schema import ScenarioDocument
            ScenarioDocument(**parsed)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid scenario payload: {str(e)}")
        content_to_write = req.yaml
    elif req.data is not None:
        try:
            from tools.schema import ScenarioDocument
            ScenarioDocument(**req.data)
            content_to_write = yaml.dump(req.data, sort_keys=False, default_flow_style=False)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid scenario payload: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Either 'yaml' or 'data' field is required")

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(content_to_write)

    # Immediately synchronize generated scenario files (scenario.ned, omnetpp.ini, constellation.tle)
    try:
        from tools.nexasim import resolve_generated_dir
        from tools.gen_scenario import ScenarioGenerator
        out_dir = resolve_generated_dir(req.id)
        gen = ScenarioGenerator(str(target_file))
        gen.generate(str(out_dir))
    except Exception as e:
        print(f"[!] Warning: Auto-regenerating scenario '{req.id}' failed: {e}")

    return {"status": "saved", "path": str(target_file)}

@app.post("/api/scenario/node/delete")
async def post_delete_node(req: NodeDeleteRequest):
    target_file = (LIBRARY_DIR / f"{req.id}.yaml").resolve()
    if LIBRARY_DIR.resolve() not in target_file.parents or not target_file.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")

    with open(target_file, 'r', encoding='utf-8') as f:
        doc = yaml.safe_load(f)

    sc = doc.get('scenario', {})
    terr = sc.get('terrestrial', {})
    const = sc.get('constellation', {})
    deleted = False

    if req.type == 'gnb':
        sites = terr.get('gnb', {}).get('sites', [])
        before = len(sites)
        sites = [s for s in sites if s.get('name') != req.name]
        if len(sites) < before:
            terr['gnb']['sites'] = sites
            terr['gnb']['count'] = len(sites)
            deleted = True
    elif req.type == 'gs':
        gws = const.get('ground_stations', [])
        before = len(gws)
        gws = [g for g in gws if g.get('name') != req.name]
        if len(gws) < before:
            const['ground_stations'] = gws
            deleted = True
    elif req.type == 'blind':
        blind = terr.get('blind_spots', [])
        before = len(blind)
        blind = [b for b in blind if b.get('name') != req.name]
        if len(blind) < before:
            terr['blind_spots'] = blind
            deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Node '{req.name}' of type '{req.type}' not found")

    from tools.schema import ScenarioDocument
    try:
        ScenarioDocument(**doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Schema validation error after delete: {str(e)}")

    with open(target_file, 'w', encoding='utf-8') as f:
        yaml.dump(doc, f, sort_keys=False, default_flow_style=False)

    # Immediately synchronize generated scenario files after node deletion
    try:
        from tools.nexasim import resolve_generated_dir
        from tools.gen_scenario import ScenarioGenerator
        out_dir = resolve_generated_dir(req.id)
        gen = ScenarioGenerator(str(target_file))
        gen.generate(str(out_dir))
    except Exception as e:
        print(f"[!] Warning: Auto-regenerating scenario '{req.id}' failed after node delete: {e}")

    return {"status": "deleted", "type": req.type, "name": req.name}

@app.post("/api/scenarios/validate")
async def post_validate_scenario(req: ValidateRequest):
    content = req.yaml
    if content is None and req.data is not None:
        content = yaml.dump(req.data, sort_keys=False)

    if not content:
        raise HTTPException(status_code=400, detail="Empty scenario content")

    try:
        parsed = yaml.safe_load(content)
        from tools.schema import ScenarioDocument
        ScenarioDocument(**parsed)
        return {"valid": True, "errors": []}
    except Exception as e:
        error_msgs = []
        if hasattr(e, 'errors'):
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err.get('loc', []))
                msg = err.get('msg', 'validation error')
                error_msgs.append(f"{loc}: {msg}")
        else:
            error_msgs.append(str(e))
        return {"valid": False, "errors": error_msgs}

@app.post("/api/scenarios/save-and-generate")
async def post_save_and_generate(req: SaveAndGenerateRequest):
    target_file = (LIBRARY_DIR / f"{req.id}.yaml").resolve()
    if LIBRARY_DIR.resolve() not in target_file.parents:
        raise HTTPException(status_code=403, detail="Invalid scenario ID")

    content_to_write = ""
    parsed_doc = None
    if req.yaml is not None:
        try:
            parsed_doc = yaml.safe_load(req.yaml)
            from tools.schema import ScenarioDocument
            ScenarioDocument(**parsed_doc)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")
        content_to_write = req.yaml
    elif req.data is not None:
        try:
            from tools.schema import ScenarioDocument
            ScenarioDocument(**req.data)
            parsed_doc = req.data
            content_to_write = yaml.dump(req.data, sort_keys=False, default_flow_style=False)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Either 'yaml' or 'data' required")

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(content_to_write)

    from tools.nexasim import resolve_generated_dir
    from tools.gen_scenario import ScenarioGenerator
    out_dir = resolve_generated_dir(req.id)
    out_dir.mkdir(parents=True, exist_ok=True)

    gen = ScenarioGenerator(str(target_file))
    gen.generate(str(out_dir))

    if req.generate_sumo and parsed_doc:
        try:
            from tools.sumo_generator import generate_sumo_scenario
            generate_sumo_scenario(parsed_doc, out_dir)
        except Exception as e:
            print(f"[!] Warning: SUMO generation failed: {e}")

    generated_files = [p.name for p in out_dir.iterdir() if p.is_file()]
    return {
        "status": "generated",
        "scenario_id": req.id,
        "path": str(target_file),
        "output_directory": str(out_dir),
        "generated_files": generated_files
    }

@app.post("/api/builder/osm-sumo")
async def post_builder_osm_sumo(req: OsmSumoRequest):
    if len(req.bbox) != 4:
        raise HTTPException(status_code=400, detail="Bbox must contain [min_lon, min_lat, max_lon, max_lat]")

    from tools.osm_downloader import download_osm_bbox
    from tools.nexasim import resolve_generated_dir

    out_dir = resolve_generated_dir(req.scenario_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    osm_path = await asyncio.to_thread(download_osm_bbox, req.bbox, out_dir / f"{req.scenario_id}.osm")
    return {
        "status": "downloaded",
        "bbox": req.bbox,
        "osm_file": str(osm_path) if osm_path else None
    }

@app.post("/api/generate")
async def post_generate(req: IdRequest):
    from tools.nexasim import resolve_scenario_yaml, resolve_generated_dir
    yaml_path = resolve_scenario_yaml(req.id)
    out_dir = resolve_generated_dir(req.id)

    if not yaml_path:
        raise HTTPException(status_code=404, detail="Scenario YAML not found")

    from tools.gen_scenario import ScenarioGenerator
    gen = ScenarioGenerator(str(yaml_path))
    gen.generate(str(out_dir))

    return {"status": "generated", "directory": str(out_dir)}

@app.post("/api/view3d")
async def post_view3d(req: IdRequest):
    from tools.czml_generator import create_scenario_digital_twin
    czml_path, html_path = await asyncio.to_thread(create_scenario_digital_twin, req.id, open_browser=False)
    return {"status": "ready", "html": str(html_path)}

@app.post("/api/run")
async def post_run(req: IdRequest, background_tasks: BackgroundTasks):
    from tools.nexasim import resolve_scenario_yaml
    if not resolve_scenario_yaml(req.id):
        raise HTTPException(status_code=404, detail="Scenario not found")

    with SIM_LOCK:
        if SIM_STATE["running"]:
            raise HTTPException(status_code=409, detail="Simulation already running")

        SIM_STATE["running"] = True
        SIM_STATE["run_id"] = uuid.uuid4().hex
        SIM_STATE["current_scenario"] = req.id
        SIM_STATE["started_at"] = datetime.now(timezone.utc).isoformat()
        SIM_STATE["logs"] = []
        SIM_STATE["exit_code"] = None
        run_id = SIM_STATE["run_id"]
        # Reset telemetry sim-time for the new run
        TELEMETRY_SIM_T[req.id] = 0.0

    background_tasks.add_task(run_simulation_worker, req.id, run_id)
    return {"status": "started", "scenario": req.id, "run_id": run_id}

# WebSocket Endpoints for Real-Time Streaming
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await BROADCASTER.connect_logs(websocket)
    with SIM_LOCK:
        recent = list(SIM_STATE["logs"][-80:])
    for line in recent:
        try:
            await websocket.send_text(line)
        except Exception:
            break
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        BROADCASTER.disconnect_logs(websocket)
    except Exception:
        BROADCASTER.disconnect_logs(websocket)

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await BROADCASTER.connect_telemetry(websocket)

    def current_frame() -> Dict[str, Any]:
        with SIM_LOCK:
            sc = SIM_STATE["current_scenario"]
        if not sc:
            sc = _default_telemetry_scenario()
        if sc:
            frame = build_live_telemetry_frame(sc, TELEMETRY_SIM_T.get(sc, 0.0))
            if frame:
                return frame
        return {
            "type": "telemetry",
            "sim_time": 0.0,
            "throughput_mbps": None,
            "latency_ms": None,
            "active_rat": "IDLE",
            "vehicles": [],
        }

    # Send an immediate snapshot so the client is never left idle.
    try:
        await websocket.send_json(current_frame())
    except Exception:
        pass
    try:
        while True:
            # Client pings are answered with the freshest available frame;
            # live frames are also pushed by the background broadcast loop.
            await websocket.receive_text()
            try:
                await websocket.send_json(current_frame())
            except Exception:
                break
    except WebSocketDisconnect:
        BROADCASTER.disconnect_telemetry(websocket)
    except Exception:
        BROADCASTER.disconnect_telemetry(websocket)

@app.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    """Unified telemetry + categorized logs stream for modern Mission Control studio."""
    await websocket.accept()
    await BROADCASTER.connect_telemetry(websocket)
    await BROADCASTER.connect_logs(websocket)

    def current_payload() -> Dict[str, Any]:
        with SIM_LOCK:
            sc = SIM_STATE["current_scenario"]
            st = dict(SIM_STATE)
        if not sc:
            sc = _default_telemetry_scenario()
        frame = build_live_telemetry_frame(sc, TELEMETRY_SIM_T.get(sc, 0.0)) if sc else None
        return {
            "type": "simulation_frame",
            "status": {
                "running": st.get("running", False),
                "scenario": st.get("current_scenario"),
                "run_id": st.get("run_id")
            },
            "telemetry": frame or {
                "sim_time": 0.0,
                "throughput_mbps": None,
                "latency_ms": None,
                "active_rat": "IDLE",
                "vehicles": []
            }
        }

    try:
        await websocket.send_json(current_payload())
        while True:
            msg = await websocket.receive_text()
            # Respond to client tick / ping
            await websocket.send_json(current_payload())
    except WebSocketDisconnect:
        BROADCASTER.disconnect_telemetry(websocket)
        BROADCASTER.disconnect_logs(websocket)
    except Exception:
        BROADCASTER.disconnect_telemetry(websocket)
        BROADCASTER.disconnect_logs(websocket)

def run_simulation_worker(scenario_id: str, run_id: Optional[str] = None):
    """Background worker to run simulation, record terminal logs and trigger KPI analysis."""
    from tools.nexasim import resolve_scenario_yaml, resolve_generated_dir, is_inside_docker, resolve_execution_backend

    proc = None
    exit_code = -1
    try:
        yaml_path = resolve_scenario_yaml(scenario_id)
        if not yaml_path:
            raise ValueError(f"Scenario '{scenario_id}' not found")

        out_dir = resolve_generated_dir(scenario_id)
        short_name = out_dir.name

        if not (out_dir / 'omnetpp.ini').exists():
            from tools.gen_scenario import ScenarioGenerator
            gen = ScenarioGenerator(str(yaml_path))
            gen.generate(str(out_dir))

        backend_type, cmd, cwd, env = resolve_execution_backend(short_name)

        with SIM_LOCK:
            append_sim_log(f"[*] Dispatching simulation for '{scenario_id}' (Backend: {backend_type})...")

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )

        if proc.stdout:
            for line in proc.stdout:
                with SIM_LOCK:
                    append_sim_log(line.rstrip('\r\n'))

        exit_code = proc.wait()
        if exit_code == 0:
            from tools.analyze_results import analyze_simulation_directory
            analyze_simulation_directory(str(out_dir), generate_dashboard=True)
        else:
            with SIM_LOCK:
                append_sim_log("[!] Simulation failed; KPI analysis skipped")
    except Exception as exc:
        with SIM_LOCK:
            append_sim_log(f"[!] Simulation worker error: {exc}")
    finally:
        with SIM_LOCK:
            SIM_STATE["running"] = False
            SIM_STATE["exit_code"] = exit_code if proc is None else proc.returncode
            finished_scenario = SIM_STATE["current_scenario"]
            append_sim_log(
                f"\n[+] Simulation run completed (Exit Code {SIM_STATE['exit_code']})"
            )
        # Clear telemetry sim-time for the finished scenario
        if finished_scenario:
            TELEMETRY_SIM_T.pop(finished_scenario, None)

# Dynamic results handler with token injection for Cesium & Carto
@app.get("/results/{scenario}/results/{filename}")
async def serve_scenario_result_file(scenario: str, filename: str):
    file_path = (GENERATED_DIR / scenario / 'results' / filename).resolve()
    if GENERATED_DIR.resolve() not in file_path.parents or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    if file_path.suffix == '.html':
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        c_tok = os.environ.get('CESIUM_ION_TOKEN', '')
        k_tok = os.environ.get('CARTO_API_KEY', '')
        content = content.replace('__CESIUM_ION_TOKEN__', c_tok)
        content = content.replace('__CARTO_API_KEY__', k_tok)
        return HTMLResponse(content)

    return FileResponse(file_path)

# Static files for /results/ path, inherently secure against Path Traversal
if not GENERATED_DIR.exists():
    os.makedirs(GENERATED_DIR, exist_ok=True)
app.mount("/results", StaticFiles(directory=str(GENERATED_DIR)), name="results")

# Production React Studio assets
if (STUDIO_DIST_DIR / 'assets').exists():
    app.mount("/assets", StaticFiles(directory=str(STUDIO_DIST_DIR / 'assets')), name="assets")
elif STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")

def start_studio_server(port: int = 8080, host: str = '127.0.0.1', open_browser: bool = False):
    """Starts the NexaSim Studio local web control center using Uvicorn."""
    url = f"http://localhost:{port}"

    carto_key = os.environ.get('CARTO_API_KEY')
    cesium_token = os.environ.get('CESIUM_ION_TOKEN')

    print(f"\n==========================================================================")
    print(f" NexaSim Studio • 3D Space-Ground Simulation Command Center")
    print(f" Powered by FastAPI")
    print(f" URL: {url}")
    print(f" Dual-View Engine: 2D Leaflet Tactical Map + 3D CesiumJS Digital Twin")

    if not carto_key:
        print(" [!] Warning: CARTO_API_KEY is not set. 2D Map may fallback to OpenStreetMap.")
    if not cesium_token:
        print(" [!] Warning: CESIUM_ION_TOKEN is not set. 3D Globe may fallback to offline terrain.")

    print(f" Press Ctrl+C to stop the studio server")
    print(f"==========================================================================\n")

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    uvicorn.run(app, host=host, port=port, log_level="warning")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NexaSim Studio Web Server')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind (default: 8080)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind (default: 127.0.0.1)')
    parser.add_argument('--open', action='store_true', help='Open studio in browser automatically')
    args = parser.parse_args()

    start_studio_server(port=args.port, host=args.host, open_browser=args.open)
