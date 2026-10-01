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


if __name__ == '__main__':
    unittest.main()
