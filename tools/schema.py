#!/usr/bin/env python3
"""
NexaSim YAML Scenario Schema & Validator (Pydantic v2)
Horizon Europe NexaSphere Research Project

Provides declarative structural and physical parameter validation
and exports JSON Schema for IDE autocomplete and linting.
"""

import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

class ScenarioMeta(BaseModel):
    name: str = Field(..., description="Unique scenario identifier")
    description: Optional[str] = Field(None, description="Human readable scenario description")
    version: Optional[str] = Field("1.0", description="Configuration schema version")

class AreaConfig(BaseModel):
    name: str = Field(..., description="Geographic area name")
    center_lat: float = Field(..., ge=-90.0, le=90.0, description="Center latitude in degrees")
    center_lon: float = Field(..., ge=-180.0, le=180.0, description="Center longitude in degrees")
    altitude_m: Optional[float] = Field(0.0, description="Mean reference altitude in meters")
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="[min_lon, min_lat, max_lon, max_lat]")
    elevation_mask_deg: Optional[float] = Field(15.0, ge=0.0, le=90.0, description="Orographic terrain elevation mask in degrees")

    @field_validator('bbox')
    @classmethod
    def check_bbox_order(cls, v):
        min_lon, min_lat, max_lon, max_lat = v
        if min_lon > max_lon:
            raise ValueError(f"min_lon ({min_lon}) cannot be greater than max_lon ({max_lon})")
        if min_lat > max_lat:
            raise ValueError(f"min_lat ({min_lat}) cannot be greater than max_lat ({max_lat})")
        return v

class TimeConfig(BaseModel):
    start: Optional[str] = Field("2026-08-26T10:00:00Z", description="ISO 8601 start timestamp")
    duration_s: float = Field(..., gt=0, description="Total simulation time limit in seconds")
    warmup_s: Optional[float] = Field(10.0, ge=0, description="Initial warm-up period in seconds")
    timezone: Optional[str] = Field("Europe/Rome", description="Timezone name")

class ShellConfig(BaseModel):
    name: str = Field(..., description="Orbital shell identifier")
    altitude_km: float = Field(..., ge=150.0, le=2000.0, description="LEO orbital altitude in km")
    inclination_deg: float = Field(..., ge=0.0, le=180.0, description="Orbital inclination in degrees")
    num_planes: int = Field(..., gt=0, description="Number of orbital planes")
    sats_per_plane: int = Field(..., gt=0, description="Number of satellites per plane")
    phase_offset: Optional[float] = Field(0.0, description="Walker phase offset parameter F")

class ISLConfig(BaseModel):
    enabled: bool = Field(True, description="Enable Inter-Satellite Links (ISL)")
    type: Optional[str] = Field("laser", description="'laser' (1550nm) or 'rf_v_band' (60GHz)")
    wavelength_nm: Optional[float] = Field(1550.0, gt=0, description="Laser wavelength in nm")
    max_range_km: Optional[float] = Field(5000.0, gt=0, description="Maximum link range in km")
    num_ports_per_sat: Optional[int] = Field(4, ge=1, le=8, description="Number of laser transceivers per satellite")
    tx_power_dbm: Optional[float] = Field(20.0, description="Optical transmission power in dBm")
    rx_sensitivity_dbm: Optional[float] = Field(-40.0, description="Receiver sensitivity threshold in dBm")
    pointing_accuracy_deg: Optional[float] = Field(0.01, ge=0, description="Pointing accuracy PAT in degrees")
    acquisition_time_ms: Optional[float] = Field(80.0, ge=0, description="Beam acquisition time in ms")

class GroundStationConfig(BaseModel):
    name: str = Field(..., description="Ground Station identifier")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    altitude_m: Optional[float] = Field(50.0)
    feeder_link: Optional[Dict[str, Any]] = None
    user_link: Optional[Dict[str, Any]] = None
    elevation_mask_deg: Optional[float] = Field(10.0, ge=0.0, le=90.0)

class ConstellationConfig(BaseModel):
    type: str = Field("starlink_shell", description="'starlink_shell', 'walker_delta', or 'custom_tle'")
    shells: Optional[List[ShellConfig]] = Field(default_factory=list)
    walkerT: Optional[int] = None
    walkerP: Optional[int] = None
    walkerF: Optional[int] = None
    walkerAltitudeKm: Optional[float] = None
    walkerInclinationDeg: Optional[float] = None
    isl: Optional[ISLConfig] = Field(default_factory=ISLConfig)
    ground_stations: Optional[List[GroundStationConfig]] = Field(default_factory=list)

class GNBSiteConfig(BaseModel):
    name: str = Field(..., description="Base station identifier")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    height_m: Optional[float] = Field(25.0, ge=0)
    tx_power_dbm: Optional[float] = Field(46.0)
    frequency_ghz: Optional[float] = Field(3.5, gt=0)
    bandwidth_mhz: Optional[float] = Field(100.0, gt=0)
    mimo_layers: Optional[int] = Field(4, ge=1)
    coverage_radius_m: Optional[float] = Field(1500.0, gt=0)

class BlindSpotConfig(BaseModel):
    name: str = Field(..., description="Blind spot name")
    lat_min: float = Field(..., ge=-90.0, le=90.0)
    lat_max: float = Field(..., ge=-90.0, le=90.0)
    lon_min: float = Field(..., ge=-180.0, le=180.0)
    lon_max: float = Field(..., ge=-180.0, le=180.0)
    attenuation_db: Optional[float] = Field(40.0, ge=0)

class PhasedArrayConfig(BaseModel):
    elements: Optional[int] = Field(64, ge=1)
    gain_dbi: Optional[float] = Field(32.0)
    scan_angle_max_deg: Optional[float] = Field(60.0, ge=0, le=90)
    beamwidth_deg: Optional[float] = Field(8.5, gt=0)
    tracking_rate_deg_per_sec: Optional[float] = Field(45.0, gt=0)

class DualConnectivityConfig(BaseModel):
    enabled: bool = Field(True)
    mode: Optional[str] = Field("mrdc")
    primary_rat: Optional[str] = Field("terrestrial_5g")
    fallback_rat: Optional[str] = Field("satellite_ntn")
    seamless_failover: Optional[bool] = Field(True)

class UEConfig(BaseModel):
    count: int = Field(..., ge=1, description="Number of simulated vehicles / user terminals")
    mobility_model: Optional[str] = Field("highway_platooning_linear")
    speed_kmh: Optional[float] = Field(50.0, ge=0)
    altitude_m: Optional[float] = Field(1.5)
    dual_connectivity: Optional[DualConnectivityConfig] = Field(default_factory=DualConnectivityConfig)
    phased_array: Optional[PhasedArrayConfig] = Field(default_factory=PhasedArrayConfig)

class TerrestrialConfig(BaseModel):
    gnb: Optional[Dict[str, Any]] = None
    blind_spots: Optional[List[BlindSpotConfig]] = Field(default_factory=list)
    channel_model: Optional[str] = Field("RMa")
    ue: Optional[UEConfig] = None
    integration: Optional[Dict[str, Any]] = None
    alpine_weather: Optional[Dict[str, Any]] = None

class IncidentConfig(BaseModel):
    enabled: bool = Field(False)
    trigger_time_s: Optional[float] = Field(45.0, ge=0)
    location: Optional[Dict[str, Any]] = None
    vehicle_id: Optional[int] = Field(1, ge=0)
    event_type: Optional[str] = Field("collision")
    message_type: Optional[str] = Field("ETSI_DENM")
    data_payload_bytes: Optional[int] = Field(1200, ge=0)
    alert_interval_ms: Optional[int] = Field(100, ge=10)

class OutputConfig(BaseModel):
    directory: Optional[str] = Field("output/scenario")
    metrics: Optional[List[str]] = Field(default_factory=list)
    format: Optional[str] = Field("csv")
    write_interval_s: Optional[float] = Field(0.5, gt=0)

class ScenarioSpec(BaseModel):
    name: str = Field(...)
    description: Optional[str] = None
    version: Optional[str] = "1.0"
    area: Optional[AreaConfig] = None
    time: Optional[TimeConfig] = None
    constellation: Optional[ConstellationConfig] = None
    terrestrial: Optional[TerrestrialConfig] = None
    incident: Optional[IncidentConfig] = Field(default_factory=IncidentConfig)
    output: Optional[OutputConfig] = Field(default_factory=OutputConfig)

class ScenarioDocument(BaseModel):
    scenario: ScenarioSpec

def validate_scenario_file(yaml_path: Union[str, Path]) -> tuple[bool, List[str]]:
    """Validate a YAML scenario file against Pydantic schema."""
    path = Path(yaml_path)
    if not path.exists():
        return False, [f"File not found: {path}"]

    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
    except Exception as e:
        return False, [f"YAML parsing error: {e}"]

    if not isinstance(raw_data, dict):
        return False, ["Root element must be a YAML mapping containing 'scenario:'"]

    try:
        ScenarioDocument(**raw_data)
        return True, []
    except Exception as e:
        error_msgs = []
        if hasattr(e, 'errors'):
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err.get('loc', []))
                msg = err.get('msg', 'Validation error')
                error_msgs.append(f"{loc}: {msg}")
        else:
            error_msgs.append(str(e))
        return False, error_msgs

def export_json_schema(output_path: Union[str, Path]):
    """Export standard JSON Schema for IDE autocomplete and schema validation."""
    schema = ScenarioDocument.model_json_schema()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2)
    print(f"[+] Exported JSON Schema to: {out}")

if __name__ == '__main__':
    schema_dir = Path(__file__).resolve().parent.parent / 'scenarios' / 'schema'
    schema_file = schema_dir / 'scenario.schema.json'
    export_json_schema(schema_file)

    if len(sys.argv) > 1:
        target = sys.argv[1]
        ok, errors = validate_scenario_file(target)
        if ok:
            print(f"Validation successful for {target}")
            sys.exit(0)
        else:
            print(f"Validation failed for {target}:")
            for err in errors:
                print(f"  • {err}")
            sys.exit(1)
