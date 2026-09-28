#!/usr/bin/env python3
"""
NexaSim Studio - Aerospace-Grade 2D/3D Control Center & Visual Scenario Builder
Horizon Europe NexaSphere Research Project

Features:
- Dual-Engine View: Interactive 2D Tactical Map (Leaflet) + 3D Space-Ground Globe (CesiumJS)
- Visual No-Code Editor: Point-and-click placement of 5G-NR gNodeBs, Ground Gateways, and Blind Spots
- Multi-Tab Lower Deck: Parameters Customizer, Live Telemetry Cockpit, Terminal Stream, Analytics
- In-Studio Simulation Runner with real-time log streaming and automatic results integration
- Powered by FastAPI for high performance and security
"""

import os
import sys
import json
import yaml
import argparse
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    import uvicorn
    from fastapi import FastAPI, BackgroundTasks, HTTPException
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

# Application State
SIM_STATE = {
    "running": False,
    "current_scenario": None,
    "logs": [],
    "exit_code": None
}
SIM_LOCK = threading.Lock()

app = FastAPI(title="NexaSim Studio API", description="Control Center for NexaSim")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class IdRequest(BaseModel):
    id: str

class SaveRequest(BaseModel):
    id: str
    yaml: str

# HTML rendering
def render_studio_html() -> str:
    html_file = Path(__file__).resolve().parent / 'studio.html'
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

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

@app.get("/api/status")
async def get_status():
    with SIM_LOCK:
        return {
            "running": SIM_STATE["running"],
            "scenario": SIM_STATE["current_scenario"],
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

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(req.yaml)
    return {"status": "saved", "path": str(target_file)}

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
    czml_path, html_path = create_scenario_digital_twin(req.id, open_browser=False)
    return {"status": "ready", "html": str(html_path)}

@app.post("/api/run")
async def post_run(req: IdRequest, background_tasks: BackgroundTasks):
    with SIM_LOCK:
        if SIM_STATE["running"]:
            raise HTTPException(status_code=409, detail="Simulation already running")

        SIM_STATE["running"] = True
        SIM_STATE["current_scenario"] = req.id
        SIM_STATE["logs"] = []
        SIM_STATE["exit_code"] = None

    background_tasks.add_task(run_simulation_worker, req.id)
    return {"status": "started", "scenario": req.id}

def run_simulation_worker(scenario_id: str):
    """Background worker to run simulation, record terminal logs and trigger KPI analysis."""
    from tools.nexasim import resolve_scenario_yaml, resolve_generated_dir, is_inside_docker

    yaml_path = resolve_scenario_yaml(scenario_id)
    out_dir = resolve_generated_dir(scenario_id)
    short_name = out_dir.name

    if not (out_dir / 'omnetpp.ini').exists():
        from tools.gen_scenario import ScenarioGenerator
        gen = ScenarioGenerator(str(yaml_path))
        gen.generate(str(out_dir))

    in_docker = is_inside_docker()
    if in_docker:
        cmd = ['bash', '/artery/tools/opp_run.sh', '-f', f"/artery/scenarios/generated/{short_name}/omnetpp.ini", '-u', 'Cmdenv']
        cwd = str(out_dir)
        env = os.environ.copy()
    else:
        cmd = [
            'docker', 'compose', 'run', '--rm',
            '-w', f"/artery/scenarios/generated/{short_name}",
            'nexasim', 'bash', '/artery/tools/opp_run.sh', '-f', f"/artery/scenarios/generated/{short_name}/omnetpp.ini", '-u', 'Cmdenv'
        ]
        cwd = str(REPO_ROOT)
        env = os.environ.copy()
        env['MSYS_NO_PATHCONV'] = '1'

    with SIM_LOCK:
        SIM_STATE["logs"].append(f"[*] Dispatching simulation for '{scenario_id}'...")

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

    for line in proc.stdout:
        with SIM_LOCK:
            SIM_STATE["logs"].append(line.rstrip('\r\n'))

    proc.wait()

    from tools.analyze_results import analyze_simulation_directory
    analyze_simulation_directory(str(out_dir), generate_dashboard=True)

    with SIM_LOCK:
        SIM_STATE["running"] = False
        SIM_STATE["exit_code"] = proc.returncode
        SIM_STATE["logs"].append(f"\n[+] Simulation run completed (Exit Code {proc.returncode})")

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
if GENERATED_DIR.exists():
    app.mount("/results", StaticFiles(directory=str(GENERATED_DIR)), name="results")
else:
    os.makedirs(GENERATED_DIR, exist_ok=True)
    app.mount("/results", StaticFiles(directory=str(GENERATED_DIR)), name="results")


def start_studio_server(port: int = 8080, open_browser: bool = False):
    """Starts the NexaSim Studio local web control center using Uvicorn."""
    url = f"http://localhost:{port}"

    print(f"\n==========================================================================")
    print(f" NexaSim Studio • 3D Space-Ground Simulation Command Center")
    print(f" Powered by FastAPI")
    print(f" URL: {url}")
    print(f" Dual-View Engine: 2D Leaflet Tactical Map + 3D CesiumJS Digital Twin")
    print(f" Press Ctrl+C to stop the studio server")
    print(f"==========================================================================\n")

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NexaSim Studio Web Server')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind (default: 8080)')
    parser.add_argument('--open', action='store_true', help='Open studio in browser automatically')
    args = parser.parse_args()

    start_studio_server(port=args.port, open_browser=args.open)