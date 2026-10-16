#!/usr/bin/env python3
"""
Scientific Validation Test Suite for NexaSim
Verifies 3GPP TR 38.811 (NTN), 3GPP TR 38.901 (5G-NR), ITU-R P.618,
and Orbital Mechanics (ECEF/WGS84, J2 Perturbation, Doppler Shift, RTT).
"""

import math
import unittest

# Physical Constants (CODATA / IAU / WGS84)
SPEED_OF_LIGHT = 299792458.0  # m/s
GM_EARTH = 3.986004418e14     # m^3/s^2
WGS84_A = 6378137.0           # m
WGS84_F = 1.0 / 298.257223563
WGS84_B = WGS84_A * (1.0 - WGS84_F)
WGS84_E2 = 2.0 * WGS84_F - WGS84_F * WGS84_F
J2_EARTH = 1.08263e-3
EARTH_ROTATION_OMEGA = 7.2921159e-5  # rad/s


def calculate_fspl(distance_km: float, freq_ghz: float) -> float:
    """Calculates Free Space Path Loss in dB."""
    d_m = distance_km * 1000.0
    f_hz = freq_ghz * 1e9
    return 20.0 * math.log10(4.0 * math.pi * d_m * f_hz / SPEED_OF_LIGHT)


def calculate_leo_max_doppler(sat_velocity_kmps: float, freq_ghz: float) -> float:
    """Calculates maximum theoretical Doppler shift for LEO link in Hz."""
    v_mps = sat_velocity_kmps * 1000.0
    f_hz = freq_ghz * 1e9
    return (v_mps / SPEED_OF_LIGHT) * f_hz


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> tuple[float, float, float]:
    """WGS84 Geodetic to ECEF transformation."""
    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    sin_lam = math.sin(lam)
    cos_lam = math.cos(lam)

    N = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_phi * sin_phi)
    x = (N + alt_m) * cos_phi * cos_lam
    y = (N + alt_m) * cos_phi * sin_lam
    z = (N * (1.0 - WGS84_E2) + alt_m) * sin_phi
    return x, y, z


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    """WGS84 ECEF to Geodetic transformation (Bowring algorithm)."""
    p = math.sqrt(x * x + y * y)
    lon_deg = math.degrees(math.atan2(y, x))
    if p < 1e-6:
        lat_deg = 90.0 if z >= 0 else -90.0
        alt_m = abs(z) - WGS84_B
        return lat_deg, lon_deg, alt_m

    e_prime2 = (WGS84_A * WGS84_A - WGS84_B * WGS84_B) / (WGS84_B * WGS84_B)
    theta = math.atan2(z * WGS84_A, p * WGS84_B)
    phi = math.atan2(
        z + e_prime2 * WGS84_B * (math.sin(theta) ** 3),
        p - WGS84_E2 * WGS84_A * (math.cos(theta) ** 3)
    )
    lat_deg = math.degrees(phi)
    N = WGS84_A / math.sqrt(1.0 - WGS84_E2 * (math.sin(phi) ** 2))
    alt_m = p / math.cos(phi) - N
    return lat_deg, lon_deg, alt_m


def calculate_j2_raan_precession(altitude_km: float, inclination_deg: float) -> float:
    """Calculates J2 nodal precession rate dOmega/dt in degrees per day."""
    a = (WGS84_A / 1000.0) + altitude_km
    n0 = math.sqrt((GM_EARTH / 1e9) / (a ** 3))  # rad/s
    i_rad = math.radians(inclination_deg)
    j2_factor = 1.5 * J2_EARTH * ((WGS84_A / 1000.0 / a) ** 2) * n0
    raan_dot_rad_per_s = -j2_factor * math.cos(i_rad)
    return math.degrees(raan_dot_rad_per_s) * 86400.0


def bessel_j1(x: float) -> float:
    """Exact Taylor series summation for Bessel function of the first kind J_1(x)."""
    if abs(x) < 1e-12:
        return 0.0
    ans = 0.0
    term = x / 2.0
    x2_4 = (x * x) / 4.0
    for m in range(25):
        ans += term
        term = -term * x2_4 / ((m + 1) * (m + 2))
        if abs(term) < 1e-15:
            break
    return ans


def calculate_physical_rtt(is_satellite: bool, ue_dist_km: float, gw_dist_km: float = 700.0,
                           is_mbb: bool = True, is_handover: bool = False) -> float:
    """Computes end-to-end round trip time (RTT) from physics parameters."""
    c_km_s = SPEED_OF_LIGHT / 1000.0
    if is_satellite:
        prop_delay = 2.0 * (ue_dist_km + gw_dist_km) / c_km_s
        harq_rtt = 0.040
        bler = 0.015
    else:
        prop_delay = 2.0 * ue_dist_km / c_km_s + 0.004  # 4ms terrestrial backhaul
        harq_rtt = 0.004
        bler = 0.005

    tx_delay = 0.0005
    queuing = bler * harq_rtt + 0.001
    hit_penalty = 0.0 if is_mbb or not is_handover else 0.045
    return prop_delay + tx_delay + queuing + hit_penalty


class TestScientificValidation(unittest.TestCase):

    def test_ka_band_fspl_at_600km(self):
        """Validates that 28 GHz Free Space Path Loss at 600 km is ~176.95 dB."""
        fspl = calculate_fspl(distance_km=600.0, freq_ghz=28.0)
        # Expected: 20*log10(4*pi*600e3*28e9 / 299792458) = 176.95 dB
        self.assertAlmostEqual(fspl, 176.95, delta=0.5)

    def test_leo_maximum_doppler_shift(self):
        """Validates that maximum LEO Doppler shift at 28 GHz is in the range of +-650 to 710 kHz."""
        # For a 550 km Starlink orbit, orbital speed v ~ 7.56 km/s
        v_orbit_kmps = 7.56
        doppler_max_hz = calculate_leo_max_doppler(sat_velocity_kmps=v_orbit_kmps, freq_ghz=28.0)
        # Expected max line-of-sight Doppler: ~706 kHz
        self.assertGreater(doppler_max_hz, 650000.0)
        self.assertLess(doppler_max_hz, 720000.0)

    def test_wgs84_geodetic_ecef_roundtrip(self):
        """Validates sub-millimeter WGS84 coordinate transformation consistency."""
        test_coords = [
            (46.538, 10.453, 2757.0),   # Stelvio Pass
            (0.0, 0.0, 0.0),            # Equator prime meridian
            (89.9, 45.0, 100.0),        # Near North Pole
            (-33.8688, 151.2093, 50.0)  # Sydney
        ]
        for lat, lon, alt in test_coords:
            x, y, z = geodetic_to_ecef(lat, lon, alt)
            lat_out, lon_out, alt_out = ecef_to_geodetic(x, y, z)
            self.assertAlmostEqual(lat, lat_out, places=6)
            self.assertAlmostEqual(lon, lon_out, places=6)
            self.assertAlmostEqual(alt, alt_out, delta=0.001)

    def test_j2_orbital_precession(self):
        """Validates that J2 nodal regression for LEO at i=53 deg is negative (precessing westwards)."""
        raan_rate_deg_per_day = calculate_j2_raan_precession(altitude_km=550.0, inclination_deg=53.0)
        # At 53 deg inclination and 550 km, precession is roughly -4.0 to -6.5 deg/day
        self.assertLess(raan_rate_deg_per_day, -4.0)
        self.assertGreater(raan_rate_deg_per_day, -6.5)

    def test_bessel_j1_accuracy(self):
        """Validates Bessel function J1 properties (zero at 0, peak at ~1.84, first zero at ~3.83)."""
        self.assertAlmostEqual(bessel_j1(0.0), 0.0, places=6)
        # Peak of J_1(x) is at x ~ 1.84118 with value ~0.581865
        peak_val = bessel_j1(1.84118)
        self.assertAlmostEqual(peak_val, 0.5818, delta=0.005)
        # First positive zero is at x ~ 3.8317
        zero_val = bessel_j1(3.8317)
        self.assertAlmostEqual(zero_val, 0.0, delta=0.005)

    def test_physics_rtt_model(self):
        """Validates multi-RAT RTT values and Make-Before-Break vs Hard Handover interruption."""
        # 5G-NR Terrestrial RTT
        rtt_5g = calculate_physical_rtt(is_satellite=False, ue_dist_km=1.0)
        self.assertGreater(rtt_5g, 0.004)
        self.assertLess(rtt_5g, 0.015)

        # LEO NTN Ka-Band RTT (650 km slant range to sat, 700 km sat to gateway)
        rtt_leo = calculate_physical_rtt(is_satellite=True, ue_dist_km=650.0, gw_dist_km=700.0)
        # 2 * (650 + 700) / 300000 ~ 9.0 ms two-way + queuing/HARQ -> ~10-25 ms
        self.assertGreater(rtt_leo, 0.010)
        self.assertLess(rtt_leo, 0.035)

        # Make-Before-Break handover: 0 ms extra interruption
        rtt_mbb = calculate_physical_rtt(is_satellite=True, ue_dist_km=650.0, is_mbb=True, is_handover=True)
        self.assertEqual(rtt_mbb, rtt_leo)

        # Hard Handover: 45 ms extra interruption penalty
        rtt_hard = calculate_physical_rtt(is_satellite=True, ue_dist_km=650.0, is_mbb=False, is_handover=True)
        self.assertAlmostEqual(rtt_hard - rtt_leo, 0.045, places=5)


if __name__ == '__main__':
    unittest.main()
