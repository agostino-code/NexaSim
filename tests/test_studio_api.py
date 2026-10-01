#!/usr/bin/env python3
"""
Integration tests for Studio Web GUI Backend API (FastAPI).
"""

import sys
import os
import shutil
import unittest
from pathlib import Path
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.studio import app, LIBRARY_DIR


class TestStudioAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_scenario_id = "_test_auto_scenario_temp"
        self.test_scenario_file = LIBRARY_DIR / f"{self.test_scenario_id}.yaml"

    def tearDown(self):
        if self.test_scenario_file.exists():
            self.test_scenario_file.unlink(missing_ok=True)

    def test_get_scenarios_list(self):
        """Tests GET /api/scenarios returns available scenarios with metadata."""
        response = self.client.get("/api/scenarios")
        self.assertEqual(response.status_code, 200)
        scenarios = response.json()
        self.assertIsInstance(scenarios, list)
        self.assertGreater(len(scenarios), 0)

        # Check key fields in scenario summaries
        s0 = scenarios[0]
        self.assertIn("id", s0)
        self.assertIn("name", s0)
        self.assertIn("satellites", s0)
        self.assertIn("gnbs", s0)

    def test_get_single_scenario(self):
        """Tests GET /api/scenario?name=stelvio_pass_hybrid."""
        response = self.client.get("/api/scenario?name=stelvio_pass_hybrid")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("yaml", data)
        self.assertIn("data", data)
        self.assertEqual(data["data"]["scenario"]["name"], "stelvio_pass_alpine_hybrid")

    def test_post_save_valid_scenario(self):
        """Tests POST /api/save successfully validates and persists a new scenario."""
        valid_yaml = """
scenario:
  name: "test_auto_scenario_temp"
  description: "Temporary automated test scenario"
  version: "1.0"
  time:
    start: "2026-08-26T10:00:00Z"
    duration_s: 60.0
    warmup_s: 5.0
  area:
    name: "Test Alpine Area"
    center_lat: 46.5
    center_lon: 10.4
    bbox: [10.3, 46.4, 10.5, 46.6]
    elevation_mask_deg: 20.0
  constellation:
    shells:
      - name: "shell_1"
        altitude_km: 550.0
        inclination_deg: 53.0
        num_planes: 2
        sats_per_plane: 2
  terrestrial:
    gnb:
      count: 1
      sites:
        - name: "gnb_1"
          lat: 46.5
          lon: 10.4
          height_m: 30.0
    ue:
      count: 2
"""
        payload = {
            "id": self.test_scenario_id,
            "yaml": valid_yaml
        }

        response = self.client.post("/api/save", json=payload)
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertEqual(res_data["status"], "saved")
        self.assertTrue(self.test_scenario_file.exists())

        # Verify saved file content is readable and valid
        content = self.test_scenario_file.read_text(encoding='utf-8')
        self.assertIn("test_auto_scenario_temp", content)

    def test_post_save_invalid_yaml_syntax(self):
        """Tests POST /api/save rejects malformed YAML syntax."""
        payload = {
            "id": self.test_scenario_id,
            "yaml": "scenario:\n  name: [unclosed list"
        }
        response = self.client.post("/api/save", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid scenario payload", response.json()["detail"])
        self.assertFalse(self.test_scenario_file.exists())

    def test_post_save_path_traversal_attack(self):
        """Tests POST /api/save prevents path traversal outside library directory."""
        payload = {
            "id": "../../malicious_escape",
            "yaml": "scenario:\n  name: 'test'"
        }
        response = self.client.post("/api/save", json=payload)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid scenario ID", response.json()["detail"])

    def test_get_status(self):
        """Tests GET /api/status returns runner status."""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        status = response.json()
        self.assertIn("running", status)
        self.assertIn("scenario", status)
        self.assertIn("logs", status)
        self.assertIn("run_id", status)
        self.assertIn("started_at", status)

    def test_static_studio_assets_are_served(self):
        """Studio serves CSS and JavaScript as separate static assets."""
        css_response = self.client.get("/assets/studio.css")
        js_response = self.client.get("/assets/studio.js")

        self.assertEqual(css_response.status_code, 200)
        self.assertEqual(js_response.status_code, 200)
        self.assertIn("--bg-base", css_response.text)
        self.assertIn("function boot", js_response.text)

    def test_simulation_log_buffer_is_bounded(self):
        """The in-memory log buffer must not grow without limit."""
        from tools import studio

        with studio.SIM_LOCK:
            studio.SIM_STATE["logs"] = []
            for index in range(studio.MAX_LOG_LINES + 25):
                studio.append_sim_log(f"line-{index}")
            logs = list(studio.SIM_STATE["logs"])

        self.assertEqual(len(logs), studio.MAX_LOG_LINES)
        self.assertEqual(logs[0], "line-25")

    def test_get_telemetry_timeseries(self):
        """Tests GET /api/telemetry returns realistic timeseries metrics for Chart.js drawer."""
        response = self.client.get("/api/telemetry?name=stelvio")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("timestamps", data)
        self.assertIn("throughput_mbps", data)
        self.assertIn("rtt_ms", data)
        self.assertIn("handover_events", data)
        self.assertIn("active_interface", data)
        self.assertGreater(len(data["timestamps"]), 0)
        self.assertEqual(len(data["timestamps"]), len(data["throughput_mbps"]))
        self.assertEqual(len(data["timestamps"]), len(data["rtt_ms"]))


if __name__ == '__main__':
    unittest.main()
