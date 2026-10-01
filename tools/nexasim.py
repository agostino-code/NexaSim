#!/usr/bin/env python3
"""
NexaSim Unified CLI - 3D Multi-Tier Network Simulation Engine
Horizon Europe NexaSphere Research Project

Usage:
  nexasim list                                   List all scenarios in library
  nexasim validate [scenario]                    Validate scenario YAML specification
  nexasim generate <scenario> [-o <dir>]         Generate OMNeT++ and SUMO configs
  nexasim run <scenario> [--gui]                 Run simulation (headless or NoVNC GUI)
  nexasim analyze <scenario> [--dashboard]       Extract KPIs and generate dashboard
  nexasim dashboard <scenario> [--open]          Generate and open Chart.js dashboard
  nexasim all <scenario> [--gui]                 End-to-end: generate, run, analyze
  nexasim clean                                  Clean generated outputs and temporary logs
"""

import sys
import os
import argparse
import subprocess
import shutil
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
LIBRARY_DIR = REPO_ROOT / 'scenarios' / 'library'
GENERATED_DIR = REPO_ROOT / 'scenarios' / 'generated'

# Terminal ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def is_inside_docker() -> bool:
    """Check if the script is executing inside a Docker container."""
    return Path('/.dockerenv').exists() or Path('/omnetpp').exists()

def resolve_scenario_yaml(identifier: str) -> Optional[Path]:
    """Finds YAML file either by exact path, relative path, or scenario name."""
    p = Path(identifier)
    if p.exists() and p.is_file():
        return p.resolve()

    # Check library dir
    if not identifier.endswith('.yaml') and not identifier.endswith('.yml'):
        candidate = LIBRARY_DIR / f"{identifier}.yaml"
        if candidate.exists():
            return candidate.resolve()
    else:
        candidate = LIBRARY_DIR / identifier
        if candidate.exists():
            return candidate.resolve()

    # Substring search in library
    for item in LIBRARY_DIR.glob("*.yaml"):
        if identifier.lower() in item.stem.lower():
            return item.resolve()
    return None

def resolve_generated_dir(identifier: str) -> Path:
    """Finds or infers the generated scenario output folder."""
    p = Path(identifier)
    if p.exists() and p.is_dir():
        return p.resolve()

    # Check exact match under GENERATED_DIR
    exact = GENERATED_DIR / identifier
    if exact.exists():
        return exact.resolve()

    yaml_path = resolve_scenario_yaml(identifier)
    if yaml_path:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        sc_name = data.get('scenario', {}).get('name', yaml_path.stem)
    else:
        sc_name = identifier

    # Search existing directories in generated
    if GENERATED_DIR.exists():
        for d in GENERATED_DIR.iterdir():
            if d.is_dir():
                d_stem = d.name.lower()
                clean_name = sc_name.lower().replace('nexasphere_', '').replace('_hybrid', '').replace('_alpine', '')
                if d_stem in clean_name or clean_name in d_stem:
                    return d.resolve()

    short_name = sc_name.replace('nexasphere_', '').replace('_hybrid', '').replace('_alpine', '').replace('_pass', '')
    return GENERATED_DIR / short_name

def cmd_list(args):
    """List all available scenarios in library with metadata."""
    print(f"\n{BOLD}{CYAN}========================================================================================{RESET}")
    print(f"{BOLD}{CYAN}  NexaSim 3D Scenario Library (Horizon Europe NexaSphere){RESET}")
    print(f"{BOLD}{CYAN}========================================================================================{RESET}\n")

    files = sorted(list(LIBRARY_DIR.glob("*.yaml")))
    if not files:
        print(f"{YELLOW}No scenarios found in {LIBRARY_DIR}{RESET}")
        return

    header = f"{'Scenario Name':<32} {'Domain / Focus':<28} {'Nodes (Sat/gNB/UE)':<20} {'Duration':<10}"
    print(f"{BOLD}{header}{RESET}")
    print("-" * 92)

    for yaml_file in files:
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            sc = data.get('scenario', {})
            name = sc.get('name', yaml_file.stem)
            time_cfg = sc.get('time', {})
            duration = f"{time_cfg.get('duration_s', '?')}s"

            # Constellation
            const_cfg = sc.get('constellation', {})
            shells = const_cfg.get('shells', [])
            sats = sum(s.get('num_planes', 0) * s.get('sats_per_plane', 0) for s in shells)

            # Terrestrial
            terr_cfg = sc.get('terrestrial', {})
            gnbs = len(terr_cfg.get('gnb', {}).get('sites', []))
            ues = terr_cfg.get('ue', {}).get('count', 0)

            nodes_str = f"{sats} sat / {gnbs} gnb / {ues} ue"
            desc = sc.get('description', '')
            if len(desc) > 26:
                desc = desc[:23] + "..."

            print(f"{GREEN}{name:<32}{RESET} {desc:<28} {nodes_str:<20} {duration:<10}")
        except Exception as e:
            print(f"{RED}{yaml_file.stem:<32} [Error loading YAML: {e}]{RESET}")

    print("\nRun any scenario with:")
    print(f"  {CYAN}nexasim run <scenario_name> [--gui]{RESET}\n")

def cmd_validate(args):
    """Validate scenario syntax and physical parameter bounds."""
    try:
        from tools.schema import validate_scenario_file
    except ImportError:
        try:
            from schema import validate_scenario_file
        except ImportError:
            validate_scenario_file = None

    if args.scenario:
        yaml_path = resolve_scenario_yaml(args.scenario)
        if not yaml_path:
            print(f"{RED}Error: Scenario '{args.scenario}' not found.{RESET}")
            sys.exit(1)
        targets = [yaml_path]
    else:
        targets = sorted(list(LIBRARY_DIR.glob("*.yaml")))

    print(f"\n{BOLD}Validating {len(targets)} scenario(s)...{RESET}\n")
    all_ok = True
    for target in targets:
        if validate_scenario_file:
            ok, errors = validate_scenario_file(target)
            if ok:
                print(f"  [{GREEN}PASS{RESET}] {target.name}")
            else:
                all_ok = False
                print(f"  [{RED}FAIL{RESET}] {target.name}:")
                for err in errors:
                    print(f"         {YELLOW}• {err}{RESET}")
        else:
            # Fallback simple PyYAML syntax check
            try:
                with open(target, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
                print(f"  [{GREEN}PASS{RESET}] {target.name} (Valid YAML syntax)")
            except Exception as e:
                all_ok = False
                print(f"  [{RED}FAIL{RESET}] {target.name}: {e}")

    if not all_ok:
        sys.exit(1)
    print(f"\n{GREEN}All scenarios passed validation!{RESET}\n")

def cmd_generate(args):
    """Generate OMNeT++ and SUMO scenario files."""
    yaml_path = resolve_scenario_yaml(args.scenario)
    if not yaml_path:
        print(f"{RED}Error: Scenario '{args.scenario}' not found.{RESET}")
        sys.exit(1)

    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    scenario_name = data.get('scenario', {}).get('name', yaml_path.stem)

    if args.output:
        out_dir = Path(args.output).resolve()
    else:
        out_dir = resolve_generated_dir(args.scenario)

    print(f"{BOLD}[*] Generating scenario '{scenario_name}' into {out_dir}...{RESET}")
    gen_script = REPO_ROOT / 'tools' / 'gen_scenario.py'

    cmd = [sys.executable, str(gen_script), str(yaml_path), '-o', str(out_dir)]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"{RED}Generation failed.{RESET}")
        sys.exit(res.returncode)

    print(f"{GREEN}Generation complete!{RESET}\n")
    return out_dir

def cmd_run(args):
    """Execute scenario simulation (in container or locally)."""
    yaml_path = resolve_scenario_yaml(args.scenario)
    if not yaml_path:
        print(f"{RED}Error: Scenario '{args.scenario}' not found.{RESET}")
        sys.exit(1)

    out_dir = resolve_generated_dir(args.scenario)
    short_name = out_dir.name

    # Auto-generate if missing
    if not (out_dir / 'omnetpp.ini').exists():
        print(f"{YELLOW}[!] Scenario files not found. Auto-generating...{RESET}")
        gen_script = REPO_ROOT / 'tools' / 'gen_scenario.py'
        subprocess.run([sys.executable, str(gen_script), str(yaml_path), '-o', str(out_dir)], check=True)

    in_docker = is_inside_docker()

    if in_docker:
        # Run directly inside container
        opp_run_sh = REPO_ROOT / 'tools' / 'opp_run.sh'
        if args.gui:
            gui_script = REPO_ROOT / 'tools' / 'start_gui.sh'
            cmd = ['bash', str(gui_script), '-f', str(out_dir / 'omnetpp.ini')]
        else:
            cmd = ['bash', str(opp_run_sh), '-f', str(out_dir / 'omnetpp.ini'), '-u', 'Cmdenv']

        print(f"{BOLD}[*] Executing inside container: {' '.join(cmd)}{RESET}")
        res = subprocess.run(cmd, cwd=str(out_dir))
        return res.returncode
    else:
        # Host execution: dispatch via docker compose
        print(f"{BOLD}[*] Dispatching simulation via Docker Compose...{RESET}")
        if args.gui:
            print(f"\n{BOLD}{CYAN}========================================================================{RESET}")
            print(f"{BOLD}{GREEN} Starting NexaSim OMNeT++ Qtenv & SUMO-GUI Virtual Desktop             {RESET}")
            print(f"{BOLD}{GREEN} Connect via Browser: {CYAN}http://localhost:6080/vnc.html{RESET}")
            print(f"{BOLD}{CYAN}========================================================================{RESET}\n")
            cmd = [
                'docker', 'compose', 'run', '--rm', '-p', '6080:6080',
                '-w', f"/artery/scenarios/generated/{short_name}",
                'nexasim-gui', 'bash', '/artery/tools/start_gui.sh', '-f', f"/artery/scenarios/generated/{short_name}/omnetpp.ini"
            ]
        else:
            cmd = [
                'docker', 'compose', 'run', '--rm',
                '-w', f"/artery/scenarios/generated/{short_name}",
                'nexasim', 'bash', '/artery/tools/opp_run.sh', '-f', f"/artery/scenarios/generated/{short_name}/omnetpp.ini", '-u', 'Cmdenv'
            ]
        env = os.environ.copy()
        env['MSYS_NO_PATHCONV'] = '1'
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
        return res.returncode

def cmd_analyze(args):
    """Run KPI evaluation and generate dashboard."""
    target_dir = resolve_generated_dir(args.scenario)

    if not target_dir.exists():
        print(f"{RED}Error: Results directory '{target_dir}' does not exist.{RESET}")
        sys.exit(1)

    analyze_script = REPO_ROOT / 'tools' / 'analyze_results.py'
    cmd = [sys.executable, str(analyze_script), str(target_dir)]
    if args.dashboard:
        cmd.append('--dashboard')

    subprocess.run(cmd, check=True)

def cmd_dashboard(args):
    """Generate and view interactive HTML dashboard."""
    target_dir = resolve_generated_dir(args.scenario)

    dashboard_script = REPO_ROOT / 'tools' / 'dashboard.py'
    cmd = [sys.executable, str(dashboard_script), str(target_dir)]
    subprocess.run(cmd, check=True)

    html_file = target_dir / 'results' / 'dashboard.html'
    if not html_file.exists():
        html_file = target_dir / 'dashboard.html'

    if html_file.exists():
        print(f"\n{GREEN}Dashboard ready: {html_file}{RESET}")
        if args.open:
            import webbrowser
            webbrowser.open(str(html_file.resolve().as_uri()))

def cmd_sweep(args):
    """Run parameter sweep and sensitivity benchmark."""
    try:
        from tools.sweep import run_parameter_sweep
    except ImportError:
        from sweep import run_parameter_sweep

    out_dir = Path(args.output).resolve() if args.output else None
    seeds = [int(s.strip()) for s in args.seeds.split(',')] if args.seeds else None
    run_parameter_sweep(args.scenario, args.param, reps=args.reps, seeds=seeds, output_dir=out_dir)

def cmd_view3d(args):
    """Generate and view 3D Space-Ground Digital Twin on Cesium globe."""
    try:
        from tools.czml_generator import create_scenario_digital_twin
    except ImportError:
        from czml_generator import create_scenario_digital_twin

    create_scenario_digital_twin(args.scenario, open_browser=args.open)

def cmd_studio(args):
    """Launch NexaSim Studio local web control center."""
    try:
        from tools.studio import start_studio_server
    except ImportError:
        from studio import start_studio_server

    start_studio_server(port=args.port, host=args.host, open_browser=args.open)

def cmd_all(args):
    """All-in-one end-to-end command."""
    print(f"\n{BOLD}{CYAN}=== Step 1/3: Generating Scenario ==={RESET}")
    cmd_generate(args)

    print(f"\n{BOLD}{CYAN}=== Step 2/3: Running Simulation ==={RESET}")
    ret = cmd_run(args)
    if ret != 0:
        print(f"{RED}Simulation failed with exit code {ret}.{RESET}")
        sys.exit(ret)

    print(f"\n{BOLD}{CYAN}=== Step 3/3: Analyzing Results & Dashboard ==={RESET}")
    args.dashboard = True
    cmd_analyze(args)

def cmd_clean(args):
    """Clean transient result files and vector artifacts."""
    count = 0
    for pattern in ["**/*.vec", "**/*.vci", "**/*.log", "**/.cmdenv-log"]:
        for f in REPO_ROOT.glob(pattern):
            if f.is_file():
                f.unlink()
                count += 1
    print(f"{GREEN}Cleaned {count} transient files.{RESET}")

def main():
    parser = argparse.ArgumentParser(
        prog='nexasim',
        description='NexaSim 3D Unified Network Simulator CLI (Horizon Europe NexaSphere)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nexasim list
  nexasim validate
  nexasim run stelvio --gui
  nexasim analyze stelvio --dashboard
  nexasim sweep emergency_corridor --param switchingMode=coverage-based,qos-based
  nexasim view-3d stelvio
  nexasim studio
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')

    # list
    p_list = subparsers.add_parser('list', help='List scenarios in library')
    p_list.set_defaults(func=cmd_list)

    # validate
    p_val = subparsers.add_parser('validate', help='Validate scenario YAML syntax & physical rules')
    p_val.add_argument('scenario', nargs='?', help='Scenario name or YAML file (default: all)')
    p_val.set_defaults(func=cmd_validate)

    # generate
    p_gen = subparsers.add_parser('generate', help='Generate OMNeT++ & SUMO scenario files')
    p_gen.add_argument('scenario', help='Scenario name or YAML path')
    p_gen.add_argument('-o', '--output', help='Output directory')
    p_gen.set_defaults(func=cmd_generate)

    # run
    p_run = subparsers.add_parser('run', help='Execute simulation')
    p_run.add_argument('scenario', help='Scenario name or path')
    p_run.add_argument('--gui', action='store_true', help='Launch interactive Qtenv & SUMO-GUI')
    p_run.add_argument('--headless', action='store_true', help='Force headless Cmdenv execution')
    p_run.set_defaults(func=cmd_run)

    # analyze
    p_ana = subparsers.add_parser('analyze', help='Extract KPIs and evaluation metrics')
    p_ana.add_argument('scenario', help='Scenario name or directory')
    p_ana.add_argument('--dashboard', action='store_true', help='Generate HTML dashboard as well')
    p_ana.set_defaults(func=cmd_analyze)

    # dashboard
    p_dash = subparsers.add_parser('dashboard', help='Generate and open Chart.js dashboard')
    p_dash.add_argument('scenario', help='Scenario name or directory')
    p_dash.add_argument('--open', action='store_true', help='Open dashboard in browser')
    p_dash.set_defaults(func=cmd_dashboard)

    # all
    p_all = subparsers.add_parser('all', help='End-to-end: generate, run and analyze')
    p_all.add_argument('scenario', help='Scenario name or path')
    p_all.add_argument('--gui', action='store_true', help='Run with GUI')
    p_all.add_argument('-o', '--output', help='Output directory')
    p_all.set_defaults(func=cmd_all)

    # sweep
    p_swp = subparsers.add_parser('sweep', help='Run multi-run sensitivity studies and parameter sweeps')
    p_swp.add_argument('scenario', help='Scenario name or path')
    p_swp.add_argument('--param', action='append', required=True, help="Parameter to sweep: 'name=v1,v2,v3'")
    p_swp.add_argument('--reps', type=int, default=1, help='Number of seed repetitions per configuration')
    p_swp.add_argument('--seeds', type=str, help='Comma-separated explicit seeds (e.g. 42,43,44)')
    p_swp.add_argument('-o', '--output', help='Output directory for sweep')
    p_swp.set_defaults(func=cmd_sweep)

    # view-3d
    p_v3d = subparsers.add_parser('view-3d', help='Generate and view 3D Space-Ground Digital Twin (CesiumJS)')
    p_v3d.add_argument('scenario', help='Scenario name or path')
    p_v3d.add_argument('--open', action='store_true', default=True, help='Open 3D globe viewer in browser')
    p_v3d.set_defaults(func=cmd_view3d)

    # studio
    p_std = subparsers.add_parser('studio', help='Launch NexaSim Studio local web control center')
    p_std.add_argument('--port', type=int, default=8080, help='Port to bind (default: 8080)')
    p_std.add_argument('--host', default='127.0.0.1', help='Host to bind (default: 127.0.0.1)')
    p_std.add_argument('--open', action='store_true', default=True, help='Open studio in browser')
    p_std.set_defaults(func=cmd_studio)

    # clean
    p_clean = subparsers.add_parser('clean', help='Clean temporary simulation logs & artifacts')
    p_clean.set_defaults(func=cmd_clean)

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
