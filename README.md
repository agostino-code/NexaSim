# NexaSim: 3D Unified Terrestrial & Non-Terrestrial Network Simulator

[![Horizon Europe - NexaSphere](https://img.shields.io/badge/Horizon%20Europe-NexaSphere-003399.svg)](https://cordis.europa.eu/)
[![Conan 2.x](https://img.shields.io/badge/Conan-2.x%20Ready-blue.svg)](https://conan.io/)
[![OMNeT++](https://img.shields.io/badge/OMNeT++-5.6.2-green.svg)](https://omnetpp.org/)
[![INET](https://img.shields.io/badge/INET-4.2.2-brightgreen.svg)](https://inet.omnetpp.org/)
[![Simu5G](https://img.shields.io/badge/Simu5G-1.1.0-orange.svg)](http://simu5g.org/)
[![space_veins](https://img.shields.io/badge/space__veins-0.3-purple.svg)](https://github.com/veins/space_veins)
[![Vanetza](https://img.shields.io/badge/Vanetza-26.02-red.svg)](https://github.com/riebl/vanetza)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

**NexaSim** is a state-of-the-art **3D Unified Communication Network Simulator** developed for the European Union's **Horizon Europe NexaSphere** research and innovation project.

Built upon the modular foundation of Artery, **NexaSim** evolves traditional vehicular and terrestrial simulation into a full-scale **three-dimensional, multi-tier network architecture** spanning:
- **Terrestrial Networks (TN)**: V2X (ETSI ITS-G5, GeoNetworking, C-V2X), 5G New Radio (3GPP Rel 15/16 gNodeB / UE via Simu5G), and SUMO microscopic traffic co-simulation.
- **Non-Terrestrial Networks (NTN)**: Low Earth Orbit (LEO) mega-constellations (Starlink, Kuiper, Walker-Delta), SGP4 orbital propagation (via space_veins), optical laser (1550 nm) & RF (Ka/V-band) Inter-Satellite Links (ISL), phased-array user terminals, and Ground Station feeder links.
- **Unified 3D Multi-RAT Orchestration**: Seamless Dual-Connectivity (DC), make-before-break satellite handovers, multi-link path routing, and dynamic failover between terrestrial cellular and space-based backhauls.

---

## Key Highlights

### 1. Modern Conan 2 Dependency Management (Zero Submodules)
NexaSim eliminates internal legacy submodules (`extern/`) in favor of **Conan 2 package management**:
* All dependencies (`INET 4.2.2`, `Simu5G 1.1.0`, `space_veins 0.3`, `Vanetza 26.02`, `Boost 1.86`, `GeographicLib`, `Crypto++`) are managed, pinned, and built through native Conan recipes (`recipes/`).
* Isolated, reproducible builds with persistent caching (`artery-conan2-cache`) reduce incremental build setup times from ~35 minutes to seconds.

### 2. Multi-Domain 3D Mobility & Node Management
* **Unified Mobility Manager** coordinates vehicles, road-side units (RSUs), drones (UAVs), high-altitude platforms (HAPS), LEO satellites, and ground stations across a single coordinate reference frame (`inet::Coord` & WGS84 Geodetic).
* Real-time position updates driven simultaneously by SUMO TraCI (terrestrial vehicles) and SGP4 orbital propagation (satellites).

### 3. Integrated Terrestrial 5G-NR & V2X
* **Simu5G 5G-NR Integration**: Standalone & Non-Standalone gNodeBs, User Plane protocol stacks, dynamic scheduling, Carrier Aggregation, and Beamforming.
* **Vanetza ITS-G5 Stack**: GeoNetworking (ETSI EN 302 636), BTP, Decentralized Congestion Control (DCC), and standard V2X services (CAM, DENM, CPM).

### 4. Non-Terrestrial Network (NTN) Engine
* **Orbital Mechanics**: Walker-Delta parametric constellations, multi-shell Starlink configurations, and custom Two-Line Element (TLE) ephemeris parsing.
* **Inter-Satellite Links (ISL)**: Realistic Pointing, Acquisition, and Tracking (PAT) modeling with optical beam divergence, pointing jitter, Doppler shift, and atmospheric/space link budgets.
* **Smart User Terminals**: Phased-array electronic steering with beamforming weight computation, multi-satellite tracking, and predictive make-before-break handovers.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                                     NexaSim                                       |
|                  3D Unified TN-NTN Multi-Tier Simulation Framework                |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +-----------------------------------+     +-----------------------------------+  |
|  |     Terrestrial Network (TN)      |     |   Non-Terrestrial Network (NTN)   |  |
|  |-----------------------------------|     |-----------------------------------|  |
|  | • ETSI ITS-G5 (Vanetza)           |     | • LEO Constellations (Walker/TLE) |  |
|  | • 5G New Radio (Simu5G)           |     | • Optical & RF ISL (ISLNic)       |  |
|  | • SUMO TraCI Traffic Co-Sim       |     | • Space Veins SGP4 Orbit Engine   |  |
|  | • C-V2X / DSRC & Radar Sensors    |     | • Phased Array User Terminals     |  |
|  +-----------------------------------+     +-----------------------------------+  |
|                    \                                 /                            |
|                     +-------------------------------+                             |
|                     | Unified Multi-RAT Coordinator |                             |
|                     | • 3D Unified Mobility Manager |                             |
|                     | • Dual Connectivity (TN+NTN)  |                             |
|                     | • Make-Before-Break Handovers |                             |
|                     +-------------------------------+                             |
|                                     |                                             |
|                     +-------------------------------+                             |
|                     |   OMNeT++ 5.6.2 / INET 4.2.2  |                             |
|                     +-------------------------------+                             |
|                                     |                                             |
|                     +-------------------------------+                             |
|                     |  Conan 2 Package Ecosystem    |                             |
|                     +-------------------------------+                             |
+-----------------------------------------------------------------------------------+
```

---

## Quick Start (Docker Environment)

NexaSim runs inside an optimized Docker environment providing all dependencies and build toolchains.

### 1. Build the Simulator

```bash
# Compile NexaSim (fast parallel Ninja build with Conan 2 caching)
docker compose run --rm nexasim-build
```

*(Legacy alias `docker compose run --rm artery-build` is also supported).*

### 2. Run a 3D Integrated Scenario

NexaSim comes with pre-packaged scenarios demonstrating TN-NTN multi-tier communications:

```bash
# Execute Starlink + Berlin 5G-NR Dual-Connectivity scenario
docker compose run --rm nexasim-scenario
```

### 3. Analyze Simulation Results

```bash
# Generate analytical plots (throughput, latency, handover CDFs, ISL link quality)
docker compose run --rm nexasim-analyze
```

---

## Scenario Library

Pre-configured YAML scenarios are provided in `scenarios/library/`:

| Scenario | Domain / Focus | Key NexaSphere Features |
| :--- | :--- | :--- |
| **`stelvio_pass_hybrid.yaml`** | Alpine Mountain Automotive | 3D mountain orography, 5G blackout gorge, Starlink LEO tracking, crash failover & V2V relay |
| **`nexasphere_highway_platooning.yaml`** | Autonomous Truck Platooning | 4-truck convoy on A22 highway, <5ms V2V sidelink string stability, hybrid LEO cloud gateway |
| **`nexasphere_emergency_corridor.yaml`** | Connected Ambulance Telemedicine | 120 km/h ambulance, 4K ultrasound video streaming, dynamic 5G/LEO Multi-RAT steering & preemption |
| **`nexasphere_urban_canyon_cpm.yaml`** | Urban Canyon & Perception | High-rise skyscraper masking (48° mask), microcell 5G beamforming, ETSI Collective Perception (CPM) |
| **`nexasphere_uav_corridor.yaml`** | Aerial UAV Infrastructure Corridor | Drones at 250m altitude transitioning between sparse 5G cells and LEO satellite backhaul |
| **`nexasphere_maritime_sar.yaml`** | Offshore Maritime Search & Rescue | Deep sea vessels & sensor buoys with pure NTN LEO coverage, distress beacon & laser ISLs |
| **`nexasphere_rail_highspeed.yaml`** | High-Speed Rail (300 km/h) | Fast train TN-NTN handover, Doppler shift compensation, Apennine tunnel outage recovery |

### Complete Documentation & Syntax Guide

For complete reference on YAML syntax, simulation workflows, data analysis, and 3D visualization, see the **[NexaSim Complete User Manual](docs/MANUAL.md)**.

```bash
# 1. Generate OMNeT++ scenario from YAML
python tools/gen_scenario.py scenarios/library/stelvio_pass_hybrid.yaml -o scenarios/generated/stelvio

# 2. Run simulation with OMNeT++ Graphical Interface (Qtenv)
docker compose run --rm -e DISPLAY=$DISPLAY nexasim-run opp_run -l build/libartery_core.so -f scenarios/generated/stelvio/omnetpp.ini -u Qtenv

# 3. Analyze Simulation KPIs & Results
python tools/analyze_results.py scenarios/generated/stelvio
```

---

## Project Structure

```
.
├── CMakeLists.txt                # Root CMake project (NexaSim)
├── conanfile.py                  # Conan 2 package definition
├── conandata.yml                 # Dependency version locks
├── docker-compose.yml            # Containerized build & execution orchestration
├── Dockerfile                    # Multi-stage Ubuntu build environment
├── recipes/                      # Conan 2 package recipes (inet, simu5g, space_veins, vanetza)
├── src/
│   ├── artery/
│   │   ├── ntn/                  # Non-Terrestrial Network engine (ISL, Constellations, User Terminal)
│   │   ├── nr/                   # 5G-NR Simu5G integration
│   │   ├── inet/                 # INET 4.2.2 radio & mobility adapters
│   │   ├── application/          # V2X ITS-G5 services & middleware
│   │   ├── envmod/               # Environmental perception & radar sensors
│   │   └── utility/              # Coordinate transforms, math, asio tasks
│   └── traci/                    # SUMO TraCI interface & node managers
├── scenarios/                    # OMNeT++ scenario configurations and NED topologies
└── tools/                        # Scenario generator, simulation runner, analysis scripts
```

---

## License & Acknowledgements

- **NexaSphere**: Developed under the European Union's Horizon Europe research framework for 3D unified communication networks.
- **Artery**: Based on the Artery V2X Simulation Framework (Raphael Riebl et al., GPLv2).
- **Core Components**: INET Framework, Simu5G, space_veins, and Vanetza.