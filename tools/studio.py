#!/usr/bin/env python3
"""
NexaSim Studio - Interactive Web Control Center & No-Code Scenario Builder
Horizon Europe NexaSphere Research Project

Provides a lightweight, zero-external-dependency local web studio:
- Visual scenario browser with interactive Leaflet map
- Parameter editor (constellation, VHO strategy, 5G cells, rain rate)
- Real-time simulation launcher with live log stream
- Integrated dashboard and 3D digital twin viewer
"""

import os
import sys
import json
import yaml
import argparse
import threading
import subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import urllib.parse

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = REPO_ROOT / 'scenarios' / 'library'
GENERATED_DIR = REPO_ROOT / 'scenarios' / 'generated'

# Simulation runner state
SIM_STATE = {
    "running": False,
    "current_scenario": None,
    "logs": [],
    "exit_code": None
}
SIM_LOCK = threading.Lock()

class StudioAPIHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress routine HTTP 200 access logs for a clean console
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/' or path == '/index.html':
            self.serve_studio_html()
        elif path == '/api/scenarios':
            self.handle_get_scenarios()
        elif path == '/api/scenario':
            sc_name = query.get('name', [''])[0]
            self.handle_get_scenario(sc_name)
        elif path == '/api/status':
            self.handle_get_status()
        elif path == '/api/results':
            sc_name = query.get('name', [''])[0]
            self.handle_get_results(sc_name)
        elif path.startswith('/results/'):
            # Serve generated dashboard or globe files safely
            rel = path[len('/results/'):]
            target_file = GENERATED_DIR / rel
            if target_file.exists() and target_file.is_file():
                self.serve_file(target_file)
            else:
                self.send_error(404, "Result file not found")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len) if content_len > 0 else b'{}'

        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = {}

        if path == '/api/run':
            self.handle_post_run(data)
        elif path == '/api/generate':
            self.handle_post_generate(data)
        elif path == '/api/save':
            self.handle_post_save(data)
        elif path == '/api/view3d':
            self.handle_post_view3d(data)
        else:
            self.send_error(404, "Endpoint not found")

    def send_json(self, data: Any, status: int = 200):
        resp = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(resp)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(resp)

    def serve_file(self, file_path: Path):
        content_type = 'text/plain'
        if file_path.suffix == '.html':
            content_type = 'text/html; charset=utf-8'
        elif file_path.suffix == '.json' or file_path.suffix == '.czml':
            content_type = 'application/json'
        elif file_path.suffix == '.css':
            content_type = 'text/css'
        elif file_path.suffix == '.js':
            content_type = 'application/javascript'

        with open(file_path, 'rb') as f:
            content = f.read()

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def handle_get_scenarios(self):
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
                gnbs = len(terr_cfg.get('gnb', {}).get('sites', []))
                ues = terr_cfg.get('ue', {}).get('count', 0)

                short_name = name.replace('nexasphere_', '').replace('_hybrid', '').replace('_alpine', '')
                results_dir = GENERATED_DIR / short_name / 'results'
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
                    "satellites": sats,
                    "gnbs": gnbs,
                    "vehicles": ues,
                    "has_dashboard": has_dashboard,
                    "has_globe": has_globe
                })
            except Exception:
                pass
        self.send_json(scenarios)

    def handle_get_scenario(self, sc_id: str):
        yaml_file = LIBRARY_DIR / f"{sc_id}.yaml"
        if not yaml_file.exists():
            for f in LIBRARY_DIR.glob("*.yaml"):
                if sc_id in f.stem:
                    yaml_file = f
                    break

        if not yaml_file.exists():
            self.send_json({"error": "Scenario not found"}, 404)
            return

        with open(yaml_file, 'r', encoding='utf-8') as f:
            raw_text = f.read()
            f.seek(0)
            parsed = yaml.safe_load(f)

        self.send_json({
            "id": yaml_file.stem,
            "yaml": raw_text,
            "data": parsed
        })

    def handle_post_save(self, data: Dict[str, Any]):
        sc_id = data.get('id')
        yaml_text = data.get('yaml')
        if not sc_id or not yaml_text:
            self.send_json({"error": "Missing id or yaml"}, 400)
            return

        target_file = LIBRARY_DIR / f"{sc_id}.yaml"
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(yaml_text)

        self.send_json({"status": "saved", "path": str(target_file)})

    def handle_post_generate(self, data: Dict[str, Any]):
        sc_id = data.get('id')
        if not sc_id:
            self.send_json({"error": "Missing scenario id"}, 400)
            return

        from tools.nexasim import resolve_scenario_yaml, resolve_generated_dir
        yaml_path = resolve_scenario_yaml(sc_id)
        out_dir = resolve_generated_dir(sc_id)

        from tools.gen_scenario import ScenarioGenerator
        gen = ScenarioGenerator(str(yaml_path))
        gen.generate(str(out_dir))

        self.send_json({"status": "generated", "directory": str(out_dir)})

    def handle_post_view3d(self, data: Dict[str, Any]):
        sc_id = data.get('id')
        if not sc_id:
            self.send_json({"error": "Missing scenario id"}, 400)
            return

        from tools.czml_generator import create_scenario_digital_twin
        czml_path, html_path = create_scenario_digital_twin(sc_id, open_browser=False)
        self.send_json({"status": "ready", "html": str(html_path)})

    def handle_post_run(self, data: Dict[str, Any]):
        sc_id = data.get('id')
        if not sc_id:
            self.send_json({"error": "Missing scenario id"}, 400)
            return

        with SIM_LOCK:
            if SIM_STATE["running"]:
                self.send_json({"error": "Another simulation is currently running"}, 409)
                return

            SIM_STATE["running"] = True
            SIM_STATE["current_scenario"] = sc_id
            SIM_STATE["logs"] = []
            SIM_STATE["exit_code"] = None

        thread = threading.Thread(target=run_simulation_worker, args=(sc_id,))
        thread.daemon = True
        thread.start()

        self.send_json({"status": "started", "scenario": sc_id})

    def handle_get_status(self):
        with SIM_LOCK:
            self.send_json({
                "running": SIM_STATE["running"],
                "scenario": SIM_STATE["current_scenario"],
                "logs": SIM_STATE["logs"][-150:], # Last 150 lines
                "exit_code": SIM_STATE["exit_code"]
            })

    def handle_get_results(self, sc_id: str):
        from tools.nexasim import resolve_generated_dir
        target_dir = resolve_generated_dir(sc_id)
        short_name = target_dir.name
        results_dir = target_dir / 'results'

        kpi_json = results_dir / 'kpi_summary.json'
        kpis = {}
        if kpi_json.exists():
            with open(kpi_json, 'r', encoding='utf-8') as f:
                kpis = json.load(f)

        has_dashboard = (results_dir / 'dashboard.html').exists()
        has_globe = (results_dir / 'globe.html').exists()

        self.send_json({
            "scenario": short_name,
            "kpis": kpis,
            "dashboard_url": f"/results/{short_name}/results/dashboard.html" if has_dashboard else None,
            "globe_url": f"/results/{short_name}/results/globe.html" if has_globe else None
        })

    def serve_studio_html(self):
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaSim Studio • 3D TN-NTN Simulation Center</title>
    <!-- Leaflet Map CSS/JS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        :root {{
            --bg-dark: #0a0f1d;
            --surface-panel: #111a2e;
            --surface-hover: #1a2744;
            --border-line: #223458;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #10b981;
            --accent-orange: #f59e0b;
            --radius-md: 8px;
            --radius-lg: 12px;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-dark); color: var(--text-main); height: 100vh; overflow: hidden; display: flex; flex-direction: column;
        }}
        header.studio-header {{
            background: var(--surface-panel); border-bottom: 1px solid var(--border-line);
            padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; z-index: 10;
        }}
        .brand {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 18px; }}
        .badge {{ background: #0284c7; color: #fff; font-size: 11px; padding: 3px 8px; border-radius: 4px; }}
        .studio-body {{ display: flex; flex: 1; overflow: hidden; }}

        /* Left Sidebar: Catalog & Config */
        .sidebar {{
            width: 380px; background: var(--surface-panel); border-right: 1px solid var(--border-line);
            display: flex; flex-direction: column; overflow-y: auto;
        }}
        .sidebar-section {{ padding: 18px; border-bottom: 1px solid var(--border-line); }}
        .section-title {{ font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--text-sub); margin-bottom: 12px; letter-spacing: 0.5px; }}
        .scenario-item {{
            background: var(--surface-hover); border: 1px solid var(--border-line); border-radius: var(--radius-md);
            padding: 12px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s ease;
        }}
        .scenario-item:hover, .scenario-item.active {{
            border-color: var(--accent-blue); background: #1f3054;
        }}
        .scenario-name {{ font-weight: 600; font-size: 14px; margin-bottom: 4px; }}
        .scenario-meta {{ font-size: 12px; color: var(--text-sub); }}

        /* Main Workspace: Map, Controls, Terminal */
        .workspace {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }}
        #map {{ height: 50%; width: 100%; border-bottom: 1px solid var(--border-line); background: #000; }}

        /* Lower Controls & Terminal Split */
        .lower-deck {{ height: 50%; display: flex; overflow: hidden; }}
        .config-deck {{ width: 50%; padding: 20px; overflow-y: auto; border-right: 1px solid var(--border-line); }}
        .terminal-deck {{ width: 50%; background: #050811; display: flex; flex-direction: column; overflow: hidden; }}
        .terminal-header {{ background: #0d1527; padding: 8px 16px; font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--border-line); display: flex; justify-content: space-between; }}
        .terminal-body {{ flex: 1; padding: 12px; font-family: monospace; font-size: 12px; color: #a5f3fc; overflow-y: auto; white-space: pre-wrap; }}

        .btn {{
            background: #0284c7; color: #fff; border: none; padding: 9px 16px; border-radius: var(--radius-md);
            font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
        }}
        .btn:hover {{ background: #0369a1; }}
        .btn-success {{ background: var(--accent-green); }}
        .btn-success:hover {{ background: #059669; }}
        .btn-secondary {{ background: var(--surface-hover); color: var(--text-main); border: 1px solid var(--border-line); }}

        .form-group {{ margin-bottom: 14px; }}
        .form-label {{ font-size: 12px; color: var(--text-sub); font-weight: 600; display: block; margin-bottom: 6px; }}
        .form-input, .form-select {{
            width: 100%; background: var(--surface-hover); border: 1px solid var(--border-line); color: var(--text-main);
            padding: 8px 12px; border-radius: var(--radius-md); font-size: 13px; outline: none;
        }}
        .button-bar {{ display: flex; gap: 10px; margin-top: 18px; }}
    </style>
</head>
<body>
    <header class="studio-header">
        <div class="brand">
            <span class="badge">NexaSphere</span>
            <span>NexaSim Studio • 3D Control Center</span>
        </div>
        <div>
            <button class="btn btn-secondary" onclick="openDashboard()">📊 Open Dashboard</button>
            <button class="btn btn-secondary" onclick="open3DGlobe()">🌐 Open 3D Globe</button>
            <button class="btn btn-success" id="runBtn" onclick="runSimulation()">▶️ Run Simulation</button>
        </div>
    </header>

    <div class="studio-body">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="sidebar-section">
                <div class="section-title">Scenario Library Catalog</div>
                <div id="scenarioList">Loading scenarios...</div>
            </div>
        </aside>

        <!-- Workspace -->
        <main class="workspace">
            <div id="map"></div>

            <div class="lower-deck">
                <div class="config-deck">
                    <div class="section-title">Scenario Parameters & Visual Customizer</div>
                    <div class="form-group">
                        <label class="form-label">Vertical Handover (VHO) Strategy</label>
                        <select class="form-select" id="cfgStrategy">
                            <option value="coverage-based">Coverage-based (Blind-spot failover)</option>
                            <option value="qos-based">QoS-based (Multi-criteria utility)</option>
                            <option value="energy-aware">Energy-aware (Battery SoC preservation)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Ka-Band Rain Rate (mm/h) - Atmospheric Attenuation</label>
                        <input type="range" class="form-input" id="cfgRain" min="0" max="60" value="15" oninput="document.getElementById('rainVal').textContent = this.value">
                        <div style="font-size: 12px; color: var(--text-sub); margin-top: 4px;">Value: <span id="rainVal">15</span> mm/h</div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Simulation Duration (seconds)</label>
                        <input type="number" class="form-input" id="cfgDuration" value="200">
                    </div>

                    <div class="button-bar">
                        <button class="btn btn-secondary" onclick="generateScenarioFiles()">⚙️ Generate Network</button>
                        <button class="btn btn-secondary" onclick="prepare3DDigitalTwin()">🛰️ Build 3D Digital Twin</button>
                    </div>
                </div>

                <div class="terminal-deck">
                    <div class="terminal-header">
                        <span>SIMULATION RUNNER LOG TERMINAL</span>
                        <span id="simStatusBadge" style="color: var(--text-sub);">Ready</span>
                    </div>
                    <div class="terminal-body" id="termLogs">// Select scenario and click 'Run Simulation' to start.</div>
                </div>
            </div>
        </main>
    </div>

    <script>
        let map = L.map('map').setView([46.5286, 10.4531], 9);
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '© OpenStreetMap, © CartoDB',
            maxZoom: 18
        }}).addTo(map);

        let currentScenarioId = 'stelvio_pass_hybrid';
        let currentBboxRect = null;
        let mapMarkers = [];

        async function loadScenarios() {{
            const res = await fetch('/api/scenarios');
            const data = await res.json();
            const list = document.getElementById('scenarioList');
            list.innerHTML = '';

            data.forEach((sc, i) => {{
                const item = document.createElement('div');
                item.className = 'scenario-item' + (i === 0 ? ' active' : '');
                item.onclick = () => selectScenario(sc, item);
                item.innerHTML = `
                    <div class="scenario-name">${{sc.name}}</div>
                    <div class="scenario-meta">${{sc.satellites}} Sats • ${{sc.gnbs}} gNB • ${{sc.vehicles}} Vehicles • ${{sc.duration_s}}s</div>
                `;
                list.appendChild(item);
                if (i === 0) selectScenario(sc, item);
            }});
        }}

        function selectScenario(sc, elem) {{
            document.querySelectorAll('.scenario-item').forEach(e => e.classList.remove('active'));
            elem.classList.add('active');
            currentScenarioId = sc.id;

            // Update Map
            if (sc.center) {{
                map.setView([sc.center[0], sc.center[1]], 10);
            }}

            if (currentBboxRect) map.removeLayer(currentBboxRect);
            mapMarkers.forEach(m => map.removeLayer(m));
            mapMarkers = [];

            if (sc.bbox) {{
                const bounds = [[sc.bbox[1], sc.bbox[0]], [sc.bbox[3], sc.bbox[2]]];
                currentBboxRect = L.rectangle(bounds, {{ color: '#38bdf8', weight: 2, fillOpacity: 0.15 }}).addTo(map);
                map.fitBounds(bounds);
            }}

            if (sc.center) {{
                const m = L.circleMarker([sc.center[0], sc.center[1]], {{ radius: 8, color: '#10b981', fillOpacity: 0.8 }}).addTo(map);
                m.bindPopup(`<b>${{sc.name}}</b><br>${{sc.area_name}}`);
                mapMarkers.push(m);
            }}

            document.getElementById('cfgDuration').value = sc.duration_s || 200;
        }}

        async function runSimulation() {{
            const btn = document.getElementById('runBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Simulating...';

            await fetch('/api/run', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ id: currentScenarioId }})
            }});

            pollStatus();
        }}

        async function pollStatus() {{
            const term = document.getElementById('termLogs');
            const badge = document.getElementById('simStatusBadge');
            const interval = setInterval(async () => {{
                const res = await fetch('/api/status');
                const state = await res.json();

                badge.textContent = state.running ? 'RUNNING...' : 'COMPLETED';
                badge.style.color = state.running ? '#f59e0b' : '#10b981';

                term.textContent = state.logs.join('\\n');
                term.scrollTop = term.scrollHeight;

                if (!state.running) {{
                    clearInterval(interval);
                    const btn = document.getElementById('runBtn');
                    btn.disabled = false;
                    btn.textContent = '▶️ Run Simulation';
                }}
            }}, 1000);
        }}

        async function generateScenarioFiles() {{
            const term = document.getElementById('termLogs');
            term.textContent = 'Generating network topology & SUMO traffic...\\n';
            const res = await fetch('/api/generate', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ id: currentScenarioId }})
            }});
            const data = await res.json();
            term.textContent += `Generated: ${{data.directory}}\\nReady to run.`;
        }}

        async function prepare3DDigitalTwin() {{
            const term = document.getElementById('termLogs');
            term.textContent = 'Building 3D Digital Twin CZML scene...\\n';
            const res = await fetch('/api/view3d', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ id: currentScenarioId }})
            }});
            const data = await res.json();
            term.textContent += `3D Digital Twin Ready: ${{data.html}}\\n`;
        }}

        async function openDashboard() {{
            const res = await fetch(`/api/results?name=${{currentScenarioId}}`);
            const data = await res.json();
            if (data.dashboard_url) {{
                window.open(data.dashboard_url, '_blank');
            }} else {{
                alert('No dashboard found. Run the simulation first.');
            }}
        }}

        async function open3DGlobe() {{
            const res = await fetch(`/api/results?name=${{currentScenarioId}}`);
            const data = await res.json();
            if (data.globe_url) {{
                window.open(data.globe_url, '_blank');
            }} else {{
                await prepare3DDigitalTwin();
                window.open(`/results/${{currentScenarioId}}/results/globe.html`, '_blank');
            }}
        }}

        window.onload = loadScenarios;
    </script>
</body>
</html>
"""
        resp = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

def run_simulation_worker(scenario_id: str):
    """Worker executed in background thread to run simulation and capture logs."""
    from tools.nexasim import resolve_scenario_yaml, resolve_generated_dir, is_inside_docker

    yaml_path = resolve_scenario_yaml(scenario_id)
    out_dir = resolve_generated_dir(scenario_id)
    short_name = out_dir.name

    # Auto-generate if needed
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
            'nexasim-run', 'bash', '/artery/tools/opp_run.sh', '-f', f"/artery/scenarios/generated/{short_name}/omnetpp.ini", '-u', 'Cmdenv'
        ]
        cwd = str(REPO_ROOT)
        env = os.environ.copy()
        env['MSYS_NO_PATHCONV'] = '1'

    with SIM_LOCK:
        SIM_STATE["logs"].append(f"[*] Starting simulation for '{scenario_id}'...")

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    for line in proc.stdout:
        with SIM_LOCK:
            SIM_STATE["logs"].append(line.rstrip('\r\n'))

    proc.wait()

    # Automatically analyze after run
    from tools.analyze_results import analyze_simulation_directory
    analyze_simulation_directory(str(out_dir), generate_dashboard=True)

    with SIM_LOCK:
        SIM_STATE["running"] = False
        SIM_STATE["exit_code"] = proc.returncode
        SIM_STATE["logs"].append(f"\n[+] Simulation finished with exit code {proc.returncode}")

def start_studio_server(port: int = 8080, open_browser: bool = False):
    """Starts the NexaSim Studio web server."""
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, StudioAPIHandler)
    url = f"http://localhost:{port}"

    print(f"\n==========================================================================")
    print(f" NexaSim Studio • Interactive Web Control Center")
    print(f" URL: {url}")
    print(f" Press Ctrl+C to stop the studio server")
    print(f"==========================================================================\n")

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NexaSim Studio server...")
        httpd.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NexaSim Studio Web Server')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind (default: 8080)')
    parser.add_argument('--open', action='store_true', help='Open studio in browser automatically')
    args = parser.parse_args()

    start_studio_server(port=args.port, open_browser=args.open)
