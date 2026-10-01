# NexaSim: 3D Unified Terrestrial & Non-Terrestrial Network Simulator

[![Horizon Europe - NexaSphere](https://img.shields.io/badge/Horizon%20Europe-NexaSphere-003399.svg)](https://cordis.europa.eu/)
[![Conan 2.x](https://img.shields.io/badge/Conan-2.x%20Ready-blue.svg)](https://conan.io/)
[![OMNeT++](https://img.shields.io/badge/OMNeT++-5.7.1-green.svg)](https://omnetpp.org/)
[![SUMO](https://img.shields.io/badge/SUMO-1.21.0-blue.svg)](https://eclipse.dev/sumo/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async%20Core-009688.svg)](https://fastapi.tiangolo.com/)
[![INET](https://img.shields.io/badge/INET-4.2.2-brightgreen.svg)](https://inet.omnetpp.org/)
[![Simu5G](https://img.shields.io/badge/Simu5G-1.1.0-orange.svg)](http://simu5g.org/)
[![space_veins](https://img.shields.io/badge/space__veins-0.3-purple.svg)](https://github.com/veins/space_veins)
[![Vanetza](https://img.shields.io/badge/Vanetza-26.02-red.svg)](https://github.com/riebl/vanetza)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED.svg)](https://www.docker.com/)

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
|                     |   OMNeT++ 5.7.1 / INET 4.2.2  |                             |
|                     +-------------------------------+                             |
|                                     |                                             |
|                     +-------------------------------+                             |
|                     |  Conan 2 Package Ecosystem    |                             |
|                     +-------------------------------+                             |
+-----------------------------------------------------------------------------------+
```

---

## Quick Start (Docker Environment)

NexaSim runs inside an optimized **Multi-Stage Docker environment** providing isolated headless execution and interactive Web GUI modes.

### 1. Build the Simulator

```bash
# Compile NexaSim (fast parallel Ninja build with Conan 2 caching)
docker compose run --rm nexasim-build
```

### 2. Run a 3D Integrated Scenario

NexaSim comes with pre-packaged scenarios demonstrating TN-NTN multi-tier communications:

```bash
# Execute Starlink + Stelvio 5G-NR Dual-Connectivity scenario (Headless, ultra-fast)
docker compose run --rm nexasim-scenario

# Or execute with interactive 3D Web GUI (OMNeT++ Qtenv + SUMO GUI on http://localhost:6080/vnc.html)
docker compose run --rm -p 6080:6080 nexasim-gui
```

### 3. Analyze Simulation Results

```bash
# Generate analytical plots (throughput, latency, handover CDFs, ISL link quality)
docker compose run --rm nexasim-analyze
```

### Reproducible Build and Validation

The build service uses a single Release tree at `build/Release` and removes stale generated CMake files before configuring. Conan dependencies are rebuilt only when the requested package is missing from the cache.

The INET and space_veins recipes regenerate Message Compiler outputs with the OMNeT++ toolchain installed in the container. This keeps generated headers compatible with the OMNeT++ version used by the simulator.

For a clean build, use the project service rather than configuring a second build tree manually:

```bash
docker compose run --rm nexasim-build
```

The recommended pre-run checks are:

```bash
./nexasim validate
./nexasim generate stelvio
```

Studio binds to `127.0.0.1` by default. Use `--host` only when exposing it through a controlled network boundary.

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
# Unified CLI Workflow (Recommended):
./nexasim list                     # List all available scenarios in library
./nexasim validate stelvio         # Validate scenario specification (Pydantic / Schema)
./nexasim run stelvio              # Run scenario in headless mode
./nexasim run stelvio --gui        # Run with Qtenv & SUMO-GUI Virtual Desktop (http://localhost:6080/vnc.html)
./nexasim analyze stelvio          # Evaluate KPIs and generate interactive Chart.js dashboard
./nexasim sweep emergency_corridor --param switchingMode=coverage-based,qos-based # Parameter sweep benchmark
./nexasim view-3d stelvio          # Launch 3D Space-Ground Digital Twin (CesiumJS)
./nexasim studio                   # Start Web Control Center (http://localhost:8080)
./nexasim all highway_platooning   # End-to-end (generate -> run -> analyze)
```

---

## Project Structure

```
.
├── nexasim                       # Root CLI launcher
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
│   │   ├── hybrid/               # Multi-RAT Vertical Handover & MEC Offloading
│   │   ├── application/          # V2X ITS-G5 services & middleware
│   │   ├── envmod/               # Environmental perception & radar sensors
│   │   └── utility/              # Coordinate transforms, math, asio tasks
│   └── traci/                    # SUMO TraCI interface & node managers
├── scenarios/
│   ├── library/                  # Declarative YAML scenario specifications
│   ├── schema/                   # Pydantic JSON Schema for YAML autocompletion
│   └── generated/                # Auto-generated OMNeT++ & SUMO runtime files
└── tools/
    ├── nexasim.py                # Core CLI implementation
    ├── studio.py                 # Interactive Web Studio & Control Center
    ├── sweep.py                  # Sensitivity study & parameter sweep runner
    ├── czml_generator.py         # 3D Cesium globe & CZML digital twin generator
    ├── sumo_generator.py         # Procedural SUMO network generator
    ├── gen_scenario.py           # YAML to OMNeT++ scenario compiler
    ├── analyze_results.py        # KPI evaluation engine
    └── dashboard.py              # Executive Chart.js interactive dashboard
```

---

## Research & Innovation Roadmap

In alignment with the Horizon Europe NexaSphere technical objectives:

* **Milestone 1**: Modern Conan 2 Zero-Submodule Architecture & Multi-Domain Mobility *(Completed)*.
* **Milestone 2**: Unified CLI & Procedural SUMO Traffic Generation *(Completed)*.
* **Milestone 3**: Dynamic Multi-Tier VHO & Hierarchical MEC Edge Computing *(Completed)*.
* **Milestone 4**: Multi-Run Benchmark Suite, 3D Digital Twin (CesiumJS) & Web Studio *(Completed)*.

### NexaSim Studio — Web Control Center (Powered by FastAPI)

The Studio is an aerospace-grade web control center that orchestrates the entire simulation pipeline from a browser, powered by an asynchronous **FastAPI** backend and **Uvicorn** ASGI server. Start it with:

```bash
./nexasim studio --port 8080
```

Then open `http://localhost:8080`. Interactive OpenAPI/Swagger documentation is available at `http://localhost:8080/docs`. The Cesium Ion token and CARTO API key are read from `.env` (isolated and `.gitignore`-ated — never committed).

* **Async Worker Architecture**: Long-running simulations are dispatched via FastAPI `BackgroundTasks`, streaming logs in real time without blocking HTTP requests.
* **Built-in Security**: Static assets and simulation artifacts are served via mounted Starlette `StaticFiles` with automatic Path Traversal protection. Input specifications are validated via Pydantic models.
* **Layout** (CSS Grid): header with view-mode buttons, 340 px left sidebar (scenario catalog + actions + drawer toggle), main area (2D Leaflet map and/or 3D CesiumJS globe), and a collapsible lower drawer (45% height) hosting the executive dashboard.

**View modes:**
- **Single 2D** — Leaflet tactical map with CARTO Dark / ESRI Dark Gray / ESRI Satellite basemaps. Animated vehicle convoy markers with dynamic RAT handover (green = 5G-NR terrestrial, cyan = LEO NTN satellite when in a blind spot), gNodeB, ground station, and visible-satellite overlays.
- **Single 3D** — CesiumJS globe with camera presets (Tactical, Chase Cam, Orbit LEO) calibrated on the scenario's real coordinates, basemap selection, and terrain-clamped vehicle markers (`heightReference: "CLAMP_TO_GROUND"`).
- **Dual** — 2D and 3D side by side; the lower drawer closes automatically and the globe's HUD panel is hidden (via `?hud=0` query param + `postMessage`).

**Lower drawer — Executive Dashboard** (Chart.js, 2x2 grid): Active Interface (area), QoS Utility Score (line), MEC Latency (bar), Cumulative Handovers (line), plus a Fleet Multi-RAT Telemetry Summary table and a Physical Link Budget section.

**Sidebar controls:** scenario parameter sliders (rain rate, duration, VHO strategy), streaming execution console (`ev/sec`, simulated time, live logs), and one-click buttons to Generate, Run, Analyze, open the Dashboard, or launch the 3D globe.

### 3D Digital Twin (`nexasim view-3d`)

A separate command launches the photorealistic 3D geospatial twin built on **CesiumJS 1.119** with dynamically generated **CZML** packets (`tools/czml_generator.py`):

```bash
./nexasim view-3d stelvio
```

The globe renders: LEO constellation satellites with Keplerian/SGP4 orbital dynamics, optical ISL laser beams between adjacent satellites, volumetric 5G-NR coverage cones around gNodeB towers, dynamic magenta phased-array tracking beams from vehicle to satellite, and **terrain-clamped vehicle markers** (all vehicles sit exactly on the digital terrain, never floating above or sinking below it).

**Camera presets** (all calibrated on the scenario's real coordinates, no hardcoded values): **Tactical** (regional overview at 5.5 km, -32° pitch), **Chase Cam** (tracks convoy leader `veh_0`), **Orbit LEO** (constellation-wide view at 2,200 km). **Basemap picker** offers Cesium World Terrain, ESRI World Imagery (via `UrlTemplateImageryProvider`, avoiding the deprecated `ArcGisMapServerImageryProvider` errors), and Cesium Black Marble. A try/catch fallback to `EllipsoidTerrainProvider` prevents crashes when no Cesium Ion token is available.

**HUD toggling:** in Dual view the globe's HUD panel is hidden via `?hud=0` query param and `postMessage({ showHud: false })`, so the HUD never overlaps the 2D map.
* **Milestone 5 (Upcoming)**: Multi-Hop Inter-Satellite Mesh Routing using Contact Graph Routing (CGR) and dynamic space Dijkstra.
* **Milestone 6 (Upcoming)**: Reinforcement Learning (Deep Q-Network / PPO) for predictive make-before-break vertical handover.
* **Milestone 7 (Upcoming)**: 3GPP Rel. 16/17 5G-NR V2X Sidelink (PC5) integration with Collective Perception Service (CPM).

---

## License & Acknowledgements

- **NexaSphere**: Developed under the European Union's Horizon Europe research framework for 3D unified communication networks.
- **Artery**: Based on the Artery V2X Simulation Framework (Raphael Riebl et al., GPLv2).
- **Core Components**: INET Framework, Simu5G, space_veins, and Vanetza.
