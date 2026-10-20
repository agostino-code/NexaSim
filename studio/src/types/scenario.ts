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
  elevation_mask_deg?: number;
  feeder_link?: {
    frequency_ghz: number;
    bandwidth_mhz: number;
  };
}

export interface BlindSpotZone {
  name: string;
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
  attenuation_db?: number;
}

export interface ConstellationShell {
  name: string;
  altitude_km: number;
  inclination_deg: number;
  num_planes: number;
  sats_per_plane: number;
  phase_offset?: number;
}

export interface SatelliteISLConfig {
  enabled: boolean;
  type?: string;
  wavelength_nm?: number;
  max_range_km?: number;
  num_ports_per_sat?: number;
}

export interface MecServerConfig {
  name: string;
  lat: number;
  lon: number;
  compute_capacity_mips?: number;
  storage_gb?: number;
  assigned_gnb?: string;
}

export interface ScenarioAreaConfig {
  name: string;
  center_lat: number;
  center_lon: number;
  altitude_m?: number | null;
  bbox: [number, number, number, number]; // [min_lon, min_lat, max_lon, max_lat]
  elevation_mask_deg?: number | null;
  environment_profile?: 'urban' | 'suburban' | 'rural' | 'alpine' | string;
}

export interface ScenarioTimeConfig {
  start?: string;
  duration_s: number;
  warmup_s?: number;
  timezone?: string;
}

export interface ScenarioConstellationConfig {
  type?: string;
  shells?: ConstellationShell[];
  isl?: SatelliteISLConfig;
  ground_stations?: GroundStationSite[];
}

export interface ScenarioTerrestrialConfig {
  gnb?: {
    deployment?: string;
    count?: number;
    sites?: GnbSite[];
    inter_site_distance_m?: number;
  };
  ue?: {
    count?: number;
    mobility?: string;
    speed_kmh?: number;
  };
  blind_spots?: BlindSpotZone[];
  switching_mode?: string;
  alpine_weather?: {
    rain_rate_mm_hr?: number;
    cloud_attenuation_db?: number;
  };
  mec?: {
    enabled?: boolean;
    servers?: MecServerConfig[];
  };
  services?: string[];
}

export interface ScenarioUavConfig {
  corridor_name?: string;
  altitude_m?: number;
  waypoints?: [number, number, number][]; // [lon, lat, alt]
  uas_count?: number;
}

export interface ScenarioMaritimeConfig {
  area_name?: string;
  vessels_count?: number;
  sar_mission?: boolean;
}

export interface ScenarioRailConfig {
  track_id?: string;
  trains_count?: number;
  frequency_ghz?: number;
}

export interface ScenarioConfig {
  scenario: {
    name: string;
    description?: string;
    version?: string;
    time: ScenarioTimeConfig;
    area: ScenarioAreaConfig;
    constellation?: ScenarioConstellationConfig;
    terrestrial?: ScenarioTerrestrialConfig;
    uav?: ScenarioUavConfig;
    maritime?: ScenarioMaritimeConfig;
    rail?: ScenarioRailConfig;
  };
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
  elevation_deg?: number | null;
  slant_range_km?: number | null;
  doppler_khz?: number | null;
  carrier_ghz?: number | null;
  heading_deg?: number | null;
  last_updated_s?: number | null;
  // Multi-domain support
  domain?: 'vehicle' | 'uav' | 'ship' | 'train';
  altitude_m?: number | null;
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

export interface FleetSnapshot {
  scenario: string;
  sim_time: number | null;
  active_rat?: string | null;
  vehicles: VehicleTelemetry[];
}

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
  v2x_usage_pct?: number | null;
  total_vho_switches?: number;
  ping_pong_handovers?: number | null;
  ping_pong_rate_pct?: number | null;
  mean_qos_score?: number | null;
  final_battery_soc?: number | null;
  energy_per_mb_joules?: number | null;
  pdr_pct?: number | null;
  mean_bler_pct?: number | null;
  outage_time_pct?: number | null;
  packets_sent?: number;
  packets_rcvd?: number;
  packets_dropped?: number;
  avg_latency_ms?: number | null;
  latency_p95_ms?: number | null;
  latency_p99_ms?: number | null;
  avg_jitter_ms?: number | null;
  one_way_prop_delay_ms?: number;
  direct_rtt_ms?: number;
  throughput_mbps?: number | null;
}

export interface FleetTimelinePoint {
  t: number;
  speed_kmh?: number | null;
  throughput_mbps?: number | null;
  mec_latency_ms?: number | null;
  qos_score?: number | null;
  battery_soc_pct?: number | null;
  vho_count?: number | null;
  active_rat?: RatType | null;
  elevation_deg?: number | null;
  slant_range_km?: number | null;
  doppler_khz?: number | null;
  carrier_ghz?: number | null;
  heading_deg?: number | null;
  domain?: string;
  altitude_m?: number | null;
}

export interface FleetTimelineResponse {
  scenario: string;
  timestamps: number[];
  vehicles_timeline: Record<string, FleetTimelinePoint[]>;
}

export interface CompareResponse {
  available: boolean;
  scenario: string;
  baseline_strategy?: string | null;
  kpis?: KpiSummary | null;
  telemetry?: TelemetrySeries | null;
}

export type SelectedNodeType = 'gnb' | 'gs' | 'blind' | 'veh' | 'sat' | 'uav' | 'ship' | 'train' | 'mec';

export interface SelectedNode {
  type: SelectedNodeType;
  index: number;
  data: any;
}

// -------------------------------------------------------------
// Multi-Scale 2D/3D Unified Engine & Digital Twin Entity Types
// -------------------------------------------------------------
export type SimulationDomain = 'terrestrial' | 'space' | 'aerial' | 'maritime' | 'rail';

export interface SatelliteEntity {
  id: string;
  name: string;
  planeIndex: number;
  satIndex: number;
  altitudeKm: number;
  lat: number;
  lon: number;
  altM: number;
  tleLine1?: string;
  tleLine2?: string;
  footprintRadiusKm?: number;
  elevationDeg?: number;
}

export interface SimulationRadioLink {
  id: string;
  sourceId: string;
  targetId: string;
  sourcePos: [number, number, number]; // [lon, lat, alt]
  targetPos: [number, number, number]; // [lon, lat, alt]
  rat: 'ITS-G5' | '5G-NR' | 'LEO-NTN' | 'ISL' | 'MEC';
  state: 'los' | 'nlos_v' | 'nlos_b' | 'active' | 'outage';
  sinrDb?: number;
  latencyMs?: number;
  color?: [number, number, number, number];
}

export interface SimulationFrame {
  simTime: number;
  vehicles: VehicleTelemetry[];
  satellites: SatelliteEntity[];
  links: SimulationRadioLink[];
  aggregates?: {
    throughput_mbps: number | null;
    latency_ms: number | null;
    active_rat: string | null;
  };
}

export type WorkspaceMode = 'design' | 'live' | 'analyze';

export interface LayersVisibility {
  vehicles: boolean;
  uavs: boolean;
  ships: boolean;
  trains: boolean;
  rsuAndGnb: boolean;
  groundStations: boolean;
  leoSatellites: boolean;
  leoOrbits: boolean;
  islLinks: boolean;
  v2xLinks: boolean;
  nrLinks: boolean;
  ntnLinks: boolean;
  sensorCones: boolean;
  gemv2LosRays: boolean;
  buildings3D: boolean;
  terrain3D: boolean;
}

export type DrawingToolType =
  | 'select'
  | 'bbox_osm'
  | 'route_polyline'
  | 'uav_corridor'
  | 'place_rsu'
  | 'place_gnb'
  | 'place_ground_station'
  | 'place_blind_spot'
  | 'region_of_interest';

export interface ValidationError {
  path: string;
  message: string;
  keyword?: string;
}
