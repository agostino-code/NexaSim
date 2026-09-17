#!/usr/bin/env python3
"""
Artery Integrated TN-NTN Scenario Generator

Generates OMNeT++ simulation scenarios from YAML configuration files.
Supports:
- LEO constellations (Walker Delta, Starlink shells)
- Terrestrial 5G/6G networks (gNB deployment)
- User terminals with dual connectivity
- Ground stations and gateways
- ISL topology
"""

import yaml
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import math

@dataclass
class Satellite:
    name: str
    plane_id: int
    sat_id: int
    global_id: int
    altitude_km: float
    inclination_deg: float
    raan_deg: float
    mean_anomaly_deg: float
    arg_perigee_deg: float = 0.0
    eccentricity: float = 0.0
    
    def to_tle(self) -> tuple:
        """Generate TLE lines for this satellite"""
        # Simplified TLE generation
        sat_num = self.global_id % 99999
        epoch_year = 24
        epoch_day = 1.0
        
        line1 = f"1 {sat_num:05d}U 99999A   {epoch_year:02d}{epoch_day:012.8f}  .00000000  00000-0  00000-0 0  9990"
        line2 = f"2 {sat_num:05d} {self.inclination_deg:8.4f} {self.raan_deg:8.4f} {int(self.eccentricity*1e7):07d} {self.arg_perigee_deg:8.4f} {self.mean_anomaly_deg:8.4f} {14.2:11.8f}"
        
        return line1, line2

@dataclass
class GroundStation:
    name: str
    lat: float
    lon: float
    alt: float
    elevation_mask_deg: float = 10.0
    feeder_freq_ghz: float = 28.0
    feeder_bw_mhz: float = 1000.0
    user_freq_ghz: float = 28.0
    user_bw_mhz: float = 500.0

@dataclass
class GNB:
    name: str
    gnb_type: str  # macro, micro, mmwave
    lat: float
    lon: float
    height_m: float
    tx_power_dbm: float
    frequency_ghz: float
    bandwidth_mhz: float
    mimo_layers: int
    beamforming: bool = True

@dataclass
class UserTerminal:
    terminal_id: int
    terminal_type: str
    lat: float
    lon: float
    array_elements: int = 64
    dual_connectivity: bool = False

class ScenarioGenerator:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.scenario = self.config.get('scenario', {})
        self.constellation = self.scenario.get('constellation', {})
        self.terrestrial = self.scenario.get('terrestrial', {})
        self.output = self.scenario.get('output', {})
        self.area = self.scenario.get('area', {})
        self.time = self.scenario.get('time', {})
        
        self.satellites: List[Satellite] = []
        self.ground_stations: List[GroundStation] = []
        self.gnbs: List[GNB] = []
        self.user_terminals: List[UserTerminal] = []

    def build(self):
        """Build in-memory network topology from config"""
        if not self.satellites and not self.gnbs and not self.user_terminals:
            self._generate_constellation()
            self._generate_terrestrial()
            self._generate_user_terminals()
    
    def generate(self, output_dir: str):
        """Generate all scenario files"""
        os.makedirs(output_dir, exist_ok=True)
        self.build()
        
        # Write OMNeT++ files
        self._write_ned_file(output_dir)
        self._write_ini_file(output_dir)
        self._write_tle_file(output_dir)
        self._write_mobility_file(output_dir)
        
        print(f"Scenario generated in {output_dir}")
    
    def _generate_constellation(self):
        """Generate satellite constellation from config"""
        const_type = self.constellation.get('type', 'starlink_shell')
        shells = self.constellation.get('shells', [])
        
        if const_type == 'walker_delta':
            self._generate_walker_delta()
        elif const_type == 'starlink_shell':
            self._generate_starlink_shells(shells)
        else:
            print(f"Unknown constellation type: {const_type}")
        
        # Ground stations
        for gs_config in self.constellation.get('ground_stations', []):
            gs = GroundStation(
                name=gs_config['name'],
                lat=gs_config['lat'],
                lon=gs_config['lon'],
                alt=gs_config.get('altitude_m', 50),
                elevation_mask_deg=gs_config.get('elevation_mask_deg', 10.0),
                feeder_freq_ghz=gs_config.get('feeder_link', {}).get('frequency_ghz', 28.0),
                feeder_bw_mhz=gs_config.get('feeder_link', {}).get('bandwidth_mhz', 1000.0),
                user_freq_ghz=gs_config.get('user_link', {}).get('frequency_ghz', 28.0),
                user_bw_mhz=gs_config.get('user_link', {}).get('bandwidth_mhz', 500.0),
            )
            self.ground_stations.append(gs)
    
    def _generate_walker_delta(self):
        """Generate Walker Delta constellation"""
        T = self.constellation.get('walkerT', 72)
        P = self.constellation.get('walkerP', 12)
        F = self.constellation.get('walkerF', 0)
        altitude = self.constellation.get('walkerAltitudeKm', 550)
        inclination = self.constellation.get('walkerInclinationDeg', 53.0)
        
        sats_per_plane = T // P
        global_id = 0
        
        for p in range(P):
            raan = p * (360.0 / P)
            for s in range(sats_per_plane):
                mean_anomaly = s * (360.0 / sats_per_plane) + F * p * (360.0 / T)
                
                sat = Satellite(
                    name=f"sat_{p}_{s}",
                    plane_id=p,
                    sat_id=s,
                    global_id=global_id,
                    altitude_km=altitude,
                    inclination_deg=inclination,
                    raan_deg=raan,
                    mean_anomaly_deg=mean_anomaly % 360.0,
                )
                self.satellites.append(sat)
                global_id += 1
    
    def _generate_starlink_shells(self, shells: List[Dict]):
        """Generate Starlink-like multi-shell constellation"""
        global_id = 0
        
        for shell in shells:
            name = shell.get('name', 'shell')
            altitude = shell.get('altitude_km', 550)
            inclination = shell.get('inclination_deg', 53.0)
            num_planes = shell.get('num_planes', 12)
            sats_per_plane = shell.get('sats_per_plane', 6)
            phase_offset = shell.get('phase_offset', 0)
            
            for p in range(num_planes):
                raan = p * (360.0 / num_planes)
                for s in range(sats_per_plane):
                    mean_anomaly = s * (360.0 / sats_per_plane) + phase_offset * p * (360.0 / (num_planes * sats_per_plane))
                    
                    sat = Satellite(
                        name=f"{name}_sat_{p}_{s}",
                        plane_id=p,
                        sat_id=s,
                        global_id=global_id,
                        altitude_km=altitude,
                        inclination_deg=inclination,
                        raan_deg=raan,
                        mean_anomaly_deg=mean_anomaly % 360.0,
                    )
                    self.satellites.append(sat)
                    global_id += 1
    
    def _generate_terrestrial(self):
        """Generate terrestrial gNB deployment"""
        gnb_config = self.terrestrial.get('gnb', {})
        deployment = gnb_config.get('deployment', 'grid')
        density = gnb_config.get('density_per_km2', 5)
        isd = gnb_config.get('inter_site_distance_m', 1000)
        
        # Parse area
        bbox = self.area.get('bbox', [13.0, 52.3, 13.6, 52.7])
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Get gNB types
        types = gnb_config.get('types', [
            {'name': 'macro', 'ratio': 1.0, 'height_m': 25, 'tx_power_dbm': 46, 
             'frequency_ghz': 3.5, 'bandwidth_mhz': 100, 'mimo_layers': 4}
        ])
        
        if deployment == 'custom':
            for site in gnb_config.get('sites', []):
                gnb = GNB(
                    name=site['name'],
                    gnb_type=site.get('type', 'macro'),
                    lat=site['lat'],
                    lon=site['lon'],
                    height_m=site.get('height_m', 25),
                    tx_power_dbm=site.get('tx_power_dbm', 46),
                    frequency_ghz=site.get('frequency_ghz', 3.5),
                    bandwidth_mhz=site.get('bandwidth_mhz', 100),
                    mimo_layers=site.get('mimo_layers', 4),
                    beamforming=site.get('beamforming', True),
                )
                self.gnbs.append(gnb)
        elif deployment == 'grid':
            # Grid deployment
            lat_step = isd / 111000.0  # degrees
            lon_step = isd / (111000.0 * math.cos(math.radians((min_lat + max_lat) / 2)))
            
            gnb_id = 0
            lat = min_lat
            while lat < max_lat:
                lon = min_lon
                while lon < max_lon:
                    # Select type based on ratio
                    import random
                    r = random.random()
                    cumulative = 0
                    selected_type = types[0]
                    for t in types:
                        cumulative += t.get('ratio', 1.0)
                        if r <= cumulative:
                            selected_type = t
                            break
                    
                    gnb = GNB(
                        name=f"gnb_{gnb_id}",
                        gnb_type=selected_type['name'],
                        lat=lat,
                        lon=lon,
                        height_m=selected_type.get('height_m', 25),
                        tx_power_dbm=selected_type.get('tx_power_dbm', 46),
                        frequency_ghz=selected_type.get('frequency_ghz', 3.5),
                        bandwidth_mhz=selected_type.get('bandwidth_mhz', 100),
                        mimo_layers=selected_type.get('mimo_layers', 4),
                        beamforming=selected_type.get('beamforming', True),
                    )
                    self.gnbs.append(gnb)
                    gnb_id += 1
                    lon += lon_step
                lat += lat_step
        
        print(f"Generated {len(self.gnbs)} gNBs")
    
    def _generate_user_terminals(self):
        """Generate user terminals"""
        ue_config = self.terrestrial.get('ue', {})
        count = ue_config.get('count', 50)
        mobility = ue_config.get('mobility_model', 'urban_pedestrian')
        dual_conn = ue_config.get('dual_connectivity', {}).get('enabled', False)
        
        bbox = self.area.get('bbox', [13.0, 52.3, 13.6, 52.7])
        min_lon, min_lat, max_lon, max_lat = bbox
        
        import random
        for i in range(count):
            lat = random.uniform(min_lat, max_lat)
            lon = random.uniform(min_lon, max_lon)
            
            ut = UserTerminal(
                terminal_id=i,
                terminal_type='residential',
                lat=lat,
                lon=lon,
                array_elements=64,
                dual_connectivity=dual_conn,
            )
            self.user_terminals.append(ut)
        
        print(f"Generated {len(self.user_terminals)} user terminals")
    
    def _write_ned_file(self, output_dir: str):
        """Write OMNeT++ NED network file"""
        ned_path = os.path.join(output_dir, 'scenario.ned')
        subpkg = Path(output_dir).name
        package_name = f"generated.{subpkg}"
        
        with open(ned_path, 'w') as f:
            f.write(f"""package {package_name};

import artery.ntn.ConstellationManager;
import artery.ntn.LEO_Satellite;
import artery.ntn.GroundStation;
import artery.ntn.UserTerminalNode;
import artery.nr.GNB;
import artery.nr.UE;
import traci.Manager;
import inet.physicallayer.unitdisk.UnitDiskRadioMedium;
import inet.physicallayer.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import inet.visualizer.integrated.IntegratedCanvasVisualizer;

network GeneratedScenario
{{
    parameters:
        @display("bgb=1600,1000");
    submodules:
        visualizer: IntegratedCanvasVisualizer {{
            @display("p=50,50");
        }}
        traci: Manager {{
            @display("p=50,150");
        }}
        constellationManager: ConstellationManager {{
            parameters:
                constellationType = "{self.constellation.get('type', 'starlink_shell')}";
                walkerT = {len(self.satellites)};
                walkerP = {len(set(s.plane_id for s in self.satellites))};
                walkerF = 0;
                walkerAltitudeKm = {self.satellites[0].altitude_km if self.satellites else 550};
                walkerInclinationDeg = {self.satellites[0].inclination_deg if self.satellites else 53.0};
                islEnabled = {str(self.constellation.get('isl', {}).get('enabled', True)).lower()};
            @display("p=50,50");
        }}
        radioMedium: UnitDiskRadioMedium {{
            @display("p=200,50");
        }}
        nrRadioMedium: UnitDiskRadioMedium {{
            @display("p=200,150");
        }}
        wlanRadioMedium: Ieee80211ScalarRadioMedium {{
            @display("p=200,250");
        }}
        satellite[{len(self.satellites)}]: LEO_Satellite {{
            @display("p=400,100");
        }}
        groundStation[{len(self.ground_stations)}]: GroundStation {{
            @display("p=400,300");
        }}
        gnb[{len(self.gnbs)}]: GNB {{
            @display("p=600,100");
        }}
        ue[{len(self.user_terminals)}]: UE {{
            @display("p=600,300");
        }}
        userTerminal[{len(self.user_terminals)}]: UserTerminalNode {{
            @display("p=800,300");
        }}
    connections allowunconnected:
        // Connections established dynamically by managers
}}
""")
        print(f"Written: {ned_path}")
    
    def _write_ini_file(self, output_dir: str):
        """Write OMNeT++ ini configuration file"""
        ini_path = os.path.join(output_dir, 'omnetpp.ini')
        subpkg = Path(output_dir).name
        package_name = f"generated.{subpkg}"
        
        duration = self.time.get('duration_s', 300)
        warmup = self.time.get('warmup_s', 30)
        seed = self.scenario.get('seed', 42)
        
        with open(ini_path, 'w') as f:
            f.write(f"""[General]
network = {package_name}.GeneratedScenario
sim-time-limit = {duration}s
warmup-period = {warmup}s
rng-class = "cMersenneTwister"
seed-set = {seed}

# Constellation Manager
*.constellationManager.constellationType = "{self.constellation.get('type', 'starlink_shell')}"
*.constellationManager.walkerT = {len(self.satellites)}
*.constellationManager.walkerP = {len(set(s.plane_id for s in self.satellites))}
*.constellationManager.walkerAltitudeKm = {self.satellites[0].altitude_km if self.satellites else 550}
*.constellationManager.walkerInclinationDeg = {self.satellites[0].inclination_deg if self.satellites else 53.0}
*.constellationManager.islEnabled = {str(self.constellation.get('isl', {}).get('enabled', True)).lower()}
*.constellationManager.islType = "{self.constellation.get('isl', {}).get('type', 'laser')}"
*.constellationManager.islMaxRangeKm = {self.constellation.get('isl', {}).get('max_range_km', 5000)}
*.constellationManager.islPortsPerSat = {self.constellation.get('isl', {}).get('num_ports_per_sat', 4)}

# Satellite TLEs
""")
            
            # Write TLE and initial positions for each satellite
            for i, sat in enumerate(self.satellites):
                line1, line2 = sat.to_tle()
                f.write(f"*.satellite[{i}].mobility.tleLine1 = \"{line1}\"\n")
                f.write(f"*.satellite[{i}].mobility.tleLine2 = \"{line2}\"\n")
                f.write(f"*.satellite[{i}].mobility.initialX = {sat.raan_deg * 10000}m\n")
                f.write(f"*.satellite[{i}].mobility.initialY = {sat.mean_anomaly_deg * 10000}m\n")
                f.write(f"*.satellite[{i}].mobility.initialZ = {sat.altitude_km * 1000}m\n")
                f.write(f"*.satellite[{i}].manager.satelliteName = \"{sat.name}\"\n")
            
            f.write("\n# Ground Stations\n")
            for i, gs in enumerate(self.ground_stations):
                f.write(f"*.groundStation[{i}].latitude = {gs.lat}\n")
                f.write(f"*.groundStation[{i}].longitude = {gs.lon}\n")
                f.write(f"*.groundStation[{i}].altitude = {gs.alt}\n")
                f.write(f"*.groundStation[{i}].elevationMaskDeg = {gs.elevation_mask_deg}\n")
                f.write(f"*.groundStation[{i}].mobility.initialX = {gs.lon * 111000}m\n")
                f.write(f"*.groundStation[{i}].mobility.initialY = {gs.lat * 111000}m\n")
                f.write(f"*.groundStation[{i}].mobility.initialZ = {gs.alt}m\n")
            
            f.write("\n# gNBs\n")
            for i, gnb in enumerate(self.gnbs):
                f.write(f"*.gnb[{i}].gnbType = {['macro', 'micro', 'mmwave', 'pico'].index(gnb.gnb_type) if gnb.gnb_type in ['macro', 'micro', 'mmwave', 'pico'] else 0}\n")
                f.write(f"*.gnb[{i}].txPowerDbm = {gnb.tx_power_dbm}\n")
                f.write(f"*.gnb[{i}].frequencyGhz = {gnb.frequency_ghz}\n")
                f.write(f"*.gnb[{i}].bandwidthMhz = {gnb.bandwidth_mhz}\n")
                f.write(f"*.gnb[{i}].mimoLayers = {gnb.mimo_layers}\n")
                f.write(f"*.gnb[{i}].mobility.initialX = {gnb.lon * 111000}m\n")
                f.write(f"*.gnb[{i}].mobility.initialY = {gnb.lat * 111000}m\n")
                f.write(f"*.gnb[{i}].mobility.initialZ = {gnb.height_m}m\n")
            
            f.write("\n# User Terminals\n")
            for i, ut in enumerate(self.user_terminals):
                f.write(f"*.userTerminal[{i}].terminal.terminalId = {ut.terminal_id}\n")
                f.write(f"*.userTerminal[{i}].terminal.terminalType = \"{ut.terminal_type}\"\n")
                f.write(f"*.userTerminal[{i}].terminal.arrayNumElements = {ut.array_elements}\n")
                f.write(f"*.userTerminal[{i}].terminal.dualConnectivityEnabled = {str(ut.dual_connectivity).lower()}\n")
                f.write(f"*.userTerminal[{i}].mobility.initialX = {ut.lon * 111000}m\n")
                f.write(f"*.userTerminal[{i}].mobility.initialY = {ut.lat * 111000}m\n")
                f.write(f"*.userTerminal[{i}].mobility.initialZ = 0m\n")
                f.write(f"*.ue[{i}].mobility.initialX = {ut.lon * 111000}m\n")
                f.write(f"*.ue[{i}].mobility.initialY = {ut.lat * 111000}m\n")
                f.write(f"*.ue[{i}].mobility.initialZ = 0m\n")
            
            f.write("\n# NR Manager\n")
            f.write(f"*.nrManager.channelModel = \"{self.terrestrial.get('channel_model', 'UMa')}\"\n")
            f.write(f"*.nrManager.carrierAggregationEnabled = {str(self.terrestrial.get('carrier_aggregation', {}).get('enabled', True)).lower()}\n")
            f.write(f"*.nrManager.beamformingEnabled = true\n")
            f.write(f"*.nrManager.networkSlicingEnabled = {str(self.terrestrial.get('core_network', {}).get('network_slicing', {}).get('enabled', True)).lower()}\n")
            f.write(f"*.nrManager.dualConnectivityEnabled = {str(self.terrestrial.get('ue', {}).get('dual_connectivity', {}).get('enabled', False)).lower()}\n")
            
            # Output configuration
            f.write(f"""
# Satellite Interface & MAC Defaults
*.satellite[*].**.mac.typename = "AckingMac"
*.satellite[*].**.mac.bitrate = 100Mbps
*.satellite[*].**.mac.headerLength = 32B
*.satellite[*].**.mac.fullDuplex = true
*.satellite[*].**.mac.useAck = false

*.groundStation[*].**.mac.typename = "AckingMac"
*.groundStation[*].**.mac.bitrate = 100Mbps
*.groundStation[*].**.mac.headerLength = 32B
*.groundStation[*].**.mac.fullDuplex = true
*.groundStation[*].**.mac.useAck = false

*.gnb[*].**.mac.typename = "AckingMac"
*.gnb[*].**.mac.bitrate = 100Mbps
*.gnb[*].**.mac.headerLength = 32B
*.gnb[*].**.mac.fullDuplex = true
*.gnb[*].**.mac.useAck = false

*.ue[*].**.mac.typename = "AckingMac"
*.ue[*].**.mac.bitrate = 100Mbps
*.ue[*].**.mac.headerLength = 32B
*.ue[*].**.mac.fullDuplex = true
*.ue[*].**.mac.useAck = false

*.userTerminal[*].**.mac.typename = "AckingMac"
*.userTerminal[*].**.mac.bitrate = 100Mbps
*.userTerminal[*].**.mac.headerLength = 32B
*.userTerminal[*].**.mac.fullDuplex = true
*.userTerminal[*].**.mac.useAck = false

*.satellite[*].**.radio.typename = "UnitDiskRadio"
*.satellite[*].**.radio.radioMediumModule = "radioMedium"
*.satellite[*].**.radio.transmitter.communicationRange = 9999999km
*.satellite[*].**.radio.transmitter.bitrate = 100Mbps
*.satellite[*].**.radio.transmitter.headerLength = 8bit
*.satellite[*].**.radio.transmitter.preambleDuration = 0s
*.satellite[*].**.radio.receiver.ignoreInterference = true

*.groundStation[*].**.radio.typename = "UnitDiskRadio"
*.groundStation[*].**.radio.radioMediumModule = "radioMedium"
*.groundStation[*].**.radio.transmitter.communicationRange = 9999999km
*.groundStation[*].**.radio.transmitter.bitrate = 100Mbps
*.groundStation[*].**.radio.transmitter.headerLength = 8bit
*.groundStation[*].**.radio.transmitter.preambleDuration = 0s
*.groundStation[*].**.radio.receiver.ignoreInterference = true

*.gnb[*].**.radio.typename = "UnitDiskRadio"
*.gnb[*].**.radio.radioMediumModule = "radioMedium"
*.gnb[*].**.radio.transmitter.communicationRange = 9999999km
*.gnb[*].**.radio.transmitter.bitrate = 100Mbps
*.gnb[*].**.radio.transmitter.headerLength = 8bit
*.gnb[*].**.radio.transmitter.preambleDuration = 0s
*.gnb[*].**.radio.receiver.ignoreInterference = true

*.ue[*].**.radio.typename = "UnitDiskRadio"
*.ue[*].**.radio.radioMediumModule = "radioMedium"
*.ue[*].**.radio.transmitter.communicationRange = 9999999km
*.ue[*].**.radio.transmitter.bitrate = 100Mbps
*.ue[*].**.radio.transmitter.headerLength = 8bit
*.ue[*].**.radio.transmitter.preambleDuration = 0s
*.ue[*].**.radio.receiver.ignoreInterference = true

*.userTerminal[*].**.radio.typename = "UnitDiskRadio"
*.userTerminal[*].**.radio.radioMediumModule = "radioMedium"
*.userTerminal[*].**.radio.transmitter.communicationRange = 9999999km
*.userTerminal[*].**.radio.transmitter.bitrate = 100Mbps
*.userTerminal[*].**.radio.transmitter.headerLength = 8bit
*.userTerminal[*].**.radio.transmitter.preambleDuration = 0s
*.userTerminal[*].**.radio.receiver.ignoreInterference = true

*.node[*].satNic.mac.typename = "AckingMac"
*.node[*].satNic.mac.bitrate = 100Mbps
*.node[*].satNic.mac.headerLength = 32B
*.node[*].satNic.mac.fullDuplex = true
*.node[*].satNic.mac.useAck = false
*.node[*].satNic.radio.typename = "UnitDiskRadio"
*.node[*].satNic.radio.radioMediumModule = "radioMedium"
*.node[*].satNic.radio.transmitter.communicationRange = 9999999km
*.node[*].satNic.radio.transmitter.bitrate = 100Mbps
*.node[*].satNic.radio.transmitter.headerLength = 8bit
*.node[*].satNic.radio.transmitter.preambleDuration = 0s
*.node[*].satNic.radio.receiver.ignoreInterference = true

*.node[*].wlan[*].radio.radioMediumModule = "wlanRadioMedium"
*.wlanRadioMedium.carrierFrequency = 5.9GHz

# Radio Medium & Dynamic 3GPP/ITU-R PathLoss Defaults
**.radioMedium.backgroundNoise.power = -110dBm
**.nrRadioMedium.backgroundNoise.power = -110dBm
**.radioMedium.pathLoss.typename = "NTNPathLoss"
**.nrRadioMedium.pathLoss.typename = "NTNPathLoss"
**.radioMedium.pathLoss.rainRateMmPerH = 25.0
**.radioMedium.pathLoss.elevationMaskDeg = 28.0
**.radioMedium.pathLoss.environmentType = "suburban"
**.radioMedium.mediumLimitCache.carrierFrequency = 28GHz
**.nrRadioMedium.mediumLimitCache.carrierFrequency = 3.5GHz
*.satellite[*].**.interfaceTableModule = ""
*.groundStation[*].**.interfaceTableModule = ""
*.gnb[*].**.interfaceTableModule = ""
*.ue[*].**.interfaceTableModule = ""
*.userTerminal[*].**.interfaceTableModule = ""
**.energyStorageModule = ""

# Antenna & Mobility Defaults
**.antenna.mobility.typename = ""
**.antenna.mobilityModule = "^.^.^.mobility"

# Output
**.scalar-recording = true
**.vector-recording = true
output-vector-file = "${{resultdir}}/${{configname}}-${{runnumber}}.vec"
output-scalar-file = "${{resultdir}}/${{configname}}-${{runnumber}}.sca"

# TraCI Co-Simulation with SUMO
*.traci.launcher.typename = "PosixLauncher"
*.traci.launcher.sumocfg = "stelvio.sumocfg"
*.traci.launcher.sumo = "sumo"
*.traci.core.version = 21
*.traci.mapper.vehicleType = "artery.inet.HybridCar"
*.traci.mapper.personType = "artery.inet.Person"
*.traci.nodes.personSinkModule = ".mobility"
*.traci.nodes.vehicleSinkModule = ".mobility"

# =========================================================================
# INET Canvas Visualizers (Matching squidslab/simu-scs-hybrid)
# =========================================================================
*.visualizer.dataLinkVisualizer.displayLinks = true
*.visualizer.dataLinkVisualizer.lineColor = "darkcyan"
*.visualizer.dataLinkVisualizer.packetFilter = "*"
*.visualizer.dataLinkVisualizer.fadeTime = 1s

*.visualizer.physicalLinkVisualizer.displayLinks = true
*.visualizer.physicalLinkVisualizer.lineColor = "green"
*.visualizer.physicalLinkVisualizer.fadeTime = 1s

*.visualizer.mediumVisualizer.displaySignals = true
*.visualizer.mediumVisualizer.signalColor = "gold"

*.visualizer.mobilityVisualizer.displayVelocities = true
*.visualizer.mobilityVisualizer.displayMovementTrails = true
*.visualizer.mobilityVisualizer.trailLength = 20

# =========================================================================
# Hybrid Interface Management (Vertical Handover Strategies)
# =========================================================================
**.hybridManager.switchingMode = "qos-based"
**.hybridManager.checkInterval = 0.5s
**.hybridManager.elevationMaskDeg = 25.0
""")
        
        print(f"Written: {ini_path}")
    
    def _write_tle_file(self, output_dir: str):
        """Write TLE file for constellation"""
        tle_path = os.path.join(output_dir, 'constellation.tle')
        
        with open(tle_path, 'w') as f:
            for sat in self.satellites:
                line1, line2 = sat.to_tle()
                f.write(f"{sat.name}\n")
                f.write(f"{line1}\n")
                f.write(f"{line2}\n")
        
        print(f"Written: {tle_path}")
    
    def _write_mobility_file(self, output_dir: str):
        """Write mobility traces for ground nodes"""
        mobility_path = os.path.join(output_dir, 'mobility.tcl')
        
        with open(mobility_path, 'w') as f:
            f.write("# Mobility traces for ground nodes\n")
            f.write("# Generated by scenario_generator.py\n\n")
            
            for gnb in self.gnbs:
                f.write(f"$gnb({gnb.name}) set X_ {gnb.lon * 111000}\n")
                f.write(f"$gnb({gnb.name}) set Y_ {gnb.lat * 111000}\n")
                f.write(f"$gnb({gnb.name}) set Z_ {gnb.height_m}\n")
            
            for ut in self.user_terminals:
                f.write(f"$ut({ut.terminal_id}) set X_ {ut.lon * 111000}\n")
                f.write(f"$ut({ut.terminal_id}) set Y_ {ut.lat * 111000}\n")
                f.write(f"$ut({ut.terminal_id}) set Z_ 1.5\n")
        
        print(f"Written: {mobility_path}")

def main():
    parser = argparse.ArgumentParser(description='Artery TN-NTN Scenario Generator')
    parser.add_argument('config', help='YAML configuration file')
    parser.add_argument('-o', '--output', default='output/scenario', help='Output directory')
    parser.add_argument('--validate', action='store_true', help='Only validate configuration')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)
    
    generator = ScenarioGenerator(args.config)
    generator.build()
    
    if args.validate:
        print("Configuration validation passed!")
        print(f"  Satellites: {len(generator.satellites)}")
        print(f"  Ground stations: {len(generator.ground_stations)}")
        print(f"  gNBs: {len(generator.gnbs)}")
        print(f"  User terminals: {len(generator.user_terminals)}")
    else:
        generator.generate(args.output)

if __name__ == '__main__':
    main()