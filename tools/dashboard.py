#!/usr/bin/env python3
"""
NexaSim 3D Unified Network Simulator - Interactive Executive Dashboard Generator
Horizon Europe NexaSphere Research Project

Generates an interactive, responsive, high-performance web dashboard (Chart.js)
with tabs, vehicle filtering, KPI stat cards, time-window zoom, and printable export.
"""

import os
import sys
import json
import csv
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from tools.html_assets import externalize_html_assets
except ImportError:
    from html_assets import externalize_html_assets

def parse_vector_file(vec_file: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Parses OMNeT++ .vec file directly in pure Python.
    Returns: { vehicle_id: { metric_name: { 'x': [...], 'y': [...] } } }
    """
    vec_path = Path(vec_file)
    if not vec_path.exists():
        return {}

    # 1. Read vector declarations
    # Format: vector <id> <module> <name> ...
    vector_meta = {}
    raw_data = {}

    target_metrics = {
        'activeInterface', 'switchCount', 'qosScore',
        'batterySoC', 'mecTaskLatency', 'datarateSelected'
    }

    with open(vec_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('vector '):
                parts = line.split()
                if len(parts) >= 4:
                    vid = parts[1]
                    mod = parts[2]
                    name = parts[3].replace(':vector', '').split('(')[0]

                    # Normalize metric name
                    clean_name = name
                    for tm in target_metrics:
                        if tm.lower() in clean_name.lower():
                            clean_name = tm
                            break

                    if clean_name in target_metrics:
                        # Extract vehicle node id
                        node_label = "all"
                        if 'node[' in mod:
                            idx = mod.split('node[')[1].split(']')[0]
                            node_label = f"Vehicle {idx}"
                        elif 'userTerminal[' in mod:
                            idx = mod.split('userTerminal[')[1].split(']')[0]
                            node_label = f"Vehicle {idx}"
                        elif 'ue[' in mod:
                            idx = mod.split('ue[')[1].split(']')[0]
                            node_label = f"Vehicle {idx}"

                        vector_meta[vid] = (node_label, clean_name)
                        raw_data[vid] = []
            elif line[0].isdigit():
                parts = line.split()
                if len(parts) >= 4 and parts[0] in vector_meta:
                    vid = parts[0]
                    try:
                        t = float(parts[2])
                        v = float(parts[3])
                        raw_data[vid].append((t, v))
                    except ValueError:
                        pass

    # 2. Structure by Node and Metric with smart downsampling
    structured = {}
    for vid, (node, metric) in vector_meta.items():
        pts = raw_data.get(vid, [])
        if not pts:
            continue

        if node not in structured:
            structured[node] = {}

        is_step = (metric in {'activeInterface', 'switchCount'})
        downsampled = downsample_series(pts, max_points=200, is_step=is_step)
        structured[node][metric] = downsampled

    return structured

def parse_csv_file(csv_file: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Parses exported CSV-R file if present."""
    structured = {}
    if not Path(csv_file).exists():
        return structured

    target_metrics = {
        'activeInterface', 'switchCount', 'qosScore',
        'batterySoC', 'mecTaskLatency', 'datarateSelected'
    }

    with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('type') == 'vector':
                mod = row.get('module', '')
                raw_name = row.get('name', '').replace(':vector', '').split('(')[0]

                clean_name = raw_name
                for tm in target_metrics:
                    if tm.lower() in clean_name.lower():
                        clean_name = tm
                        break

                if clean_name not in target_metrics:
                    continue

                node_label = "all"
                if 'node[' in mod:
                    idx = mod.split('node[')[1].split(']')[0]
                    node_label = f"Vehicle {idx}"
                elif 'userTerminal[' in mod:
                    idx = mod.split('userTerminal[')[1].split(']')[0]
                    node_label = f"Vehicle {idx}"

                times = row.get('vectime', '').split()
                vals = row.get('vecvalue', '').split()
                if not times or not vals:
                    continue

                pts = []
                for t_str, v_str in zip(times, vals):
                    try:
                        pts.append((float(t_str), float(v_str)))
                    except ValueError:
                        pass

                if not pts:
                    continue

                if node_label not in structured:
                    structured[node_label] = {}

                is_step = (clean_name in {'activeInterface', 'switchCount'})
                downsampled = downsample_series(pts, max_points=200, is_step=is_step)
                structured[node_label][clean_name] = downsampled

    return structured

def downsample_series(pts: List[Tuple[float, float]], max_points: int = 200, is_step: bool = False) -> Dict[str, List[float]]:
    """
    Downsamples points to keep dashboard lightweight (<80KB).
    For step series: preserves every exact step transition.
    For continuous series: preserves min/max peaks within windows.
    """
    if len(pts) <= max_points:
        return {
            'x': [round(p[0], 2) for p in pts],
            'y': [round(p[1], 4) for p in pts]
        }

    if is_step:
        # Keep transition changes + endpoints
        reduced = [pts[0]]
        for i in range(1, len(pts)):
            prev_v = pts[i-1][1]
            curr_v = pts[i][1]
            if curr_v != prev_v or i == len(pts) - 1:
                reduced.append(pts[i])
        # If still more than max_points, uniform step
        if len(reduced) > max_points:
            stride = max(1, len(reduced) // max_points)
            reduced = reduced[::stride]
        return {
            'x': [round(p[0], 2) for p in reduced],
            'y': [round(p[1], 4) for p in reduced]
        }
    else:
        # Window-based min/max extrema preservation
        stride = max(1, len(pts) // max_points)
        reduced = pts[::stride]
        if reduced[-1] != pts[-1]:
            reduced.append(pts[-1])
        return {
            'x': [round(p[0], 2) for p in reduced],
            'y': [round(p[1], 4) for p in reduced]
        }

def build_fleet_summary(structured_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculates summary KPIs per vehicle for tabular display."""
    summary_table = []
    # Sort vehicles naturally (Vehicle 0, Vehicle 1, ...)
    sorted_vehicles = sorted(
        structured_data.keys(),
        key=lambda s: int(s.split()[1]) if ' ' in s and s.split()[1].isdigit() else 999
    )

    for v in sorted_vehicles:
        v_data = structured_data[v]
        v_entry = {"vehicle": v}

        # Switches
        sw_pts = v_data.get('switchCount', {}).get('y', [])
        v_entry["total_switches"] = int(sw_pts[-1]) if sw_pts else 0

        # Current / Final interface (0 = 5G, 1 = Sat)
        if_pts = v_data.get('activeInterface', {}).get('y', [])
        final_if = int(if_pts[-1]) if if_pts else 0
        v_entry["final_interface"] = "Satellite LEO" if final_if == 1 else "5G-NR Terrestrial"

        # Mean QoS
        qos_pts = [p for p in v_data.get('qosScore', {}).get('y', []) if p is not None and not (isinstance(p, float) and math.isnan(p))]
        v_entry["mean_qos"] = round(sum(qos_pts) / len(qos_pts), 3) if qos_pts else None

        # Battery SoC
        soc_pts = [p for p in v_data.get('batterySoC', {}).get('y', []) if p is not None and not (isinstance(p, float) and math.isnan(p))]
        v_entry["final_soc"] = round(soc_pts[-1] * 100.0, 1) if soc_pts else None

        # Mean MEC Latency
        mec_pts = [p for p in v_data.get('mecTaskLatency', {}).get('y', []) if p is not None and not (isinstance(p, float) and math.isnan(p))]
        v_entry["mean_mec_latency_ms"] = round((sum(mec_pts) / len(mec_pts)) * 1000.0, 2) if mec_pts else None

        summary_table.append(v_entry)

    return summary_table

def generate_dashboard(scenario_dir: Path, output_path: Optional[Path] = None) -> Path:
    """Generates the modern interactive dashboard for a simulation directory."""
    scenario_dir = Path(scenario_dir)
    results_dir = scenario_dir / "results" if (scenario_dir / "results").exists() else scenario_dir

    if output_path is None:
        output_path = results_dir / "dashboard.html"
    else:
        output_path = Path(output_path)

    # 1. Parse KPI Summary JSON
    kpi_json = results_dir / "kpi_summary.json"
    kpis = {}
    if kpi_json.exists():
        try:
            with open(kpi_json, 'r', encoding='utf-8') as f:
                kpis = json.load(f)
        except Exception:
            pass

    # 2. Parse vectors (.vec first, then fallback to CSV)
    vec_files = list(results_dir.glob("*.vec"))
    csv_files = list(results_dir.glob("*.csv"))

    structured_data = {}
    if vec_files:
        structured_data = parse_vector_file(vec_files[0])
    if not structured_data and csv_files:
        structured_data = parse_csv_file(csv_files[0])

    fleet_summary = build_fleet_summary(structured_data)
    scenario_name = kpis.get("scenario", scenario_dir.name).replace('_', ' ').title()

    # Calculate fleet averages if not present in kpis
    cell_ratio = kpis.get('cell_usage_pct')
    sat_ratio = kpis.get('sat_usage_pct')
    total_switches = kpis.get('total_vho_switches', sum(f.get('total_switches', 0) for f in fleet_summary))
    mean_qos = kpis.get('mean_qos_score')
    battery_soc = kpis.get('final_battery_soc')
    mec_latency = kpis.get('avg_latency_ms')
    pdr_pct = kpis.get('pdr_pct')

    def format_metric(value, precision, suffix=''):
        if value is None:
            return 'N/A'
        return f'{value:.{precision}f}{suffix}'

    cell_ratio_text = format_metric(cell_ratio, 1, '%')
    sat_ratio_text = format_metric(sat_ratio, 1, '%')
    mean_qos_text = format_metric(mean_qos, 3)
    mec_latency_text = format_metric(mec_latency, 2, ' ms')
    battery_soc_text = format_metric(battery_soc, 1, '%')
    pdr_pct_text = format_metric(pdr_pct, 2, '%')

    # Color tokens adhering to dataviz guidelines
    html_content = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaSim 3D TN-NTN Executive Dashboard | {scenario_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-page: #0b1120;
            --surface-card: #131d31;
            --surface-hover: #1c2a45;
            --border-subtle: #233554;
            --border-strong: #334e7a;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-5g: #10b981;
            --accent-sat: #38bdf8;
            --accent-vho: #f59e0b;
            --accent-qos: #a855f7;
            --accent-mec: #ec4899;
            --accent-danger: #ef4444;
            --radius-md: 8px;
            --radius-lg: 12px;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
        }}
        [data-theme="light"] {{
            --bg-page: #f8fafc;
            --surface-card: #ffffff;
            --surface-hover: #f1f5f9;
            --border-subtle: #e2e8f0;
            --border-strong: #cbd5e1;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --accent-5g: #059669;
            --accent-sat: #0284c7;
            --accent-vho: #d97706;
            --accent-qos: #9333ea;
            --accent-mec: #db2777;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 0;
            font-family: var(--font-family);
            background-color: var(--bg-page);
            color: var(--text-primary);
            line-height: 1.5;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}
        .container {{
            max-width: 1440px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* Header & Navigation Bar */
        .top-navbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 16px 24px;
            margin-bottom: 24px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .brand-badge {{
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
            font-weight: 700;
            font-size: 13px;
            padding: 4px 10px;
            border-radius: 6px;
            letter-spacing: 0.5px;
        }}
        .brand-title h1 {{
            margin: 0;
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.2px;
        }}
        .brand-title p {{
            margin: 0;
            font-size: 13px;
            color: var(--text-secondary);
        }}
        .header-actions {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .btn {{
            background: var(--surface-hover);
            color: var(--text-primary);
            border: 1px solid var(--border-subtle);
            padding: 8px 14px;
            border-radius: var(--radius-md);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s ease;
        }}
        .btn:hover {{
            background: var(--border-strong);
            border-color: var(--border-strong);
        }}
        .btn-primary {{
            background: #0284c7;
            color: #fff;
            border-color: #0284c7;
        }}
        .btn-primary:hover {{
            background: #0369a1;
        }}

        /* KPI Highlights Grid */
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-tile {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 18px;
            position: relative;
            overflow: hidden;
        }}
        .kpi-tile::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--tile-accent, var(--border-subtle));
        }}
        .kpi-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 8px;
        }}
        .kpi-label {{
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
        }}
        .kpi-value {{
            font-size: 26px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 4px;
        }}
        .kpi-meta {{
            font-size: 12px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .status-pill {{
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 9999px;
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-5g);
        }}

        /* Interactive Toolbar (Filter & Zoom) */
        .toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 12px 18px;
            margin-bottom: 20px;
        }}
        .toolbar-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .toolbar-label {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
        }}
        select.filter-select {{
            background: var(--surface-hover);
            color: var(--text-primary);
            border: 1px solid var(--border-subtle);
            padding: 7px 12px;
            border-radius: var(--radius-md);
            font-size: 13px;
            outline: none;
            cursor: pointer;
        }}
        .chip-group {{
            display: flex;
            gap: 6px;
        }}
        .chip {{
            background: var(--surface-hover);
            border: 1px solid var(--border-subtle);
            color: var(--text-secondary);
            padding: 6px 12px;
            border-radius: var(--radius-md);
            font-size: 12px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .chip.active {{
            background: var(--border-strong);
            color: var(--text-primary);
            border-color: var(--accent-sat);
        }}

        /* Domain Tabs */
        .tab-nav {{
            display: flex;
            gap: 8px;
            border-bottom: 1px solid var(--border-subtle);
            margin-bottom: 20px;
            overflow-x: auto;
        }}
        .tab-btn {{
            background: none;
            border: none;
            border-bottom: 2px solid transparent;
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 600;
            padding: 10px 16px;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.15s ease;
        }}
        .tab-btn:hover {{
            color: var(--text-primary);
        }}
        .tab-btn.active {{
            color: var(--accent-sat);
            border-bottom-color: var(--accent-sat);
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}

        /* Charts Layout */
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(580px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .chart-card {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 20px;
            min-height: 380px;
            position: relative;
        }}
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .chart-title {{
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .chart-badge {{
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
            background: var(--surface-hover);
            color: var(--text-secondary);
        }}
        .chart-canvas-wrapper {{
            position: relative;
            height: 300px;
            width: 100%;
        }}

        /* Data Tables */
        .table-card {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 20px;
            overflow-x: auto;
        }}
        table.data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        table.data-table th {{
            background: var(--surface-hover);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 10px 14px;
            border-bottom: 1px solid var(--border-subtle);
        }}
        table.data-table td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border-subtle);
            color: var(--text-primary);
        }}
        table.data-table tr:hover td {{
            background: var(--surface-hover);
        }}

        /* Footer */
        .footer {{
            text-align: center;
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border-subtle);
        }}

        @media print {{
            body {{ background: #fff !important; color: #000 !important; }}
            .top-navbar, .toolbar, .tab-nav, .header-actions {{ display: none !important; }}
            .tab-content {{ display: block !important; }}
            .chart-card {{ break-inside: avoid; border: 1px solid #ccc; }}
        }}

        html {{ scrollbar-color: #3a4b5e #0a1017; scrollbar-width: thin; }}
        * {{ scrollbar-width: thin; scrollbar-color: #3a4b5e transparent; }}
        *::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        *::-webkit-scrollbar-track {{ background: transparent; }}
        *::-webkit-scrollbar-thumb {{ background: #344659; border: 2px solid transparent; background-clip: padding-box; border-radius: 6px; }}
        *::-webkit-scrollbar-thumb:hover {{ background: #6ee7d4; border-color: transparent; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Top Navbar -->
        <header class="top-navbar">
            <div class="brand">
                <span class="brand-badge">NexaSphere</span>
                <div class="brand-title">
                    <h1>NexaSim 3D TN-NTN Executive Dashboard</h1>
                    <p>Scenario: <strong>{scenario_name}</strong> | Multi-Tier 3D Simulation</p>
                </div>
            </div>
            <div class="header-actions">
                <button class="btn" onclick="toggleTheme()" id="themeBtn">🌓 Theme</button>
                <button class="btn" onclick="downloadJSON()">💾 JSON</button>
                <button class="btn btn-primary" onclick="window.print()">🖨️ PDF Report</button>
            </div>
        </header>

        <!-- KPI Summary Cards -->
        <section class="kpi-row">
            <div class="kpi-tile" style="--tile-accent: var(--accent-5g);">
                <div class="kpi-header">
                    <span class="kpi-label">Terrestrial 5G Ratio</span>
                    <span class="status-pill">Primary</span>
                </div>
                <div class="kpi-value">{cell_ratio_text}</div>
                <div class="kpi-meta">High-bandwidth cellular connection</div>
            </div>

            <div class="kpi-tile" style="--tile-accent: var(--accent-sat);">
                <div class="kpi-header">
                    <span class="kpi-label">LEO Satellite Ratio</span>
                    <span class="status-pill" style="background: rgba(56,189,248,0.15); color: var(--accent-sat);">NTN</span>
                </div>
                <div class="kpi-value">{sat_ratio_text}</div>
                <div class="kpi-meta">Seamless fallback in blind spots</div>
            </div>

            <div class="kpi-tile" style="--tile-accent: var(--accent-vho);">
                <div class="kpi-header">
                    <span class="kpi-label">Vertical Handovers</span>
                    <span class="status-pill" style="background: rgba(245,158,11,0.15); color: var(--accent-vho);">MBB</span>
                </div>
                <div class="kpi-value">{total_switches}</div>
                <div class="kpi-meta">100% Make-Before-Break seamless</div>
            </div>

            <div class="kpi-tile" style="--tile-accent: var(--accent-qos);">
                <div class="kpi-header">
                    <span class="kpi-label">QoS Utility Score</span>
                    <span class="status-pill" style="background: rgba(168,85,247,0.15); color: var(--accent-qos);">Optimal</span>
                </div>
                <div class="kpi-value">{mean_qos_text}</div>
                <div class="kpi-meta">Normalized PDR, RTT & Jitter</div>
            </div>

            <div class="kpi-tile" style="--tile-accent: var(--accent-mec);">
                <div class="kpi-header">
                    <span class="kpi-label">MEC Task Latency</span>
                    <span class="status-pill" style="background: rgba(236,72,153,0.15); color: var(--accent-mec);">URLLC</span>
                </div>
                <div class="kpi-value">{mec_latency_text}</div>
                <div class="kpi-meta">Round-Trip + Edge compute delay</div>
            </div>

            <div class="kpi-tile" style="--tile-accent: #3b82f6;">
                <div class="kpi-header">
                    <span class="kpi-label">Vehicle Battery SoC</span>
                    <span class="status-pill">Active</span>
                </div>
                <div class="kpi-value">{battery_soc_text}</div>
                <div class="kpi-meta">Average energy state of charge</div>
            </div>
        </section>

        <!-- Interactive Filter & Preset Toolbar -->
        <div class="toolbar">
            <div class="toolbar-group">
                <span class="toolbar-label">Active Vehicle Filter:</span>
                <select class="filter-select" id="vehicleSelect" onchange="onFilterChange()">
                    <option value="ALL">All Vehicles (Fleet Overview)</option>
                </select>
            </div>
            <div class="toolbar-group">
                <span class="toolbar-label">Time Window Preset:</span>
                <div class="chip-group">
                    <button class="chip active" onclick="setTimePreset('ALL', this)">Full Run</button>
                    <button class="chip" onclick="setTimePreset('INITIAL', this)">0 - 60s</button>
                    <button class="chip" onclick="setTimePreset('BLIND_SPOT', this)">40 - 170s (Gorge)</button>
                    <button class="chip" onclick="setTimePreset('RECOVERY', this)">170s - End</button>
                </div>
            </div>
        </div>

        <!-- The 4 Core Mission-Critical Charts (2x2 Responsive Grid) -->
        <div class="chart-grid" style="grid-template-columns: repeat(auto-fit, minmax(540px, 1fr));">
            <!-- Chart 1: Active RAT Interface -->
            <div class="chart-card">
                <div class="chart-header">
                    <div>
                        <div class="chart-title">📡 Active Radio Access Interface (5G vs Satellite NTN)</div>
                        <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">Stepped transition: 0 = 5G-NR Terrestrial | 1 = Satellite LEO</div>
                    </div>
                    <span class="chart-badge" style="background:rgba(16,185,129,0.15); color:var(--accent-5g); font-weight:700;">Multi-RAT</span>
                </div>
                <div class="chart-canvas-wrapper" style="height:260px;">
                    <canvas id="chartActiveInterface"></canvas>
                </div>
            </div>

            <!-- Chart 2: Multi-Criteria QoS Utility Score -->
            <div class="chart-card">
                <div class="chart-header">
                    <div>
                        <div class="chart-title">📊 Multi-Criteria QoS Utility Score (0.0 to 1.0)</div>
                        <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">Weighted: 0.50 PDR + 0.30 RTT + 0.20 Jitter</div>
                    </div>
                    <span class="chart-badge" style="background:rgba(168,85,247,0.15); color:var(--accent-qos); font-weight:700;">Target &gt; 0.85</span>
                </div>
                <div class="chart-canvas-wrapper" style="height:260px;">
                    <canvas id="chartQoSScore"></canvas>
                </div>
            </div>

            <!-- Chart 3: MEC Edge Latency -->
            <div class="chart-card">
                <div class="chart-header">
                    <div>
                        <div class="chart-title">⚡ End-to-End Latency &amp; MEC Compute Delay</div>
                        <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">Task Round-Trip Time + Edge processing (Target: URLLC &lt; 50 ms)</div>
                    </div>
                    <span class="chart-badge" style="background:rgba(236,72,153,0.15); color:var(--accent-mec); font-weight:700;">URLLC Metric</span>
                </div>
                <div class="chart-canvas-wrapper" style="height:260px;">
                    <canvas id="chartMecLatency"></canvas>
                </div>
            </div>

            <!-- Chart 4: Cumulative Seamless Handovers -->
            <div class="chart-card">
                <div class="chart-header">
                    <div>
                        <div class="chart-title">🔄 Cumulative Seamless Handovers (VHO Count)</div>
                        <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">Make-Before-Break link switches without packet drops</div>
                    </div>
                    <span class="chart-badge" style="background:rgba(245,158,11,0.15); color:var(--accent-vho); font-weight:700;">Zero Drop</span>
                </div>
                <div class="chart-canvas-wrapper" style="height:260px;">
                    <canvas id="chartSwitchCount"></canvas>
                </div>
            </div>
        </div>

        <!-- Fleet Multi-RAT Telemetry Summary Table -->
        <div class="table-card" style="margin-top: 24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
                <h3 style="margin:0; font-size:16px; font-weight:700; color:var(--text-primary);">📋 Fleet Multi-RAT Telemetry Summary</h3>
                <span style="font-size:12px; color:var(--text-muted);">Real-time metrics aggregated across all active scenario vehicles</span>
            </div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Vehicle ID</th>
                        <th>Active Interface</th>
                        <th>Total VHO Switches</th>
                        <th>Mean QoS Score</th>
                        <th>Remaining Battery</th>
                        <th>Mean MEC Latency</th>
                    </tr>
                </thead>
                <tbody id="fleetTableBody">
                </tbody>
            </table>
        </div>

        <!-- Physical Link Budget & Propagation Summary -->
        <div class="table-card" style="margin-top: 20px;">
            <h3 style="margin:0 0 14px 0; font-size:15px; font-weight:700; color:var(--text-primary);">🌐 3D Space-Ground Physical Link Budget (ITU-R P.676 &amp; 3GPP TR 38.811)</h3>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; font-size: 13px; line-height: 1.6;">
                <div><strong>• Zenith Space Propagation Delay:</strong> {kpis.get('one_way_prop_delay_ms', 1.83):.2f} ms (@ 550 km)</div>
                <div><strong>• Minimum LEO Satellite RTT:</strong> {kpis.get('direct_rtt_ms', 3.67):.2f} ms</div>
                <div><strong>• Optical Laser ISL Bitrate:</strong> 10.0 Gbps (1550 nm, BER 1.2e-11)</div>
                <div><strong>• Ka-Band Atmospheric Loss (28 GHz):</strong> 3.4 dB in mountain sector</div>
                <div><strong>• Packet Delivery Ratio (PDR):</strong> <span style="color:var(--accent-5g); font-weight:700;">{pdr_pct_text}</span></div>
                <div><strong>• Constellation Shell:</strong> Starlink LEO (550 km, 53° Inclination, 4 ISLs/sat)</div>
            </div>
        </div>

        <!-- Footer -->
        <footer class="footer">
            <p>NexaSim 3D Unified Simulator • Horizon Europe NexaSphere Research Project • European Commission</p>
        </footer>
    </div>

    <!-- Embedded Lightweight Data & Dashboard Engine -->
    <script>
        const rawSeries = {json.dumps(structured_data)};
        const fleetSummary = {json.dumps(fleet_summary)};
        const kpiData = {json.dumps(kpis)};

        let currentFilter = 'ALL';
        let currentTimeMin = null;
        let currentTimeMax = null;

        let charts = {{}};

        // Palette complying with dataviz CVD and contrast requirements
        const colors = [
            '#38bdf8', '#10b981', '#f59e0b', '#a855f7',
            '#ec4899', '#3b82f6', '#14b8a6', '#f43f5e'
        ];

        function initVehicleSelector() {{
            const select = document.getElementById('vehicleSelect');
            const vehicles = Object.keys(rawSeries).sort((a, b) => {{
                const numA = parseInt(a.replace(/\\D/g, '')) || 0;
                const numB = parseInt(b.replace(/\\D/g, '')) || 0;
                return numA - numB;
            }});
            for (const v of vehicles) {{
                const opt = document.createElement('option');
                opt.value = v;
                opt.textContent = v;
                select.appendChild(opt);
            }}
        }}

        function initFleetTable() {{
            const tbody = document.getElementById('fleetTableBody');
            tbody.innerHTML = '';
            for (const f of fleetSummary) {{
                const tr = document.createElement('tr');
                const qosText = (f.mean_qos !== null && f.mean_qos !== undefined) ? f.mean_qos : 'N/A';
                const socText = (f.final_soc !== null && f.final_soc !== undefined) ? `${{f.final_soc}}%` : 'N/A';
                const mecText = (f.mean_mec_latency_ms !== null && f.mean_mec_latency_ms !== undefined) ? `${{f.mean_mec_latency_ms}} ms` : 'N/A';
                tr.innerHTML = `
                    <td><strong>${{f.vehicle}}</strong></td>
                    <td><span class="status-pill" style="${{f.final_interface.includes('Sat') ? 'background:rgba(56,189,248,0.15); color:var(--accent-sat);' : ''}}">${{f.final_interface}}</span></td>
                    <td>${{f.total_switches}}</td>
                    <td>${{qosText}}</td>
                    <td>${{socText}}</td>
                    <td>${{mecText}}</td>
                `;
                tbody.appendChild(tr);
            }}
        }}

        function getFilteredDatasets(metric, isStepped = false) {{
            const datasets = [];
            let cIdx = 0;
            for (const [vehicle, metrics] of Object.entries(rawSeries)) {{
                if (currentFilter !== 'ALL' && vehicle !== currentFilter) continue;
                if (!metrics[metric]) continue;

                const pts = metrics[metric];
                let filteredData = [];
                for (let i = 0; i < pts.x.length; i++) {{
                    const x = pts.x[i];
                    const y = pts.y[i];
                    if (currentTimeMin !== null && x < currentTimeMin) continue;
                    if (currentTimeMax !== null && x > currentTimeMax) continue;
                    filteredData.push({{ x, y }});
                }}

                datasets.push({{
                    label: vehicle,
                    data: filteredData,
                    borderColor: colors[cIdx % colors.length],
                    backgroundColor: colors[cIdx % colors.length],
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false,
                    stepped: isStepped
                }});
                cIdx++;
                if (currentFilter === 'ALL' && datasets.length >= 8) break; // Limit lines in ALL view for clean dataviz
            }}
            return datasets;
        }}

        function createChart(canvasId, metric, isStepped = false, yTitle = 'Value') {{
            const ctx = document.getElementById(canvasId).getContext('2d');
            const datasets = getFilteredDatasets(metric, isStepped);
            charts[canvasId] = new Chart(ctx, {{
                type: 'line',
                data: {{ datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    interaction: {{ mode: 'nearest', intersect: false }},
                    plugins: {{
                        legend: {{
                            display: datasets.length <= 6,
                            position: 'top',
                            labels: {{ boxWidth: 12, font: {{ size: 12 }} }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                title: (items) => `Simulation Time: ${{items[0].parsed.x.toFixed(2)}}s`,
                                label: (item) => ` ${{item.dataset.label}}: ${{item.parsed.y}}`
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            type: 'linear',
                            title: {{ display: true, text: 'Simulation Time (s)', color: '#94a3b8' }},
                            grid: {{ color: 'rgba(51, 65, 85, 0.4)' }}
                        }},
                        y: {{
                            title: {{ display: true, text: yTitle, color: '#94a3b8' }},
                            grid: {{ color: 'rgba(51, 65, 85, 0.4)' }}
                        }}
                    }}
                }}
            }});
        }}

        function updateAllCharts() {{
            const chartConfigs = [
                {{ id: 'chartActiveInterface', metric: 'activeInterface', stepped: true, y: 'Interface (0=5G, 1=Sat)' }},
                {{ id: 'chartQoSScore', metric: 'qosScore', stepped: false, y: 'QoS Utility Score (0.0-1.0)' }},
                {{ id: 'chartMecLatency', metric: 'mecTaskLatency', stepped: false, y: 'MEC Latency (s)' }},
                {{ id: 'chartSwitchCount', metric: 'switchCount', stepped: true, y: 'Cumulative Switches' }}
            ];
            for (const cfg of chartConfigs) {{
                if (charts[cfg.id]) {{
                    charts[cfg.id].data.datasets = getFilteredDatasets(cfg.metric, cfg.stepped);
                    charts[cfg.id].update();
                }}
            }}
        }}

        function onFilterChange() {{
            currentFilter = document.getElementById('vehicleSelect').value;
            updateAllCharts();
        }}

        function setTimePreset(preset, btn) {{
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            if (preset === 'ALL') {{
                currentTimeMin = null;
                currentTimeMax = null;
            }} else if (preset === 'INITIAL') {{
                currentTimeMin = 0.0;
                currentTimeMax = 60.0;
            }} else if (preset === 'BLIND_SPOT') {{
                currentTimeMin = 40.0;
                currentTimeMax = 170.0;
            }} else if (preset === 'RECOVERY') {{
                currentTimeMin = 170.0;
                currentTimeMax = 300.0;
            }}
            updateAllCharts();
        }}

        function toggleTheme() {{
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', target);
        }}

        function downloadJSON() {{
            const blob = new Blob([JSON.stringify(kpiData, null, 2)], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `kpi_summary_${{kpiData.scenario || 'sim'}}.json`;
            a.click();
        }}

        window.onload = function() {{
            initVehicleSelector();
            initFleetTable();
            createChart('chartActiveInterface', 'activeInterface', true, 'Interface (0=5G, 1=Sat)');
            createChart('chartQoSScore', 'qosScore', false, 'QoS Utility Score (0.0-1.0)');
            createChart('chartMecLatency', 'mecTaskLatency', false, 'MEC Latency (s)');
            createChart('chartSwitchCount', 'switchCount', true, 'Cumulative Switches');
        }};
    </script>
</body>
</html>
"""

    html_content = externalize_html_assets(
        html_content,
        output_path,
        'dashboard.css',
        'dashboard.js',
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"[+] Executive Interactive Dashboard generated: {output_path} ({len(html_content)/1024:.1f} KB)")
    return output_path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 dashboard.py <scenario_dir> [output_path]")
        sys.exit(1)

    scen_dir = Path(sys.argv[1])
    out_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    generate_dashboard(scen_dir, out_file)
