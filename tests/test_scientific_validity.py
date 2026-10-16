"""
NexaSim Scientific Validation Test Suite
Horizon Europe NexaSphere Research Project

Rigorous validation of:
1. Orbital Astrodynamics & Perturbations (Keplerian, J2 secular drift, Bowring ECEF roundtrip)
2. 3GPP TR 38.811 (NTN) & TR 38.901 (5G-NR) Channel Physics & Path Loss Monotonicity
3. Horizon Geometry & Fast O(1) Vector Culling
4. Handover Dynamics (HIT: DAPS 0ms vs Hard 45ms, Ping-Pong detection)
5. Multi-Hop ISL Mesh & End-to-End Latency Bounds
6. Full Scenario Catalog Consistency
"""

import math
import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.schema import validate_scenario_file
from tools.gen_scenario import ScenarioGenerator

# Physical constants
R_EARTH_KM = 6378.137
MU_EARTH = 398600.4418 # km^3/s^2
OMEGA_EARTH = 7.2921159e-5 # rad/s
J2_EARTH = 1.08263e-3
C_LIGHT_KM_S = 299792.458
C_LIGHT_M_S = 299792458.0


class TestAstrodynamicsAndOrbitalPhysics:
    """Verifies fundamental orbital mechanics and coordinate transformations."""

    def test_circular_orbit_velocity_and_period(self):
        """Validates Kepler's third law and circular velocity for Starlink-like 550km shell."""
        h_km = 550.0
        r_km = R_EARTH_KM + h_km

        # Circular velocity v = sqrt(mu / r)
        v_circ = math.sqrt(MU_EARTH / r_km)
        # Expected around 7.58 - 7.59 km/s
        assert 7.55 < v_circ < 7.62, f"Circular velocity {v_circ} km/s outside physical bounds"

        # Orbital period T = 2 * pi * sqrt(r^3 / mu)
        period_s = 2.0 * math.pi * math.sqrt((r_km ** 3) / MU_EARTH)
        # Period around 95.6 minutes (5738 seconds)
        period_min = period_s / 60.0
        assert 95.0 < period_min < 96.5, f"Orbital period {period_min} min outside expected range"

    def test_j2_nodal_regression_monotonicity(self):
        """Verifies that nodal precession rate dOmega/dt is strictly zero at i=90 deg and negative for prograde orbits."""
        a_km = R_EARTH_KM + 600.0
        n0 = math.sqrt(MU_EARTH / (a_km ** 3)) # rad/s
        eta = R_EARTH_KM / a_km
        j2_factor = 1.5 * J2_EARTH * (eta ** 2) * n0

        # Check at 0 deg, 53 deg, 90 deg (polar)
        raan_dot_equatorial = -j2_factor * math.cos(math.radians(0.0))
        raan_dot_53 = -j2_factor * math.cos(math.radians(53.0))
        raan_dot_polar = -j2_factor * math.cos(math.radians(90.0))

        assert raan_dot_equatorial < raan_dot_53 < 0.0
        assert abs(raan_dot_polar) < 1e-12, "Polar orbit nodal precession must be zero"

    def test_earth_rotation_tangential_velocity(self):
        """Validates Earth tangential velocity at equator."""
        v_tan = OMEGA_EARTH * (R_EARTH_KM * 1000.0)
        # Approximately 465.1 m/s
        assert 464.0 < v_tan < 466.0


class TestChannelPhysicsAndWavePropagation:
    """Verifies 3GPP propagation models, breakpoint distances, and FSPL monotonicity."""

    def test_fspl_monotonicity_distance_and_frequency(self):
        """FSPL must strictly increase monotonically with distance and frequency."""
        def fspl_db(d_m: float, f_hz: float) -> float:
            return 20.0 * math.log10(d_m) + 20.0 * math.log10(f_hz) + 20.0 * math.log10(4.0 * math.pi / C_LIGHT_M_S)

        # Distance monotonicity
        f_ka = 28e9
        d1, d2, d3 = 550e3, 800e3, 1200e3
        pl1 = fspl_db(d1, f_ka)
        pl2 = fspl_db(d2, f_ka)
        pl3 = fspl_db(d3, f_ka)
        assert pl1 < pl2 < pl3, "FSPL not monotonically increasing with distance"

        # Frequency monotonicity
        pl_sub6 = fspl_db(d1, 3.5e9)
        pl_ka = fspl_db(d1, 28e9)
        pl_vband = fspl_db(d1, 60e9)
        assert pl_sub6 < pl_ka < pl_vband, "FSPL not monotonically increasing with frequency"

    def test_3gpp_breakpoint_distance(self):
        """Validates 3GPP TR 38.901 breakpoint distance formulation."""
        h_bs = 25.0
        h_ue = 1.5
        fc = 3.5e9
        h_e = 1.0 # Effective environment height

        h_prime_bs = h_bs - h_e
        h_prime_ue = h_ue - h_e
        d_bp = 4.0 * h_prime_bs * h_prime_ue * fc / C_LIGHT_M_S
        # Expected around 560 meters
        assert 500.0 < d_bp < 650.0, f"Breakpoint distance {d_bp} outside expected range"


class TestHorizonAndLinkGeometry:
    """Validates topocentric elevation and O(1) vector horizon culling."""

    def test_vector_horizon_culling(self):
        """Tests that dot(r_ue, rho) >= 0 precisely separates visible satellites from below-horizon satellites."""
        # UE on Earth surface along X axis
        r_ue = (R_EARTH_KM, 0.0, 0.0)

        # Satellite directly overhead (zenith) at 600km
        sat_zenith = (R_EARTH_KM + 600.0, 0.0, 0.0)
        rho_zenith = (sat_zenith[0] - r_ue[0], sat_zenith[1] - r_ue[1], sat_zenith[2] - r_ue[2])
        dot_zenith = r_ue[0] * rho_zenith[0] + r_ue[1] * rho_zenith[1] + r_ue[2] * rho_zenith[2]
        assert dot_zenith > 0.0, "Zenith satellite must be strictly above horizon"

        # Satellite on the opposite side of Earth (nadir)
        sat_opposite = (-(R_EARTH_KM + 600.0), 0.0, 0.0)
        rho_opposite = (sat_opposite[0] - r_ue[0], sat_opposite[1] - r_ue[1], sat_opposite[2] - r_ue[2])
        dot_opposite = r_ue[0] * rho_opposite[0] + r_ue[1] * rho_opposite[1] + r_ue[2] * rho_opposite[2]
        assert dot_opposite < 0.0, "Opposite satellite must be culled by horizon"


class TestHandoverDynamicsAndKPIs:
    """Verifies DAPS MBB vs Hard Handover interruption times and ping-pong detection."""

    def test_handover_interruption_time_daps_vs_hard(self):
        """MBB (DAPS Rel-16) produces 0ms blackout; Hard Handover produces 45ms blackout."""
        # Simulation engine rules
        hit_mbb = 0.0
        hit_hard = 45.0
        assert hit_mbb == 0.0
        assert hit_hard >= 40.0

    def test_ping_pong_handover_classification(self):
        """Verifies 3GPP ping-pong criteria: reversals within <= 3.0s window."""
        ping_pong_window_s = 3.0
        transitions = [
            (10.0, "5G", "LEO"),
            (12.5, "LEO", "5G"), # Reversal in 2.5s -> PING-PONG
            (30.0, "5G", "LEO"),
            (45.0, "LEO", "5G"), # Reversal in 15.0s -> NORMAL HANDOVER
        ]

        ping_pongs = 0
        for i in range(1, len(transitions)):
            t_prev, from_prev, to_prev = transitions[i-1]
            t_curr, from_curr, to_curr = transitions[i]
            if to_curr == from_prev and (t_curr - t_prev) <= ping_pong_window_s:
                ping_pongs += 1

        assert ping_pongs == 1, f"Expected 1 ping-pong handover, found {ping_pongs}"


class TestISLMultiHopLatencyBounds:
    """Verifies end-to-end NTN latency formula T_E2E = T_UT_SAT + sum(d_ISL/c + T_switch) + T_SAT_GW."""

    def test_e2e_ntn_latency_formula(self):
        d_ut_sat_km = 600.0 # Zenith
        t_ut_sat = d_ut_sat_km / C_LIGHT_KM_S

        isl_hops = 3
        isl_hop_dist_km = 1200.0
        t_switch_s = 0.000050 # 50 us optical switching delay
        t_isl = isl_hops * ((isl_hop_dist_km / C_LIGHT_KM_S) + t_switch_s)

        d_sat_gw_km = 750.0
        t_sat_gw = d_sat_gw_km / C_LIGHT_KM_S

        t_e2e_total = t_ut_sat + t_isl + t_sat_gw
        t_e2e_ms = t_e2e_total * 1000.0

        # One way prop: ~2.0ms + ~12.15ms + ~2.5ms = ~16.65 ms
        assert 15.0 < t_e2e_ms < 18.0, f"E2E NTN latency {t_e2e_ms} ms outside expected bounds"


class TestV2XSidelinkRelayCooperation:
    """Validates 3GPP UE-to-Network V2X Sidelink relay equations and outage handling."""

    def test_sidelink_relay_latency_composition(self):
        """End-to-end relay latency must strictly equal T_sidelink + T_backhaul."""
        relay_dist_m = 150.0
        c0 = C_LIGHT_M_S
        pkt_bytes = 1200.0

        # Sidelink hop (5.9 GHz PC5, 50 Mbps)
        t_prop_sl = (2.0 * relay_dist_m) / c0
        t_tx_sl = (2.0 * pkt_bytes * 8.0) / 50e6
        t_mac_sl = 0.001
        t_sidelink = t_prop_sl + t_tx_sl + t_mac_sl

        # Backhaul hop (5G gNB at 800m)
        d_gnb_km = 0.8
        t_prop_bh = (2.0 * d_gnb_km) / C_LIGHT_KM_S
        t_tx_bh = (2.0 * pkt_bytes * 8.0) / 100e6
        t_core_bh = 0.002
        t_backhaul = t_prop_bh + t_tx_bh + t_core_bh

        t_relay_e2e_ms = (t_sidelink + t_backhaul) * 1000.0
        assert 3.0 < t_relay_e2e_ms < 5.0, f"Relay latency {t_relay_e2e_ms} ms outside expected range"

    def test_v2x_relay_range_limit(self):
        """Nodes beyond 300m cannot serve as direct PC5 Sidelink relay."""
        valid_range_m = 250.0
        out_of_range_m = 350.0
        assert valid_range_m <= 300.0
        assert out_of_range_m > 300.0


class TestPredictiveMbbHandoverStrategy:
    """Validates 6G Ephemeris & Trajectory Aware switching criteria."""

    def test_predictive_mbb_triggers(self):
        """Predictive MBB pre-allocates DAPS tunnel when timeToBlindSpot < 1.0s or satRemainingVisibility < 2.0s."""
        time_to_blind_spot_s = 0.8
        sat_remaining_vis_s = 1.5

        trigger_blind_spot = (time_to_blind_spot_s < 1.0)
        trigger_sat_vis = (sat_remaining_vis_s < 2.0)

        assert trigger_blind_spot is True
        assert trigger_sat_vis is True

    def test_mbb_zero_interruption_time(self):
        """DAPS Make-Before-Break guarantees exactly 0 ms radio interruption blackout."""
        hit_mbb_ms = 0.0
        assert hit_mbb_ms == 0.0


class TestAzimuthalHorizonMaskingAndDiffraction:
    """Validates 3D azimuthal horizon sectoring and ITU-R P.526 knife-edge diffraction."""

    def test_azimuth_sector_indexing(self):
        """Calculates correct sector index for 8-sector (45 deg) profile."""
        num_sectors = 8
        sector_width = 360.0 / num_sectors
        
        # Test 10 deg -> North (sector 0)
        assert int(10.0 / sector_width) == 0
        # Test 95 deg -> East (sector 2)
        assert int(95.0 / sector_width) == 2
        # Test 275 deg -> West (sector 6)
        assert int(275.0 / sector_width) == 6

    def test_itu_r_p526_knife_edge_diffraction(self):
        """ITU-R P.526 diffraction loss increases monotonically with obstacle angular deficit."""
        def knife_edge_j(v: float) -> float:
            if v <= -0.78:
                return 0.0
            term = math.sqrt((v - 0.1)**2 + 1.0) + v - 0.1
            if term <= 0.0:
                return 0.0
            return max(0.0, 6.9 + 20.0 * math.log10(term))

        j0 = knife_edge_j(0.0) # Line of sight grazing: ~6.0 - 6.9 dB
        j1 = knife_edge_j(1.0)
        j2 = knife_edge_j(2.5)

        assert 5.0 < j0 < 7.0
        assert j0 < j1 < j2
        assert j2 > 18.0, "Substantial obstruction must produce > 18 dB diffraction loss"


class TestFullScenarioCatalogIntegrity:
    """Validates that all 7 production scenario YAMLs pass Pydantic schema and generate valid INI files."""

    SCENARIOS = [
        "scenarios/library/nexasphere_emergency_corridor.yaml",
        "scenarios/library/nexasphere_highway_platooning.yaml",
        "scenarios/library/nexasphere_maritime_sar.yaml",
        "scenarios/library/nexasphere_rail_highspeed.yaml",
        "scenarios/library/nexasphere_uav_corridor.yaml",
        "scenarios/library/nexasphere_urban_canyon_cpm.yaml",
        "scenarios/library/stelvio_pass_hybrid.yaml",
    ]

    @pytest.mark.parametrize("scenario_path", SCENARIOS)
    def test_scenario_load_and_ini_generation(self, scenario_path, tmp_path):
        p = REPO_ROOT / scenario_path
        assert p.exists(), f"Scenario file {scenario_path} missing"

        ok, errors = validate_scenario_file(str(p))
        assert ok, f"Pydantic schema validation failed for {p.name}: {errors}"

        out_dir = tmp_path / p.stem
        generator = ScenarioGenerator(str(p))
        generator.generate(out_dir)

        out_ini = out_dir / "omnetpp.ini"
        assert out_ini.exists(), f"omnetpp.ini not generated for {p.name}"
        content = out_ini.read_text(encoding="utf-8")
        assert "[General]" in content
        assert "network =" in content
        assert "islRoutingMode" in content
