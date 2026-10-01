#!/usr/bin/env python3
"""
Unit and integration tests for ScenarioGenerator and scenario library.
"""

import sys
import os
import shutil
import tempfile
import unittest
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.gen_scenario import ScenarioGenerator
from tools.schema import validate_scenario_file


class TestScenarioGenerator(unittest.TestCase):
    def setUp(self):
        self.library_dir = REPO_ROOT / 'scenarios' / 'library'
        self.temp_dir = REPO_ROOT / 'tests' / 'tmp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_all_library_scenarios(self):
        """Validates that all scenarios in scenarios/library/*.yaml pass validation and build."""
        yaml_files = list(self.library_dir.glob('*.yaml'))
        self.assertGreater(len(yaml_files), 0, "No scenarios found in scenarios/library/")

        for yf in yaml_files:
            with self.subTest(scenario=yf.name):
                ok, errors = validate_scenario_file(str(yf))
                self.assertTrue(ok, f"Pydantic schema validation failed for {yf.name}: {errors}")
                
                generator = ScenarioGenerator(str(yf))
                generator.build()
                self.assertGreater(len(generator.satellites) + len(generator.gnbs), 0,
                                   f"Topology empty for scenario {yf.name}")

    def test_generate_stelvio_pass_hybrid(self):
        """Tests complete generation of Stelvio Pass Alpine Hybrid scenario."""
        yaml_path = self.library_dir / 'stelvio_pass_hybrid.yaml'
        out_dir = self.temp_dir / 'stelvio_out'
        out_dir.mkdir(parents=True, exist_ok=True)

        generator = ScenarioGenerator(str(yaml_path))
        generator.generate(str(out_dir))

        # Check required files generated
        ini_path = out_dir / 'omnetpp.ini'
        ned_path = out_dir / 'scenario.ned'
        tle_path = out_dir / 'constellation.tle'
        tcl_path = out_dir / 'mobility.tcl'

        self.assertTrue(ini_path.exists(), "omnetpp.ini was not generated")
        self.assertTrue(ned_path.exists(), "scenario.ned was not generated")
        self.assertTrue(tle_path.exists(), "constellation.tle was not generated")
        self.assertTrue(tcl_path.exists(), "mobility.tcl was not generated")

        # Verify ini content
        ini_content = ini_path.read_text(encoding='utf-8')

        # Check selective vector recording
        self.assertIn("**.vector-recording = false", ini_content)
        self.assertIn("*.node[*].hybridManager.*.vector-recording = true", ini_content)

        # Check single non-conflicting switchingMode
        self.assertIn("*.node[*].hybridManager.switchingMode =", ini_content)
        self.assertNotIn("**.hybridManager.switchingMode =", ini_content)

        # Check dynamic blind spot parameters
        self.assertIn("*.node[*].hybridManager.blindSpotMinX =", ini_content)
        self.assertIn("*.node[*].hybridManager.blindSpotAttenuationDb =", ini_content)

    def test_generate_highway_platooning(self):
        """Tests generation of Highway Platooning scenario."""
        yaml_path = self.library_dir / 'nexasphere_highway_platooning.yaml'
        out_dir = self.temp_dir / 'highway_out'
        out_dir.mkdir(parents=True, exist_ok=True)

        generator = ScenarioGenerator(str(yaml_path))
        generator.generate(str(out_dir))

        ini_path = out_dir / 'omnetpp.ini'
        self.assertTrue(ini_path.exists())
        ini_content = ini_path.read_text(encoding='utf-8')
        self.assertIn("*.node[*].hybridManager.switchingMode =", ini_content)

    def test_coordinates_and_blind_spots_use_local_frame(self):
        """Generated terrestrial coordinates must be local to the scenario center."""
        yaml_path = self.library_dir / 'stelvio_pass_hybrid.yaml'
        out_dir = self.temp_dir / 'local_frame_out'

        generator = ScenarioGenerator(str(yaml_path))
        generator.generate(str(out_dir))
        ini_content = (out_dir / 'omnetpp.ini').read_text(encoding='utf-8')

        center = generator.area
        expected_gs_x = (generator.ground_stations[0].lon - center['center_lon']) * 111000.0 * math.cos(math.radians(center['center_lat']))
        expected_blind_x = (10.4550 - center['center_lon']) * 111000.0 * math.cos(math.radians(center['center_lat']))
        self.assertIn('*.groundStation[0].mobility.initialX = ', ini_content)
        self.assertIn(f'*.groundStation[0].mobility.initialX = {expected_gs_x}m', ini_content)
        self.assertIn(f'*.node[*].hybridManager.blindSpotMinX = {expected_blind_x}', ini_content)


if __name__ == '__main__':
    unittest.main()
