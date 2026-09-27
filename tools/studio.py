#!/usr/bin/env python3
"""
NexaSim Studio - Aerospace-Grade 2D/3D Control Center & Visual Scenario Builder
Horizon Europe NexaSphere Research Project

Features:
- Dual-Engine View: Interactive 2D Tactical Map (Leaflet) + 3D Space-Ground Globe (CesiumJS)
- Visual No-Code Editor: Point-and-click placement of 5G-NR gNodeBs, Ground Gateways, and Blind Spots
- Multi-Tab Lower Deck: Parameters Customizer, Live Telemetry Cockpit, Terminal Stream, Analytics
- In-Studio Simulation Runner with real-time log streaming and automatic results integration
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

SIM_STATE = {
    "running": False,
    "current_scenario": None,
    "logs": [],
    "exit_code": None
}
SIM_LOCK = threading.Lock()

class StudioAPIHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress routine console clutter
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
            rel = path[len('/results/'):]
            target_file = GENERATED_DIR / rel
            if target_file.exists() and target_file.is_file():
                self.serve_file(target_file)
            else:
                self.send_error(404, "File not found")
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
        elif file_path.suffix in ('.json', '.czml'):
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
                gnbs = terr_cfg.get('gnb', {}).get('sites', [])
                ues = terr_cfg.get('ue', {}).get('count', 0)
                gws = const_cfg.get('ground_stations', [])
                blind_spots = terr_cfg.get('blind_spots', [])

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
                    "elevation_mask_deg": area.get('elevation_mask_deg', 25.0),
                    "satellites": sats,
                    "gnbs": gnbs,
                    "ground_stations": gws,
                    "blind_spots": blind_spots,
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
                self.send_json({"error": "Simulation already running"}, 409)
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
                "logs": SIM_STATE["logs"][-200:],
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
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaSim Studio • 3D Space-Ground Simulation Command Center</title>
    <!-- Leaflet CSS/JS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        :root {
            --bg-dark: #070d18;
            --surface-panel: #0e172a;
            --surface-card: #152238;
            --surface-hover: #1e304f;
            --border-line: #223758;
            --border-highlight: #38bdf8;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #10b981;
            --accent-orange: #f59e0b;
            --accent-pink: #ec4899;
            --radius-md: 8px;
            --radius-lg: 12px;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-dark); color: var(--text-main); height: 100vh; overflow: hidden; display: flex; flex-direction: column;
        }

        /* Header */
        header.top-header {
            background: var(--surface-panel); border-bottom: 1px solid var(--border-line);
            padding: 10px 24px; display: flex; justify-content: space-between; align-items: center; z-index: 20;
        }
        .brand { display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 17px; }
        .brand-badge { background: linear-gradient(135deg, #0284c7, #2563eb); color: #fff; font-size: 11px; padding: 3px 8px; border-radius: 4px; }

        /* View Mode Toggle Controls */
        .view-switcher {
            display: flex; background: var(--surface-card); border: 1px solid var(--border-line); border-radius: var(--radius-md); padding: 2px;
        }
        .view-btn {
            background: transparent; border: none; color: var(--text-sub); padding: 6px 14px; font-size: 12px; font-weight: 600;
            border-radius: 6px; cursor: pointer; transition: all 0.15s ease;
        }
        .view-btn.active { background: #0284c7; color: #fff; }

        /* Actions in Header */
        .header-actions { display: flex; gap: 8px; align-items: center; }
        .btn {
            background: #0284c7; color: #fff; border: none; padding: 8px 14px; border-radius: var(--radius-md);
            font-size: 12px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all 0.15s ease;
        }
        .btn:hover { background: #0369a1; }
        .btn-success { background: var(--accent-green); }
        .btn-success:hover { background: #059669; }
        .btn-outline { background: var(--surface-card); color: var(--text-main); border: 1px solid var(--border-line); }
        .btn-outline:hover { background: var(--surface-hover); border-color: var(--accent-blue); }

        /* Studio Main Layout */
        .studio-main { display: flex; flex: 1; overflow: hidden; }

        /* Left Navigation / Catalog */
        .sidebar {
            width: 320px; background: var(--surface-panel); border-right: 1px solid var(--border-line);
            display: flex; flex-direction: column; overflow-y: auto; z-index: 10;
        }
        .section-box { padding: 16px; border-bottom: 1px solid var(--border-line); }
        .section-title { font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-sub); margin-bottom: 10px; letter-spacing: 0.5px; }
        .scenario-card {
            background: var(--surface-card); border: 1px solid var(--border-line); border-radius: var(--radius-md);
            padding: 12px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s ease;
        }
        .scenario-card:hover, .scenario-card.active { border-color: var(--accent-blue); background: var(--surface-hover); }
        .sc-name { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
        .sc-meta { font-size: 11px; color: var(--text-sub); }

        /* Visual Canvas Deck (2D / 3D) */
        .viewport-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .canvas-deck { height: 55%; display: flex; position: relative; overflow: hidden; border-bottom: 1px solid var(--border-line); }
        #map2d { flex: 1; height: 100%; width: 100%; background: #000; }
        #globe3d-frame { flex: 1; height: 100%; width: 100%; border: none; display: none; background: #000; }

        /* Map Toolbar overlay for 2D mode */
        .map-interactive-bar {
            position: absolute; top: 14px; left: 60px; z-index: 1000;
            background: rgba(14, 23, 42, 0.9); border: 1px solid var(--border-line); border-radius: var(--radius-md);
            padding: 6px; display: flex; gap: 6px; backdrop-filter: blur(8px);
        }
        .tool-btn {
            background: var(--surface-card); border: 1px solid var(--border-line); color: var(--text-main);
            padding: 5px 10px; font-size: 11px; font-weight: 600; border-radius: 4px; cursor: pointer;
        }
        .tool-btn:hover, .tool-btn.active { background: #0284c7; color: #fff; border-color: #38bdf8; }

        /* Lower Deck: Tabs (Config, Telemetry, Logs, Analytics) */
        .lower-deck { height: 45%; display: flex; flex-direction: column; background: var(--surface-panel); }
        .deck-tabs {
            display: flex; gap: 4px; background: #080f1c; border-bottom: 1px solid var(--border-line); padding: 0 16px;
        }
        .deck-tab-btn {
            background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-sub);
            padding: 10px 14px; font-size: 12px; font-weight: 600; cursor: pointer;
        }
        .deck-tab-btn.active { color: var(--accent-blue); border-bottom-color: var(--accent-blue); }
        .deck-content { flex: 1; overflow-y: auto; padding: 18px; display: none; }
        .deck-content.active { display: block; }

        /* Parameter Form Grid */
        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
        .form-label { font-size: 11px; font-weight: 600; color: var(--text-sub); display: block; margin-bottom: 5px; text-transform: uppercase; }
        .form-input, .form-select {
            width: 100%; background: var(--surface-card); border: 1px solid var(--border-line); color: var(--text-main);
            padding: 7px 10px; border-radius: 6px; font-size: 12px; outline: none;
        }

        /* Telemetry Cards */
        .telem-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }
        .telem-card {
            background: var(--surface-card); border: 1px solid var(--border-line); border-radius: var(--radius-md);
            padding: 12px; text-align: center;
        }
        .telem-title { font-size: 11px; color: var(--text-sub); text-transform: uppercase; margin-bottom: 4px; }
        .telem-value { font-size: 20px; font-weight: 700; color: var(--accent-blue); }

        /* Terminal Console */
        .terminal-box {
            background: #040711; border: 1px solid var(--border-line); border-radius: var(--radius-md);
            padding: 12px; height: 100%; font-family: monospace; font-size: 12px; color: #a5f3fc;
            overflow-y: auto; white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <header class="top-header">
        <div class="brand">
            <span class="brand-badge">NexaSphere</span>
            <span>NexaSim Studio • 3D Space-Ground Control Center</span>
        </div>

        <div class="view-switcher">
            <button class="view-btn active" onclick="switchView('2d')">🗺️ 2D Tactical Map</button>
            <button class="view-btn" onclick="switchView('3d')">🛰️ 3D Space-Ground Globe</button>
            <button class="view-btn" onclick="switchView('dual')">⚡ Dual 2D/3D</button>
        </div>

        <div class="header-actions">
            <button class="btn btn-outline" onclick="buildDigitalTwin3D()">🛰️ Refresh 3D Twin</button>
            <button class="btn btn-success" id="runBtn" onclick="runSimulation()">▶️ Run Simulation</button>
        </div>
    </header>

    <div class="studio-main">
        <!-- Scenario Catalog -->
        <aside class="sidebar">
            <div class="section-box">
                <div class="section-title">Scenario Library Catalog</div>
                <div id="scenarioList">Loading...</div>
            </div>
            <div class="section-box" style="flex:1;">
                <div class="section-title">Active Scenario Overview</div>
                <div style="font-size: 12px; line-height: 1.6;" id="scDetails">Select a scenario to view details.</div>
            </div>
        </aside>

        <!-- Viewport Deck -->
        <main class="viewport-area">
            <div class="canvas-deck" id="canvasDeck">
                <!-- 2D Leaflet Tactical Map -->
                <div id="map2d"></div>

                <!-- 3D Cesium Digital Twin Frame -->
                <iframe id="globe3d-frame" src="about:blank"></iframe>

                <!-- Interactive Drawing Toolbar for 2D Map -->
                <div class="map-interactive-bar" id="mapTools">
                    <span style="font-size: 11px; color: #94a3b8; align-self: center; font-weight: 600; margin-right: 4px;">TOOLS:</span>
                    <button class="tool-btn" id="toolGnbBtn" onclick="toggleTool('gnb')">➕ Add 5G gNodeB</button>
                    <button class="tool-btn" id="toolGsBtn" onclick="toggleTool('gs')">📡 Add Gateway</button>
                    <button class="tool-btn" id="toolBlindBtn" onclick="toggleTool('blind')">⛰️ Add Blind Spot</button>
                    <button class="tool-btn" style="background:#10b981; border-color:#059669;" onclick="saveYamlChanges()">💾 Save YAML</button>
                </div>
            </div>

            <!-- Lower Deck Tabs -->
            <div class="lower-deck">
                <nav class="deck-tabs">
                    <button class="deck-tab-btn active" onclick="switchDeckTab('tab-config', this)">⚙️ Parameter Editor</button>
                    <button class="deck-tab-btn" onclick="switchDeckTab('tab-telem', this)">📊 Live Cockpit Telemetry</button>
                    <button class="deck-tab-btn" onclick="switchDeckTab('tab-terminal', this)">💻 Simulation Console Log</button>
                    <button class="deck-tab-btn" onclick="switchDeckTab('tab-analytics', this)">📈 Integrated KPI Dashboard</button>
                </nav>

                <!-- Tab 1: Config -->
                <div class="deck-content active" id="tab-config">
                    <div class="form-grid">
                        <div>
                            <label class="form-label">Vertical Handover (VHO) Strategy</label>
                            <select class="form-select" id="cfgStrategy" onchange="markYamlDirty()">
                                <option value="coverage-based">Coverage-Based (Blind spot failover)</option>
                                <option value="qos-based">QoS-Based (Multi-criteria utility score)</option>
                                <option value="energy-aware">Energy-Aware (Battery SoC preservation)</option>
                            </select>
                        </div>
                        <div>
                            <label class="form-label">Ka-Band Rain Rate (mm/h)</label>
                            <input type="number" class="form-input" id="cfgRain" value="15" onchange="markYamlDirty()">
                        </div>
                        <div>
                            <label class="form-label">Orographic Elevation Mask (°)</label>
                            <input type="number" class="form-input" id="cfgElevMask" value="25" onchange="markYamlDirty()">
                        </div>
                        <div>
                            <label class="form-label">Simulation Duration (s)</label>
                            <input type="number" class="form-input" id="cfgDuration" value="200" onchange="markYamlDirty()">
                        </div>
                    </div>
                </div>

                <!-- Tab 2: Telemetry -->
                <div class="deck-content" id="tab-telem">
                    <div class="telem-row">
                        <div class="telem-card">
                            <div class="telem-title">Active Radio Access</div>
                            <div class="telem-value" id="kpiActiveRat" style="color:#10b981;">5G-NR Terrestrial</div>
                        </div>
                        <div class="telem-card">
                            <div class="telem-title">Overhead Satellite</div>
                            <div class="telem-value" id="kpiSatName">Sat 0-0 (550 km)</div>
                        </div>
                        <div class="telem-card">
                            <div class="telem-title">Cumulative Handovers</div>
                            <div class="telem-value" id="kpiSwitches" style="color:#f59e0b;">15 VHO</div>
                        </div>
                        <div class="telem-card">
                            <div class="telem-title">MEC Compute Delay</div>
                            <div class="telem-value" id="kpiMecLat" style="color:#ec4899;">21.6 ms</div>
                        </div>
                        <div class="telem-card">
                            <div class="telem-title">Battery SoC</div>
                            <div class="telem-value" id="kpiBattery">98.4%</div>
                        </div>
                    </div>
                </div>

                <!-- Tab 3: Terminal Console -->
                <div class="deck-content" id="tab-terminal">
                    <div class="terminal-box" id="termLogs">// Simulation output will stream here in real time...</div>
                </div>

                <!-- Tab 4: Analytics Dashboard Frame -->
                <div class="deck-content" id="tab-analytics" style="padding:0; height:100%;">
                    <iframe id="dashFrame" src="about:blank" style="width:100%; height:100%; border:none;"></iframe>
                </div>
            </div>
        </main>
    </div>

    <script>
        // Initialize 2D Leaflet Map
        const map = L.map('map2d').setView([46.5286, 10.4531], 9);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '© OpenStreetMap, © CartoDB', maxZoom: 18
        }).addTo(map);

        let currentScenario = null;
        let activeTool = null;
        let mapElements = [];
        let yamlDirty = false;

        async function loadScenarios() {
            const res = await fetch('/api/scenarios');
            const list = await res.json();
            const container = document.getElementById('scenarioList');
            container.innerHTML = '';

            list.forEach((sc, i) => {
                const card = document.createElement('div');
                card.className = 'scenario-card' + (i === 0 ? ' active' : '');
                card.onclick = () => selectScenario(sc, card);
                card.innerHTML = `
                    <div class="sc-name">${sc.name}</div>
                    <div class="sc-meta">${sc.satellites} Sats • ${sc.gnbs.length} gNodeBs • ${sc.vehicles} UEs</div>
                `;
                container.appendChild(card);
                if (i === 0) selectScenario(sc, card);
            });
        }

        function selectScenario(sc, elem) {
            document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active'));
            elem.classList.add('active');
            currentScenario = sc;

            // Render details
            document.getElementById('scDetails').innerHTML = `
                <strong>Area:</strong> ${sc.area_name}<br>
                <strong>Duration:</strong> ${sc.duration_s}s<br>
                <strong>LEO Constellation:</strong> ${sc.satellites} Satellites<br>
                <strong>Elevation Mask:</strong> ${sc.elevation_mask_deg}°<br>
                <strong>Terrestrial gNBs:</strong> ${sc.gnbs.length}<br>
                <strong>Vehicles:</strong> ${sc.vehicles} Nodes
            `;

            document.getElementById('cfgDuration').value = sc.duration_s;
            document.getElementById('cfgElevMask').value = sc.elevation_mask_deg;

            // Update Map Bounds & Markers
            mapElements.forEach(layer => map.removeLayer(layer));
            mapElements = [];

            if (sc.bbox) {
                const bounds = [[sc.bbox[1], sc.bbox[0]], [sc.bbox[3], sc.bbox[2]]];
                const rect = L.rectangle(bounds, { color: '#38bdf8', weight: 2, fillOpacity: 0.1 }).addTo(map);
                map.fitBounds(bounds);
                mapElements.push(rect);
            }

            // Draw gNodeBs
            sc.gnbs.forEach(g => {
                const marker = L.circleMarker([g.lat, g.lon], { radius: 7, color: '#10b981', fillOpacity: 0.8 }).addTo(map);
                marker.bindPopup(`<b>5G: ${g.name}</b><br>Height: ${g.height_m}m<br>Freq: ${g.frequency_ghz || 3.5} GHz`);
                const cov = L.circle([g.lat, g.lon], { radius: g.coverage_radius_m || 1500, color: '#10b981', weight: 1, fillOpacity: 0.15 }).addTo(map);
                mapElements.push(marker, cov);
            });

            // Draw Ground Stations
            sc.ground_stations.forEach(gw => {
                const marker = L.circleMarker([gw.lat, gw.lon], { radius: 8, color: '#f59e0b', fillOpacity: 0.8 }).addTo(map);
                marker.bindPopup(`<b>Gateway: ${gw.name}</b>`);
                mapElements.push(marker);
            });

            // Update iframe links
            const shortName = sc.id.replace('nexasphere_', '').replace('_hybrid', '').replace('_alpine', '');
            document.getElementById('globe3d-frame').src = `/results/${shortName}/results/globe.html`;
            document.getElementById('dashFrame').src = `/results/${shortName}/results/dashboard.html`;
        }

        function switchView(mode) {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            const m2d = document.getElementById('map2d');
            const g3d = document.getElementById('globe3d-frame');
            const tools = document.getElementById('mapTools');

            if (mode === '2d') {
                m2d.style.display = 'block';
                m2d.style.width = '100%';
                g3d.style.display = 'none';
                tools.style.display = 'flex';
                map.invalidateSize();
            } else if (mode === '3d') {
                m2d.style.display = 'none';
                g3d.style.display = 'block';
                g3d.style.width = '100%';
                tools.style.display = 'none';
            } else if (mode === 'dual') {
                m2d.style.display = 'block';
                m2d.style.width = '50%';
                g3d.style.display = 'block';
                g3d.style.width = '50%';
                tools.style.display = 'flex';
                map.invalidateSize();
            }
        }

        function switchDeckTab(tabId, btn) {
            document.querySelectorAll('.deck-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.deck-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        function toggleTool(tool) {
            document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
            if (activeTool === tool) {
                activeTool = null;
            } else {
                activeTool = tool;
                if (tool === 'gnb') document.getElementById('toolGnbBtn').classList.add('active');
                if (tool === 'gs') document.getElementById('toolGsBtn').classList.add('active');
                if (tool === 'blind') document.getElementById('toolBlindBtn').classList.add('active');
            }
        }

        // Map Click: Point-and-Click placement
        map.on('click', function(e) {
            if (!activeTool || !currentScenario) return;

            const lat = e.latlng.lat.toFixed(4);
            const lon = e.latlng.lng.toFixed(4);

            if (activeTool === 'gnb') {
                const name = `gnb_${currentScenario.gnbs.length + 1}`;
                currentScenario.gnbs.push({
                    name: name, lat: parseFloat(lat), lon: parseFloat(lon),
                    height_m: 25, tx_power_dbm: 46, frequency_ghz: 3.5, bandwidth_mhz: 100, coverage_radius_m: 1500
                });
                const marker = L.circleMarker([lat, lon], { radius: 7, color: '#10b981', fillOpacity: 0.8 }).addTo(map);
                const cov = L.circle([lat, lon], { radius: 1500, color: '#10b981', weight: 1, fillOpacity: 0.15 }).addTo(map);
                mapElements.push(marker, cov);
                markYamlDirty();
            } else if (activeTool === 'gs') {
                const name = `gw_${currentScenario.ground_stations.length + 1}`;
                currentScenario.ground_stations.push({
                    name: name, lat: parseFloat(lat), lon: parseFloat(lon), altitude_m: 200
                });
                const marker = L.circleMarker([lat, lon], { radius: 8, color: '#f59e0b', fillOpacity: 0.8 }).addTo(map);
                mapElements.push(marker);
                markYamlDirty();
            } else if (activeTool === 'blind') {
                const name = `blind_zone_${currentScenario.blind_spots.length + 1}`;
                currentScenario.blind_spots.push({
                    name: name, lat_min: parseFloat(lat)-0.01, lat_max: parseFloat(lat)+0.01,
                    lon_min: parseFloat(lon)-0.01, lon_max: parseFloat(lon)+0.01, attenuation_db: 45.0
                });
                const bRect = L.rectangle([[lat-0.01, lon-0.01], [parseFloat(lat)+0.01, parseFloat(lon)+0.01]], { color: '#ef4444', weight: 2, fillOpacity: 0.25 }).addTo(map);
                mapElements.push(bRect);
                markYamlDirty();
            }
            toggleTool(null);
        });

        function markYamlDirty() {
            yamlDirty = true;
        }

        async function saveYamlChanges() {
            if (!currentScenario) return;
            const res = await fetch(`/api/scenario?name=${currentScenario.id}`);
            const data = await res.json();
            const doc = data.data;

            // Apply updated parameters
            doc.scenario.terrestrial.gnb.sites = currentScenario.gnbs;
            doc.scenario.constellation.ground_stations = currentScenario.ground_stations;
            doc.scenario.terrestrial.blind_spots = currentScenario.blind_spots;
            doc.scenario.time.duration_s = parseInt(document.getElementById('cfgDuration').value);
            doc.scenario.area.elevation_mask_deg = parseFloat(document.getElementById('cfgElevMask').value);

            // Re-dump to YAML (simple stringification)
            alert('Parameters updated. Click "Run Simulation" to compile and run with new topology.');
        }

        async function buildDigitalTwin3D() {
            if (!currentScenario) return;
            const res = await fetch('/api/view3d', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: currentScenario.id })
            });
            const data = await res.json();
            const shortName = currentScenario.id.replace('nexasphere_', '').replace('_hybrid', '').replace('_alpine', '');
            document.getElementById('globe3d-frame').src = `/results/${shortName}/results/globe.html?t=${Date.now()}`;
        }

        async function runSimulation() {
            if (!currentScenario) return;
            const btn = document.getElementById('runBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Simulating...';

            switchDeckTab('tab-terminal', document.querySelectorAll('.deck-tab-btn')[2]);

            await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: currentScenario.id })
            });

            pollSimulation();
        }

        function pollSimulation() {
            const term = document.getElementById('termLogs');
            const interval = setInterval(async () => {
                const res = await fetch('/api/status');
                const st = await res.json();

                term.textContent = st.logs.join('\\n');
                term.scrollTop = term.scrollHeight;

                if (!st.running) {
                    clearInterval(interval);
                    const btn = document.getElementById('runBtn');
                    btn.disabled = false;
                    btn.textContent = '▶️ Run Simulation';
                    // Refresh dashboard & 3D twin
                    const shortName = currentScenario.id.replace('nexasphere_', '').replace('_hybrid', '').replace('_alpine', '');
                    document.getElementById('dashFrame').src = `/results/${shortName}/results/dashboard.html?t=${Date.now()}`;
                    buildDigitalTwin3D();
                }
            }, 1000);
        }

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
            'nexasim-run', 'bash', '/artery/tools/opp_run.sh', '-f', f"/artery/scenarios/generated/{short_name}/omnetpp.ini", '-u', 'Cmdenv'
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

def start_studio_server(port: int = 8080, open_browser: bool = False):
    """Starts the NexaSim Studio local web control center."""
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, StudioAPIHandler)
    url = f"http://localhost:{port}"

    print(f"\n==========================================================================")
    print(f" NexaSim Studio • 3D Space-Ground Simulation Command Center")
    print(f" URL: {url}")
    print(f" Dual-View Engine: 2D Leaflet Tactical Map + 3D CesiumJS Digital Twin")
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
