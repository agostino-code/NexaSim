#!/usr/bin/env python3
"""
Unit tests for 3D CZML Generator and Aerospace Orbit Propagation.
"""

import sys
import os
import json
import math
import shutil
import unittest
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.czml_generator import (
    ecef_to_geodetic,
    compute_satellite_position,
    generate_czml_scene,
    R_EARTH_KM
)


class TestCZMLGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = REPO_ROOT / 'tests' / 'tmp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ecef_to_geodetic_equator(self):
        """Tests ECEF to geodetic conversion at known coordinates (Equator 0,0)."""
        # Point at equator, 0 deg lon, 500 km altitude
        r = R_EARTH_KM + 500.0
        lon, lat, alt_m = ecef_to_geodetic(r, 0.0, 0.0)
        self.assertAlmostEqual(lon, 0.0, places=4)
        self.assertAlmostEqual(lat, 0.0, places=4)
        self.assertAlmostEqual(alt_m, 500000.0, delta=100.0)

    def test_compute_satellite_position(self):
        """Tests satellite orbital position propagation."""
        lon, lat, alt_m = compute_satellite_position(
            altitude_km=550.0,
            inclination_deg=53.0,
            raan_deg=0.0,
            mean_anomaly_deg=0.0,
            t_sec=120.0
        )
        self.assertTrue(-180.0 <= lon <= 180.0, f"Longitude out of bounds: {lon}")
        self.assertTrue(-55.0 <= lat <= 55.0, f"Latitude out of bounds for 53 deg inc: {lat}")
        self.assertAlmostEqual(alt_m, 550000.0, delta=500.0)

    def test_generate_czml_scene_structure(self):
        """Tests end-to-end CZML document generation for standard scenario."""
        config = {
            'scenario': {
                'name': 'Test_Scenario_CZML',
                'time': {
                    'start': '2026-08-26T10:00:00Z',
                    'duration_s': 60.0
                },
                'area': {
                    'center_lat': 46.5,
                    'center_lon': 10.4,
                    'elevation_mask_deg': 25.0
                },
                'constellation': {
                    'shells': [{
                        'name': 'test_shell',
                        'altitude_km': 600.0,
                        'inclination_deg': 53.0,
                        'num_planes': 2,
                        'sats_per_plane': 2
                    }]
                },
                'terrestrial': {
                    'gnb': {
                        'count': 1,
                        'sites': [{'name': 'gNB-01', 'lat': 46.5, 'lon': 10.4, 'height_m': 35.0}]
                    },
                    'ue': {
                        'count': 2
                    }
                }
            }
        }

        output_path = self.temp_dir / 'test_scene.czml'
        czml_packets = generate_czml_scene(config, output_czml=output_path, duration_s=60.0, time_step=5.0)

        self.assertTrue(output_path.exists(), "CZML file not written")
        self.assertGreater(len(czml_packets), 0)

        # Check document header
        doc = czml_packets[0]
        self.assertEqual(doc['id'], 'document')
        self.assertIn('clock', doc)
        self.assertEqual(doc['clock']['interval'], '2026-08-26T10:00:00Z/2026-08-26T10:01:00Z')

        # Check satellites and gNB presence
        packet_ids = [p['id'] for p in czml_packets]
        self.assertTrue(any('sat_' in pid for pid in packet_ids), "No satellites found in CZML")
        self.assertTrue(any('gnb_' in pid for pid in packet_ids), "No gNB found in CZML")

    def test_adaptive_time_step_dense_constellation(self):
        """Tests that large constellations or long durations automatically adapt time_step."""
        # 12 planes x 10 sats = 120 sats (> 100)
        config = {
            'scenario': {
                'name': 'Dense_Constellation_Test',
                'time': {'duration_s': 300.0},
                'constellation': {
                    'shells': [{
                        'name': 'dense_shell',
                        'altitude_km': 550.0,
                        'inclination_deg': 53.0,
                        'num_planes': 12,
                        'sats_per_plane': 10
                    }]
                }
            }
        }
        output_path = self.temp_dir / 'dense.czml'
        czml_packets = generate_czml_scene(config, output_czml=output_path, duration_s=300.0, time_step=2.0)
        # Should adapt time step to at least 15.0s, so samples <= 300/15 + 1 = 21
        sat_packets = [p for p in czml_packets if p.get('id', '').startswith('sat_')]
        self.assertGreater(len(sat_packets), 0)
        cartographic = sat_packets[0]['position']['cartographicDegrees']
        num_samples = len(cartographic) // 4
        self.assertLessEqual(num_samples, 25, "Time step was not adaptively throttled for dense constellation")


if __name__ == '__main__':
    unittest.main()
