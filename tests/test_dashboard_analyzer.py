#!/usr/bin/env python3
"""
Unit and integration tests for Dashboard and Result Analysis tools.
"""

import sys
import os
import math
import shutil
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.dashboard import (
    build_fleet_summary,
    parse_vector_file,
    generate_dashboard
)
from tools.analyze_results import parse_sca_file, analyze_simulation_directory


class TestDashboardAnalyzer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = REPO_ROOT / 'tests' / 'tmp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.highway_results = REPO_ROOT / 'scenarios' / 'generated' / 'highway_platooning' / 'results'

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_real_sca_file(self):
        """Tests parsing real OMNeT++ scalar (.sca) file."""
        sca_file = self.highway_results / 'General-0.sca'
        self.assertTrue(sca_file.exists(), f"Missing {sca_file}")

        data = parse_sca_file(sca_file)
        self.assertIn("scalars", data)
        self.assertIn("attributes", data)
        self.assertGreater(len(data["scalars"]), 0)

    def test_parse_real_vec_file(self):
        """Tests parsing real OMNeT++ vector (.vec) file."""
        vec_file = self.highway_results / 'General-0.vec'
        self.assertTrue(vec_file.exists(), f"Missing {vec_file}")

        structured = parse_vector_file(vec_file)
        self.assertIsInstance(structured, dict)
        self.assertGreater(len(structured), 0)

    def test_build_fleet_summary_with_nan_and_empty(self):
        """Tests build_fleet_summary resilience against NaN, None, and missing metrics."""
        mock_data = {
            "Vehicle 0": {
                "switchCount": {"y": [0, 1, 2]},
                "activeInterface": {"y": [0, 1, 1]},
                "qosScore": {"y": [0.95, float('nan'), 0.85]},
                "batterySoC": {"y": [0.99, 0.98]},
                "mecTaskLatency": {"y": [0.020, 0.025]}
            },
            "Vehicle 1": {
                "switchCount": {"y": []},
                "activeInterface": {"y": []},
                "qosScore": {"y": [float('nan')]},
                "batterySoC": {"y": []},
                "mecTaskLatency": {"y": []}
            }
        }

        summary = build_fleet_summary(mock_data)
        self.assertEqual(len(summary), 2)

        v0 = summary[0]
        self.assertEqual(v0["vehicle"], "Vehicle 0")
        self.assertEqual(v0["total_switches"], 2)
        self.assertEqual(v0["final_interface"], "Satellite LEO")
        self.assertAlmostEqual(v0["mean_qos"], 0.90, places=2)
        self.assertEqual(v0["final_soc"], 98.0)
        self.assertEqual(v0["mean_mec_latency_ms"], 22.5)

        v1 = summary[1]
        self.assertEqual(v1["vehicle"], "Vehicle 1")
        self.assertEqual(v1["total_switches"], 0)
        # Verify NaN or missing doesn't crash and returns None
        self.assertIsNone(v1["mean_qos"])
        self.assertIsNone(v1["final_soc"])
        self.assertIsNone(v1["mean_mec_latency_ms"])

    def test_generate_dashboard_html(self):
        """Tests end-to-end dashboard generation produces valid HTML."""
        scenario_dir = REPO_ROOT / 'scenarios' / 'generated' / 'highway_platooning'
        out_html = self.temp_dir / 'test_dash.html'

        res = generate_dashboard(scenario_dir, output_path=out_html)
        self.assertTrue(out_html.exists())
        content = out_html.read_text(encoding='utf-8')

        self.assertIn("NexaSim 3D TN-NTN Executive Dashboard", content)
        self.assertIn("chart.js", content.lower())
        self.assertIn("fleetTableBody", content)
        self.assertIn("Highway Platooning", content)
        self.assertIn('href="dashboard.css"', content)
        self.assertIn('src="dashboard.js"', content)
        self.assertTrue((out_html.parent / 'dashboard.css').exists())
        self.assertTrue((out_html.parent / 'dashboard.js').exists())
        self.assertNotIn('<style>', content)

    def test_multi_run_monte_carlo_ci95_and_paper_export(self):
        """Tests that analyze_simulation_directory computes 95% CI across multiple runs and exports IEEE LaTeX table."""
        mock_sim_dir = self.temp_dir / 'mock_multirun'
        mock_results = mock_sim_dir / 'results'
        mock_results.mkdir(parents=True, exist_ok=True)

        sca_template = """run General-{idx}-20261016-21:00:00-1234
attr network GeneratedScenario
attr sim-time-limit 100s
par *.constellationManager.constellationType "starlink_shell"
scalar GeneratedScenario.hybridManager totalSwitches {switches}
scalar GeneratedScenario.userTerminal[0].nic packetsSent 1000
scalar GeneratedScenario.userTerminal[0].nic packetsReceived {rcvd}
scalar GeneratedScenario.userTerminal[0].nic avgLatencyMs {lat}
scalar GeneratedScenario.hybridManager satUsageRatio {sat}
scalar GeneratedScenario.hybridManager cellUsageRatio {cell}
scalar GeneratedScenario.hybridManager batterySoC 0.95
"""
        # Run 0
        (mock_results / "General-0.sca").write_text(
            sca_template.format(idx=0, switches=10, rcvd=990, lat=12.0, sat=0.4, cell=0.6),
            encoding='utf-8'
        )
        # Run 1
        (mock_results / "General-1.sca").write_text(
            sca_template.format(idx=1, switches=12, rcvd=980, lat=14.0, sat=0.5, cell=0.5),
            encoding='utf-8'
        )
        # Run 2
        (mock_results / "General-2.sca").write_text(
            sca_template.format(idx=2, switches=14, rcvd=970, lat=16.0, sat=0.6, cell=0.4),
            encoding='utf-8'
        )

        res = analyze_simulation_directory(str(mock_sim_dir), generate_dashboard=False, export_paper=True)
        self.assertEqual(res["runs_count"], 3)
        self.assertIn("multi_run_stats", res)

        stats = res["multi_run_stats"]
        self.assertIn("total_vho_switches", stats)
        # switches: [10, 12, 14] -> mean = 12.0, std = 2.0, CI95 = 1.96 * 2.0 / sqrt(3) ~ 2.2632
        sw_stat = stats["total_vho_switches"]
        self.assertAlmostEqual(sw_stat["mean"], 12.0, places=2)
        self.assertAlmostEqual(sw_stat["std"], 2.0, places=2)
        self.assertGreater(sw_stat["ci95_half_width"], 2.20)
        self.assertLess(sw_stat["ci95_half_width"], 2.30)
        self.assertEqual(sw_stat["min"], 10.0)
        self.assertEqual(sw_stat["max"], 14.0)

        # Check export_paper artifacts
        csv_file = mock_results / "summary_metrics.csv"
        tex_file = mock_results / "ieee_table.tex"
        self.assertTrue(csv_file.exists())
        self.assertTrue(tex_file.exists())

        csv_content = csv_file.read_text(encoding='utf-8')
        self.assertIn("total_vho_switches", csv_content)
        self.assertIn("pdr_pct", csv_content)

        tex_content = tex_file.read_text(encoding='utf-8')
        self.assertIn("\\begin{table}", tex_content)
        self.assertIn("\\toprule", tex_content)
        self.assertIn("Total Vertical Handovers (VHO)", tex_content)
        self.assertIn("\\pm", tex_content)


if __name__ == '__main__':
    unittest.main()
