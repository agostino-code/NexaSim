#!/usr/bin/env python3
"""
Run Artery scenario from YAML configuration
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Run Artery simulation scenario')
    parser.add_argument('config', help='YAML scenario configuration file')
    parser.add_argument('-o', '--output', default='scenarios/generated', help='Output directory')
    parser.add_argument('--generate-only', action='store_true', help='Only generate scenario files')
    parser.add_argument('--debug', action='store_true', help='Run with debug build')
    parser.add_argument('--gui', action='store_true', help='Run with Qtenv GUI')
    
    args = parser.parse_args()
    
    # Paths
    artery_root = Path(__file__).parent.parent
    build_dir = artery_root / 'build' / ('Debug' if args.debug else 'Release')
    scenario_gen = artery_root / 'tools' / 'gen_scenario.py'
    
    # Generate scenario
    output_path = Path(args.output)
    if output_path.parent.name == 'generated' or (output_path / 'omnetpp.ini').exists():
        output_dir = output_path
    else:
        scenario_name = Path(args.config).stem
        output_dir = output_path / scenario_name
    
    print(f"Generating scenario from {args.config}...")
    result = subprocess.run([
        sys.executable, str(scenario_gen), args.config, '-o', str(output_dir)
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Scenario generation failed:")
        print(result.stderr)
        sys.exit(1)
    
    print(result.stdout)
    
    if args.generate_only:
        print("Scenario files generated. Exiting.")
        return
    
    # Find the generated ini file
    ini_file = output_dir / 'omnetpp.ini'
    if not ini_file.exists():
        print(f"Error: Generated ini file not found: {ini_file}")
        sys.exit(1)

    # Find runner (prefer opp_run.sh in Linux/Docker container, fallback to standalone binary)
    opp_run_sh = artery_root / 'tools' / 'opp_run.sh'
    exe_name = 'artery' + ('.exe' if sys.platform == 'win32' else '')
    artery_exe = build_dir / exe_name

    ini_abs_path = str(ini_file.resolve())

    if opp_run_sh.exists() and sys.platform != 'win32':
        cmd = ['bash', str(opp_run_sh), '-f', ini_abs_path]
    elif artery_exe.exists():
        cmd = [str(artery_exe), '-f', ini_abs_path]
    else:
        print(f"Error: Neither {opp_run_sh} nor {artery_exe} found.")
        print("Please build the project first: docker compose run --rm nexasim-build")
        sys.exit(1)
    if args.gui:
        cmd.extend(['-u', 'Qtenv'])
    else:
        cmd.extend(['-u', 'Cmdenv'])
    
    print(f"Running simulation: {' '.join(cmd)}")
    print(f"Working directory: {output_dir}")
    
    # Run from output directory so relative paths work
    result = subprocess.run(cmd, cwd=output_dir)
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()