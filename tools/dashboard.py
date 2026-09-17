#!/usr/bin/env python3
import csv
import json
import os
import sys
import subprocess
from pathlib import Path

def export_vectors(vec_file, output_csv):
    """Uses OMNeT++ scavetool to export vectors to CSV-R."""
    cmd = ["/omnetpp/bin/scavetool", "x", "-F", "CSV-R", "-o", output_csv, vec_file]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error exporting vectors: {e.stderr}")
        return False
    except FileNotFoundError:
        print("scavetool not found. Ensure this script is run inside the OMNeT++ container.")
        return False

def parse_csv(csv_path):
    series = {}
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['type'] == 'vector':
                module = row['module']
                # remove ':vector' from the end if present
                name = row['name'].replace(':vector', '')
                
                times = row['vectime'].split()
                values = row['vecvalue'].split()
                
                if not times or not values:
                    continue
                
                if module not in series:
                    series[module] = {}
                
                series[module][name] = {
                    'x': [float(t) for t in times],
                    'y': [float(v) for v in values]
                }
    return series

def generate_html(series, output_path):
    metrics = {}
    for module, module_data in series.items():
        for metric_name, data in module_data.items():
            if metric_name not in metrics:
                metrics[metric_name] = []
            
            # Map into Chart.js dataset format
            # Use step chart for activeInterface (0=5G, 1=Sat)
            dataset = {
                'label': module,
                'data': [{'x': x, 'y': y} for x, y in zip(data['x'], data['y'])],
                'fill': False,
                'borderWidth': 2,
                'pointRadius': 0,
                'stepped': metric_name == 'activeInterface'
            }
            metrics[metric_name].append(dataset)

    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>NexaSim TN-NTN VHO Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f4f6f9; }}
        h1 {{ text-align: center; color: #2c3e50; }}
        .dashboard {{ display: flex; flex-wrap: wrap; justify-content: space-around; }}
        .chart-container {{
            width: 45%;
            background: white;
            padding: 15px;
            margin: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            min-height: 400px;
        }}
        canvas {{ width: 100% !important; height: 100% !important; }}
    </style>
</head>
<body>
    <h1>NexaSim Vertical Handover (VHO) Dashboard</h1>
    <div class="dashboard" id="charts"></div>

    <script>
        const metrics = {json.dumps(metrics)};
        const container = document.getElementById('charts');
        
        // Define human-readable titles
        const titles = {{
            'activeInterface': 'Active Interface (0 = 5G-NR, 1 = Satellite)',
            'switchCount': 'Cumulative Vertical Handovers',
            'qosScore': 'QoS Score (Score calculation based on strategy)',
            'batterySoC': 'Vehicle Battery State of Charge (SoC %)'
        }};
        
        for (const [metric, datasets] of Object.entries(metrics)) {{
            const div = document.createElement('div');
            div.className = 'chart-container';
            const canvas = document.createElement('canvas');
            div.appendChild(canvas);
            container.appendChild(div);
            
            new Chart(canvas, {{
                type: 'line',
                data: {{ datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{
                        title: {{ 
                            display: true, 
                            text: titles[metric] || metric.toUpperCase(), 
                            font: {{ size: 16 }} 
                        }},
                        legend: {{ display: datasets.length <= 10 }} // Hide legend if too many vehicles
                    }},
                    scales: {{
                        x: {{ type: 'linear', title: {{ display: true, text: 'Simulation Time (s)' }} }},
                        y: {{ title: {{ display: true, text: 'Value' }} }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
"""
    with open(output_path, 'w') as f:
        f.write(html_template)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 dashboard.py <scenario_dir>")
        sys.exit(1)
        
    scenario_dir = Path(sys.argv[1])
    results_dir = scenario_dir / "results"
    
    vec_files = list(results_dir.glob("*.vec"))
    if not vec_files:
        print(f"No .vec files found in {results_dir}. Run the simulation first.")
        sys.exit(1)
        
    vec_file = str(vec_files[0])
    csv_file = str(results_dir / "exported_vectors.csv")
    html_file = str(results_dir / "dashboard.html")
    
    print(f"[*] Exporting vectors from {vec_file} to CSV...")
    if export_vectors(vec_file, csv_file):
        print(f"[*] Parsing {csv_file}...")
        data = parse_csv(csv_file)
        if not data:
            print("[!] No vector data found in CSV.")
        else:
            print(f"[*] Generating dashboard with {len(data)} module traces...")
            generate_html(data, html_file)
            print(f"[+] Dashboard created: {html_file}")
