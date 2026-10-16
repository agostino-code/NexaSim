export interface GnbSite {
  name: string;
  lat: number;
  lon: number;
  height_m?: number;
  tx_power_dbm?: number;
  frequency_ghz?: number;
  bandwidth_mhz?: number;
  coverage_radius_m?: number;
}

export interface GroundStationSite {
  name: string;
  lat: number;
  lon: number;
  altitude_m?: number;
}

export interface BlindSpotZone {
  name: string;
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
  attenuation_db?: number;
}

export interface ScenarioSummary {
  id: string;
  name: string;
  description?: string;
  duration_s: number;
  area_name: string;
  center: [number, number];
  bbox: [number, number, number, number];
  elevation_mask_deg: number;
  switching_mode: string;
  rain_rate: number;
  satellites: number;
  gnbs: GnbSite[];
  ground_stations: GroundStationSite[];
  blind_spots: BlindSpotZone[];
  vehicles: number;
  has_dashboard: boolean;
  has_globe: boolean;
  short_name: string;
}

export interface ScenarioDetail {
  id: string;
  yaml: string;
  data: any;
}

export type RatType = '5G' | 'LEO' | 'V2X';

/**
 * Per-vehicle telemetry. Every metric is `null` when it was not recorded by
 * the simulation (e.g. empty TraCI FCD timesteps, missing vector files).
 * The Studio renders `null` as "not recorded" — it is never replaced with
 * synthesized values.
 */
export interface VehicleTelemetry {
  id: number;
  name: string;
  lat: number | null;
  lon: number | null;
  speed_kmh: number | null;
  throughput_mbps?: number | null;
  mec_latency_ms: number | null;
  qos_score: number | null;
  battery_soc_pct: number | null;
  vho_count: number | null;
  active_rat: RatType | null;
  in_blind: boolean;
  // HUD / kinematic vectors (populated from real .vec traces or live telemetry)
  elevation_deg?: number | null;   // Elevation angle to zenith satellite
  slant_range_km?: number | null;  // Slant range to serving satellite (km)
  doppler_khz?: number | null;     // Doppler shift (kHz)
  carrier_ghz?: number | null;     // Active carrier frequency (GHz)
  heading_deg?: number | null;     // Vehicle heading
  last_updated_s?: number | null;  // Simulation time of last update
}

export interface SimStatus {
  running: boolean;
  run_id: string | null;
  scenario: string | null;
  started_at: string | null;
  logs: string[];
  exit_code: number | null;
}

export interface LiveTelemetryFrame {
  type: string;
  sim_time: number;
  throughput_mbps: number | null;
  latency_ms: number | null;
  active_rat: string | null;
  vehicles: VehicleTelemetry[];
}

/** Response of GET /api/fleet — latest per-vehicle snapshot or honest empty list. */
export interface FleetSnapshot {
  scenario: string;
  sim_time: number | null;
  active_rat?: string | null;
  vehicles: VehicleTelemetry[];
}

/**
 * Fleet-aggregated series from GET /api/telemetry. Entries are null where the
 * metric was not recorded. `qos_score` is optional because older payloads do
 * not include it.
 */
export interface TelemetrySeries {
  timestamps: number[];
  throughput_mbps: (number | null)[];
  rtt_ms: (number | null)[];
  handover_events: (number | null)[];
  active_interface: (number | null)[];
  qos_score?: (number | null)[];
}

export interface KpiSummary {
  scenario: string;
  satellites_count?: number;
  gnbs_count?: number;
  user_terminals_count?: number;
  cell_usage_pct?: number | null;
  sat_usage_pct?: number | null;
  total_vho_switches?: number;
  mean_qos_score?: number | null;
  final_battery_soc?: number | null;
  pdr_pct?: number | null;
  packets_sent?: number;
  packets_rcvd?: number;
  packets_dropped?: number;
  avg_latency_ms?: number | null;
  avg_jitter_ms?: number | null;
  one_way_prop_delay_ms?: number;
  direct_rtt_ms?: number;
  throughput_mbps?: number | null;
}
