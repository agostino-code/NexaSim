#include "artery/ntn/ConstellationManager.h"
#include "artery/ntn/NTNChannelModel.h"
#include <omnetpp.h>
#include <cmath>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <queue>
#include <limits>

namespace artery {
namespace ntn {

namespace {
constexpr double WGS84_A = 6378137.0;                 // Semi-major axis (m)
constexpr double WGS84_F = 1.0 / 298.257223563;       // Flattening
constexpr double WGS84_B = WGS84_A * (1.0 - WGS84_F); // Semi-minor axis (m)
constexpr double WGS84_E2 = 2.0 * WGS84_F - WGS84_F * WGS84_F; // First eccentricity squared
constexpr double WGS84_E_PRIME2 = (WGS84_A * WGS84_A - WGS84_B * WGS84_B) / (WGS84_B * WGS84_B);
constexpr double EARTH_ROTATION_OMEGA = 7.2921159e-5; // rad/s (Earth sidereal rotation)
constexpr double GM_EARTH = 3.986004418e14;          // Standard gravitational parameter (m^3/s^2)
constexpr double J2_EARTH = 1.08263e-3;               // J2 zonal perturbation coefficient
constexpr double C_LIGHT_VACUUM = 299792458.0;        // Speed of light in vacuum (m/s)
}

Define_Module(ConstellationManager);

void ConstellationManager::initialize(int stage) {
    if (stage == 0) {
        // Read configuration
        constellationConfigFile = par("constellationConfigFile").stringValue();
        constellationType = par("constellationType").stringValue();
        
        // Walker Delta params
        walkerT = par("walkerT");
        walkerP = par("walkerP");
        walkerF = par("walkerF");
        walkerAltitudeKm = par("walkerAltitudeKm");
        walkerInclinationDeg = par("walkerInclinationDeg");
        
        // Geodetic origin
        if (hasPar("originLatitude")) originLatitude = par("originLatitude").doubleValue();
        if (hasPar("originLongitude")) originLongitude = par("originLongitude").doubleValue();
        if (hasPar("originAltitude")) originAltitude = par("originAltitude").doubleValue();
        
        // ISL params
        islEnabled = par("islEnabled");
        islType = par("islType").stringValue();
        islMaxRangeKm = par("islMaxRangeKm");
        islPortsPerSat = par("islPortsPerSat");
        islWavelengthNm = par("islWavelengthNm");
        islTxPowerDbm = par("islTxPowerDbm");
        islRxSensitivityDbm = par("islRxSensitivityDbm");
        islPointingAccuracyDeg = par("pointingAccuracyDeg");
        islAcquisitionTimeMs = par("acquisitionTimeMs");
        if (hasPar("islRoutingMode")) islRoutingMode = par("islRoutingMode").stringValue();
        if (hasPar("islSwitchingDelayMs")) islSwitchingDelayMs = par("islSwitchingDelayMs").doubleValue();
        if (hasPar("environmentProfile")) environmentProfile = par("environmentProfile").stringValue();
        if (hasPar("azimuthHorizonMask")) {
            std::string maskStr = par("azimuthHorizonMask").stringValue();
            if (!maskStr.empty()) {
                std::stringstream ss(maskStr);
                double val = 0.0;
                while (ss >> val) {
                    azimuthHorizonMask.push_back(val);
                    if (ss.peek() == ',' || ss.peek() == ';') ss.ignore();
                }
            }
        }
        
        // Satellite defaults
        satNicType = par("satNicType").stringValue();
        satIslNicType = par("satIslNicType").stringValue();
        satMobilityType = par("satMobilityType").stringValue();
        satManagerType = par("satManagerType").stringValue();
        satTxPowerDbm = par("satTxPowerDbm");
        satNoiseFigureDb = par("satNoiseFigureDb");
        satFrequencyGhz = par("satFrequencyGhz");
        satBandwidthMhz = par("satBandwidthMhz");
        
        // Visibility update interval
        visibilityUpdateInterval = par("visibilityUpdateInterval");
        
        // Register signals
        satDeployedSignal = registerSignal("satelliteDeployed");
        islEstablishedSignal = registerSignal("islEstablished");
        islBrokenSignal = registerSignal("islBroken");
        handoverSignal = registerSignal("handover");
        visibilitySignal = registerSignal("visibilityUpdate");
        m_sigIslHopCount = registerSignal("islHopCount");
        m_sigIslRouteLatency = registerSignal("islRouteLatency");
        m_sigIslMeshOutage = registerSignal("islMeshOutage");
        
        // Load configuration
        loadConfiguration();
        
        // Deploy constellation
        deployConstellation();
        m_ephemerisCache.assign(satellites.size(), EphemerisCacheEntry{});
        
        // Create ground stations
        createGroundStationModules();
        
        // Schedule visibility updates
        scheduleVisibilityUpdates();
        
        EV_INFO << "ConstellationManager initialized with " << satellites.size() << " satellites and " << gstations.size() << " ground stations\n";
    }
}

void ConstellationManager::handleMessage(omnetpp::cMessage* msg) {
    if (msg == visibilityUpdateTimer) {
        updateVisibility();
        scheduleVisibilityUpdates();
    } else {
        // Handle other messages (handover requests, etc.)
        EV_WARN << "ConstellationManager received unexpected message: " << msg->getName() << "\n";
        delete msg;
    }
}

void ConstellationManager::finish() {
    EV_INFO << "ConstellationManager finishing. Total handovers: " << totalHandovers 
            << ", ISL handoffs: " << totalISLHandoffs << "\n";
    
    // Record final statistics
    recordScalar("totalSatellites", satellites.size());
    recordScalar("totalGroundStations", gstations.size());
    recordScalar("totalISLLinks", islLinks.size());
    recordScalar("totalHandovers", totalHandovers);
    recordScalar("totalISLHandoffs", totalISLHandoffs);
    
    if (visibilityUpdateTimer) {
        cancelAndDelete(visibilityUpdateTimer);
        visibilityUpdateTimer = nullptr;
    }
}

void ConstellationManager::loadConfiguration() {
    if (!constellationConfigFile.empty()) {
        std::ifstream file(constellationConfigFile);
        if (file.is_open()) {
            std::stringstream buffer;
            buffer << file.rdbuf();
            configureFromYAML(buffer.str());
            file.close();
        } else {
            EV_WARN << "Could not open constellation config file: " << constellationConfigFile << "\n";
        }
    } else {
        // Use parameters directly
        if (constellationType == "walker_delta") {
            parseWalkerDelta("");
        } else if (constellationType == "starlink_shell") {
            parseStarlinkShells("");
        }
    }
}

void ConstellationManager::parseWalkerDelta(const std::string& config) {
    // Walker Delta: T/P/F notation
    // T = total satellites, P = planes, F = phasing
    // Already read from parameters
    EV_INFO << "Using Walker Delta: " << walkerT << "/" << walkerP << "/" << walkerF 
            << " at " << walkerAltitudeKm << "km, " << walkerInclinationDeg << "deg\n";
}

void ConstellationManager::parseStarlinkShells(const std::string& config) {
    // Default Starlink-like shells if not configured via YAML
    if (shells.empty()) {
        ShellConfig shell1;
        shell1.name = "shell_1";
        shell1.altitudeKm = 550;
        shell1.inclinationDeg = 53.0;
        shell1.numPlanes = 12;  // Reduced for simulation
        shell1.satsPerPlane = 6;
        shell1.phaseOffset = 0;
        shells.push_back(shell1);
        
        EV_INFO << "Using default Starlink shell: " << shell1.numPlanes << " planes x " 
                << shell1.satsPerPlane << " sats at " << shell1.altitudeKm << "km\n";
    }
}

void ConstellationManager::parseCustomTLE(const std::string& config) {
    EV_INFO << "Custom TLE deployment not yet implemented\n";
}

void ConstellationManager::deployConstellation() {
    if (constellationType == "walker_delta") {
        deployWalkerDelta();
    } else if (constellationType == "starlink_shell") {
        deployStarlinkShells();
    } else {
        deployCustomTLE();
    }
    
    EV_INFO << "Deployed " << satellites.size() << " satellites\n";
}

void ConstellationManager::deployWalkerDelta() {
    int globalId = 0;
    for (int p = 0; p < walkerP; ++p) {
        for (int s = 0; s < walkerT / walkerP; ++s) {
            SatelliteInfo sat;
            sat.planeId = p;
            sat.satIdInPlane = s;
            sat.globalId = globalId++;
            sat.name = "sat_" + std::to_string(p) + "_" + std::to_string(s);
            
            sat.elements = computeWalkerElements(p, s, walkerP, walkerT, walkerF,
                                                walkerAltitudeKm, walkerInclinationDeg);
            
            satellites.push_back(sat);
            satNameToIndex[sat.name] = satellites.size() - 1;
        }
    }
    
    // Create modules for each satellite
    for (auto& sat : satellites) {
        createSatelliteModule(sat);
    }
}

void ConstellationManager::deployStarlinkShells() {
    int globalId = 0;
    for (const auto& shell : shells) {
        for (int p = 0; p < shell.numPlanes; ++p) {
            for (int s = 0; s < shell.satsPerPlane; ++s) {
                SatelliteInfo sat;
                sat.planeId = p;
                sat.satIdInPlane = s;
                sat.globalId = globalId++;
                sat.name = shell.name + "_sat_" + std::to_string(p) + "_" + std::to_string(s);
                
                sat.elements = computeStarlinkElements(shell, p, s);
                
                satellites.push_back(sat);
                satNameToIndex[sat.name] = satellites.size() - 1;
            }
        }
    }
    
    // Create modules for each satellite
    for (auto& sat : satellites) {
        createSatelliteModule(sat);
    }
}

void ConstellationManager::deployCustomTLE() {
    // Not implemented yet
}

ConstellationManager::OrbitalElements ConstellationManager::computeWalkerElements(
    int planeIdx, int satIdx, int P, int T, int F, double altitudeKm, double inclinationDeg) {
    
    OrbitalElements el;
    const double earthRadiusKm = WGS84_A / 1000.0;
    const double mu = GM_EARTH / 1e9;  // km^3/s^2
    
    el.semiMajorAxisKm = earthRadiusKm + altitudeKm;
    el.eccentricity = 0.0001;  // Circular / near-circular LEO
    el.inclinationDeg = inclinationDeg;
    
    // RAAN for this plane
    el.raanDeg = std::fmod(planeIdx * (360.0 / std::max(1, P)), 360.0);
    if (el.raanDeg < 0.0) el.raanDeg += 360.0;
    
    // Argument of perigee
    el.argPerigeeDeg = 0.0;
    
    // Mean anomaly with phasing
    double satellitesPerPlane = static_cast<double>(T) / std::max(1, P);
    double meanAnomalyBase = satIdx * (360.0 / std::max(1.0, satellitesPerPlane));
    double phasing = F * planeIdx * (360.0 / std::max(1, T));
    el.meanAnomalyDeg = std::fmod(meanAnomalyBase + phasing, 360.0);
    if (el.meanAnomalyDeg < 0.0) el.meanAnomalyDeg += 360.0;
    
    // Mean motion (rad/s -> rev/day)
    double n = std::sqrt(mu / std::pow(el.semiMajorAxisKm, 3));
    el.meanMotionRevPerDay = n * 86400.0 / (2.0 * M_PI);
    
    // Epoch (current simulation time)
    el.epoch = 0;  // Will be set by SGP4Mobility
    el.bstar = 0.0;
    
    return el;
}

ConstellationManager::OrbitalElements ConstellationManager::computeStarlinkElements(
    const ShellConfig& shell, int planeIdx, int satIdx) {
    
    return computeWalkerElements(planeIdx, satIdx, 
                                 shell.numPlanes, 
                                 shell.numPlanes * shell.satsPerPlane,
                                 shell.phaseOffset,
                                 shell.altitudeKm,
                                 shell.inclinationDeg);
}

void ConstellationManager::elementsToTLE(const OrbitalElements& el, std::string& line1, std::string& line2) {
    // Simplified TLE generation (not fully compliant, but works for SGP4)
    // Line 1
    char buf1[80], buf2[80];
    snprintf(buf1, sizeof(buf1), 
        "1 %05dU 99999A   %05d.00000000  .00000000  00000-0  %+06.4f-4 0  9990",
        el.globalId % 99999,  // Satellite number
        24001,  // Epoch year/day (simplified)
        el.bstar * 1e4);
    
    // Line 2
    snprintf(buf2, sizeof(buf2),
        "2 %05d %08.4f %08.4f %07d %08.4f %08.4f %11.8f",
        el.globalId % 99999,
        el.inclinationDeg,
        el.raanDeg,
        static_cast<int>(el.eccentricity * 1e7),
        el.argPerigeeDeg,
        el.meanAnomalyDeg,
        el.meanMotionRevPerDay);
    
    line1 = buf1;
    line2 = buf2;
}

void ConstellationManager::createSatelliteModule(const SatelliteInfo& sat) {
    // Create satellite module dynamically
    // In OMNeT++, we typically define the network in NED, but we can also
    // create submodules programmatically
    
    // For now, we'll emit a signal and let the NED network handle instantiation
    // The actual satellite modules are created via the NED network definition
    // This manager just tracks them
    
    // Find the module by name and vector index from NED
    omnetpp::cModule* parent = getParentModule();
    omnetpp::cModule* mod = parent ? parent->getSubmodule("satellite", sat.globalId) : nullptr;
    
    if (mod) {
        const_cast<SatelliteInfo&>(sat).module = mod;
        emitSatelliteDeployed(sat);
        EV_DEBUG << "Found satellite module: satellite[" << sat.globalId << "]\n";
    } else {
        EV_WARN << "Satellite module not found: satellite[" << sat.globalId << "]\n";
    }
}

void ConstellationManager::createGroundStationModules() {
    omnetpp::cModule* parent = getParentModule();
    
    for (size_t i = 0; i < groundStations.size(); ++i) {
        GroundStationInfo gs;
        gs.name = groundStations[i].name;
        gs.lat = groundStations[i].lat;
        gs.lon = groundStations[i].lon;
        gs.alt = groundStations[i].alt;
        gs.elevationMaskDeg = groundStations[i].elevationMaskDeg;
        
        omnetpp::cModule* mod = parent ? parent->getSubmodule("groundStation", i) : nullptr;
        
        if (mod) {
            gs.module = mod;
            if (mod->hasPar("latitude")) mod->par("latitude") = gs.lat;
            if (mod->hasPar("longitude")) mod->par("longitude") = gs.lon;
            if (mod->hasPar("altitude")) mod->par("altitude") = gs.alt;
            EV_DEBUG << "Found ground station module: groundStation[" << i << "]\n";
        } else {
            EV_WARN << "Ground station module not found: groundStation[" << i << "]\n";
        }
        
        gsNameToIndex[gs.name] = gstations.size();
        gstations.push_back(gs);
    }
}

void ConstellationManager::scheduleVisibilityUpdates() {
    if (!visibilityUpdateTimer) {
        visibilityUpdateTimer = new omnetpp::cMessage("visibilityUpdate");
    }
    scheduleAt(omnetpp::simTime() + visibilityUpdateInterval, visibilityUpdateTimer);
}

void ConstellationManager::updateVisibility() {
    updateSatellitePositions();
    computeISLTopology();
    computeGroundStationVisibility();
    computeISLMeshShortestPaths();
    // computeUEVisibility(); // Would need UE references

    emit(visibilitySignal, omnetpp::simTime().dbl());
}

void ConstellationManager::updateSatellitePositions() {
    // Satellite positions are updated by their mobility modules (SGP4Mobility)
    // We just query them here
    for (auto& sat : satellites) {
        if (sat.module) {
            auto mobility = sat.module->getSubmodule("mobility");
            if (mobility) {
                // Get position from mobility module
                // This depends on the mobility module's interface
                // For SGP4Mobility, it typically provides getCurrentPosition()
            }
        }
    }
}

void ConstellationManager::computeISLTopology() {
    if (!islEnabled) return;

    if (islRoutingMode == "grid_plus") {
        computeGridPlusISLTopology();
        return;
    }
    
    // Clear old links
    std::vector<ISLLink> newLinks;
    
    // For each satellite, find neighbors within range
    for (size_t i = 0; i < satellites.size(); ++i) {
        SatelliteInfo& satA = satellites[i];
        satA.visibleSats.clear();
        
        if (!satA.module) continue;
        
        // Get position (simplified - would query mobility module)
        inet::Coord posA = getSatellitePosition(satA);
        
        // Check all other satellites
        for (size_t j = i + 1; j < satellites.size(); ++j) {
            SatelliteInfo& satB = satellites[j];
            if (!satB.module) continue;
            
            inet::Coord posB = getSatellitePosition(satB);
            double range = calculateRange(posA, posB);
            
            if (range <= islMaxRangeKm) {
                // Check if they have available ISL ports
                if (satA.visibleSats.size() < islPortsPerSat && 
                    satB.visibleSats.size() < islPortsPerSat) {
                    
                    // Check LOS (no Earth obstruction)
                    if (checkLOS(posA, posB, 0.0)) {
                        ISLLink link;
                        link.satA = i;
                        link.satB = j;
                        link.distanceKm = range;
                        link.active = true;
                        link.establishedAt = omnetpp::simTime();
                        link.linkQuality = calculateLinkBudget(link);
                        
                        newLinks.push_back(link);
                        satA.visibleSats.push_back(j);
                        satB.visibleSats.push_back(i);
                        
                        // Emit signal for new link
                        emitISLEstablished(i, j);
                    }
                }
            }
        }
    }
    
    // Check for broken links
    for (auto& oldLink : islLinks) {
        bool stillExists = false;
        for (auto& newLink : newLinks) {
            if ((newLink.satA == oldLink.satA && newLink.satB == oldLink.satB) ||
                (newLink.satA == oldLink.satB && newLink.satB == oldLink.satA)) {
                stillExists = true;
                break;
            }
        }
        if (!stillExists && oldLink.active) {
            emitISLBroken(oldLink.satA, oldLink.satB);
            totalISLHandoffs++;
        }
    }
    
    islLinks = std::move(newLinks);
}

void ConstellationManager::computeGridPlusISLTopology() {
    std::vector<ISLLink> newLinks;

    // Index satellites by (planeId, satIdInPlane)
    std::map<std::pair<int, int>, int> planeSatToIdx;
    std::map<int, int> planeCounts;
    int maxPlane = 0;

    for (size_t i = 0; i < satellites.size(); ++i) {
        satellites[i].visibleSats.clear();
        int p = satellites[i].planeId;
        int s = satellites[i].satIdInPlane;
        planeSatToIdx[{p, s}] = i;
        planeCounts[p]++;
        maxPlane = std::max(maxPlane, p);
    }
    int totalPlanes = maxPlane + 1;

    for (size_t i = 0; i < satellites.size(); ++i) {
        SatelliteInfo& satA = satellites[i];
        if (!satA.module) continue;
        int p = satA.planeId;
        int s = satA.satIdInPlane;
        int S = planeCounts[p];
        if (S <= 0 || totalPlanes <= 0) continue;

        inet::Coord posA = getSatellitePosition(satA);

        // Grid+ 4 neighbors:
        // 1. Intra-plane forward
        // 2. Intra-plane backward
        // 3. Inter-plane right
        // 4. Inter-plane left
        std::vector<std::pair<int, int>> candidateCoords = {
            {p, (s + 1) % S},
            {p, (s - 1 + S) % S},
            {(p + 1) % totalPlanes, s},
            {(p - 1 + totalPlanes) % totalPlanes, s}
        };

        for (const auto& coord : candidateCoords) {
            auto it = planeSatToIdx.find(coord);
            if (it == planeSatToIdx.end()) continue;
            int j = it->second;
            if (i >= static_cast<size_t>(j)) continue; // Process each undirected edge once

            SatelliteInfo& satB = satellites[j];
            if (!satB.module) continue;
            inet::Coord posB = getSatellitePosition(satB);
            double range = calculateRange(posA, posB);

            if (range <= islMaxRangeKm && checkLOS(posA, posB, 0.0)) {
                ISLLink link;
                link.satA = i;
                link.satB = j;
                link.distanceKm = range;
                link.active = true;
                link.establishedAt = omnetpp::simTime();
                link.linkQuality = calculateLinkBudget(link);

                newLinks.push_back(link);
                satA.visibleSats.push_back(j);
                satB.visibleSats.push_back(i);

                emitISLEstablished(i, j);
            }
        }
    }

    // Check for broken links
    for (auto& oldLink : islLinks) {
        bool stillExists = false;
        for (auto& newLink : newLinks) {
            if ((newLink.satA == oldLink.satA && newLink.satB == oldLink.satB) ||
                (newLink.satA == oldLink.satB && newLink.satB == oldLink.satA)) {
                stillExists = true;
                break;
            }
        }
        if (!stillExists && oldLink.active) {
            emitISLBroken(oldLink.satA, oldLink.satB);
            totalISLHandoffs++;
        }
    }

    islLinks = std::move(newLinks);
}

void ConstellationManager::computeGroundStationVisibility() {
    for (size_t g = 0; g < gstations.size(); ++g) {
        auto& gs = gstations[g];
        gs.visibleSats.clear();
        if (!gs.module) continue;
        
        inet::Coord gsPos = getGroundStationPosition(gs);
        
        for (size_t i = 0; i < satellites.size(); ++i) {
            SatelliteInfo& sat = satellites[i];
            if (!sat.module) continue;
            
            inet::Coord satPos = getSatellitePosition(sat);
            double elevation = calculateElevation(satPos, gsPos);
            
            if (elevation >= gs.elevationMaskDeg) {
                gs.visibleSats.push_back(i);
                sat.visibleGroundStations.push_back(g);
            }
        }
    }
}

double ConstellationManager::calculateEndToEndNTNLatency(int servingSatId, double ueSlantRangeKm, int gatewayIndex) {
    constexpr double cKmPerS = 299792.458;
    double tUeToSat = ueSlantRangeKm / cKmPerS; // seconds

    if (servingSatId < 0 || servingSatId >= static_cast<int>(satellites.size())) {
        return tUeToSat;
    }

    // Check if serving satellite directly sees the target gateway
    if (gatewayIndex >= 0 && gatewayIndex < static_cast<int>(gstations.size())) {
        const auto& gs = gstations[gatewayIndex];
        inet::Coord satPos = getSatellitePosition(satellites[servingSatId]);
        inet::Coord gsPos = getGroundStationPosition(gs);
        double elev = calculateElevation(satPos, gsPos);
        if (elev >= gs.elevationMaskDeg) {
            // Direct bent-pipe feeder link: N_isl = 0
            double satGwDist = calculateRange(satPos, gsPos);
            double tSatToGw = satGwDist / cKmPerS;
            return tUeToSat + tSatToGw;
        }
    }

    // Multi-hop ISL route
    ISLRouteResult route;
    if (gatewayIndex >= 0 && gatewayIndex < static_cast<int>(gstations.size())) {
        route = getShortestRouteToGateway(servingSatId, gatewayIndex);
    } else {
        route = getShortestRouteToAnyGateway(servingSatId);
    }

    if (route.routeFound && !route.pathSats.empty()) {
        double islLatencyS = route.totalLatencyMs / 1000.0;
        int lastSatId = route.targetSatId;
        double tSatToGw = 0.0025; // Default ~750km feeder link
        if (route.gatewayIndex >= 0 && route.gatewayIndex < static_cast<int>(gstations.size())) {
            inet::Coord lastSatPos = getSatellitePosition(satellites[lastSatId]);
            inet::Coord gsPos = getGroundStationPosition(gstations[route.gatewayIndex]);
            tSatToGw = calculateRange(lastSatPos, gsPos) / cKmPerS;
        }
        return tUeToSat + islLatencyS + tSatToGw;
    }

    // Fallback if mesh has temporary outage
    return tUeToSat + 0.003;
}

inet::Coord ConstellationManager::geodeticToEcef(double latDeg, double lonDeg, double altM) {
    double phi = latDeg * M_PI / 180.0;
    double lambda = lonDeg * M_PI / 180.0;
    double sinPhi = std::sin(phi);
    double cosPhi = std::cos(phi);
    double sinLambda = std::sin(lambda);
    double cosLambda = std::cos(lambda);

    double N = WGS84_A / std::sqrt(1.0 - WGS84_E2 * sinPhi * sinPhi);
    double x = (N + altM) * cosPhi * cosLambda;
    double y = (N + altM) * cosPhi * sinLambda;
    double z = (N * (1.0 - WGS84_E2) + altM) * sinPhi;
    return inet::Coord(x, y, z);
}

void ConstellationManager::ecefToGeodetic(const inet::Coord& ecef, double& latDeg, double& lonDeg, double& altM) {
    double p = std::sqrt(ecef.x * ecef.x + ecef.y * ecef.y);
    lonDeg = std::atan2(ecef.y, ecef.x) * 180.0 / M_PI;

    if (p < 1e-6) {
        latDeg = (ecef.z >= 0.0) ? 90.0 : -90.0;
        altM = std::abs(ecef.z) - WGS84_B;
        return;
    }

    // Bowring's geodetic algorithm
    double theta = std::atan2(ecef.z * WGS84_A, p * WGS84_B);
    double sinTheta = std::sin(theta);
    double cosTheta = std::cos(theta);

    double phi = std::atan2(
        ecef.z + WGS84_E_PRIME2 * WGS84_B * sinTheta * sinTheta * sinTheta,
        p - WGS84_E2 * WGS84_A * cosTheta * cosTheta * cosTheta
    );
    latDeg = phi * 180.0 / M_PI;
    double sinPhi = std::sin(phi);
    double N = WGS84_A / std::sqrt(1.0 - WGS84_E2 * sinPhi * sinPhi);
    altM = p / std::cos(phi) - N;
}

inet::Coord ConstellationManager::localToEcef(const inet::Coord& localPos) const {
    if (localPos.length() > 6000000.0) {
        return localPos; // Already in ECEF
    }
    inet::Coord originEcef = geodeticToEcef(originLatitude, originLongitude, originAltitude);
    double phi0 = originLatitude * M_PI / 180.0;
    double lam0 = originLongitude * M_PI / 180.0;
    double sinPhi = std::sin(phi0);
    double cosPhi = std::cos(phi0);
    double sinLam = std::sin(lam0);
    double cosLam = std::cos(lam0);

    double e = localPos.x;
    double n = localPos.y;
    double u = localPos.z;

    double dx = -sinLam * e - sinPhi * cosLam * n + cosPhi * cosLam * u;
    double dy =  cosLam * e - sinPhi * sinLam * n + cosPhi * sinLam * u;
    double dz =               cosPhi * n          + sinPhi * u;

    return originEcef + inet::Coord(dx, dy, dz);
}

inet::Coord ConstellationManager::ecefToLocal(const inet::Coord& ecefPos) const {
    inet::Coord originEcef = geodeticToEcef(originLatitude, originLongitude, originAltitude);
    inet::Coord diff = ecefPos - originEcef;
    return ecefToEnu(diff, originLatitude, originLongitude);
}

inet::Coord ConstellationManager::ecefToEnu(const inet::Coord& rhoEcef, double refLatDeg, double refLonDeg) {
    double phi = refLatDeg * M_PI / 180.0;
    double lam = refLonDeg * M_PI / 180.0;
    double sinPhi = std::sin(phi);
    double cosPhi = std::cos(phi);
    double sinLam = std::sin(lam);
    double cosLam = std::cos(lam);

    double E = -sinLam * rhoEcef.x + cosLam * rhoEcef.y;
    double N = -sinPhi * cosLam * rhoEcef.x - sinPhi * sinLam * rhoEcef.y + cosPhi * rhoEcef.z;
    double U =  cosPhi * cosLam * rhoEcef.x + cosPhi * sinLam * rhoEcef.y + sinPhi * rhoEcef.z;

    return inet::Coord(E, N, U);
}

bool ConstellationManager::isAboveHorizonFast(const inet::Coord& ueEcef, const inet::Coord& satEcef) {
    // Fast vector dot product: r_ue . (r_sat - r_ue) < 0 => below local horizontal tangent plane
    inet::Coord rho = satEcef - ueEcef;
    return (ueEcef.x * rho.x + ueEcef.y * rho.y + ueEcef.z * rho.z) >= 0.0;
}

void ConstellationManager::computeSatelliteEcefState(
    const OrbitalElements& el, double time, inet::Coord& posEcef, inet::Coord& velEcef) const {

    double a = el.semiMajorAxisKm * 1000.0; // km -> meters
    double e = std::clamp(el.eccentricity, 1e-6, 0.999);
    double i = el.inclinationDeg * M_PI / 180.0;
    double raan0 = el.raanDeg * M_PI / 180.0;
    double argPerigee0 = el.argPerigeeDeg * M_PI / 180.0;
    double meanAnomaly0 = el.meanAnomalyDeg * M_PI / 180.0;

    double n0 = (el.meanMotionRevPerDay > 0.0) 
        ? (el.meanMotionRevPerDay * 2.0 * M_PI / 86400.0) 
        : std::sqrt(GM_EARTH / (a * a * a));

    // Secular J2 perturbations
    double p = a * (1.0 - e * e);
    double eta = WGS84_A / p;
    double cosI = std::cos(i);
    double sinI = std::sin(i);
    double cos2I = cosI * cosI;
    double j2Factor = 1.5 * J2_EARTH * eta * eta * n0;

    double raanDot = -j2Factor * cosI;
    double argPerigeeDot = 0.5 * j2Factor * (5.0 * cos2I - 1.0);
    double meanAnomalyDot = n0 * (1.0 + 0.5 * j2Factor * std::sqrt(1.0 - e * e) * (3.0 * cos2I - 1.0));

    double dt = time - el.epoch;
    double raan = raan0 + raanDot * dt;
    double argPerigee = argPerigee0 + argPerigeeDot * dt;
    double M = std::fmod(meanAnomaly0 + meanAnomalyDot * dt, 2.0 * M_PI);
    if (M < 0.0) M += 2.0 * M_PI;

    // Kepler equation solver: E - e sin(E) = M
    double E = M + e * std::sin(M) + 0.5 * e * e * std::sin(2.0 * M);
    for (int iter = 0; iter < 6; ++iter) {
        double f = E - e * std::sin(E) - M;
        double fPrime = 1.0 - e * std::cos(E);
        E -= f / fPrime;
    }

    double sinE = std::sin(E);
    double cosE = std::cos(E);
    double sinNu = (std::sqrt(1.0 - e * e) * sinE) / (1.0 - e * cosE);
    double cosNu = (cosE - e) / (1.0 - e * cosE);
    double nu = std::atan2(sinNu, cosNu);
    double r = a * (1.0 - e * cosE);

    // Orbital plane velocity
    double h = std::sqrt(GM_EARTH * p);
    double vr = (GM_EARTH / h) * e * sinNu;
    double vt = (GM_EARTH / h) * (1.0 + e * cosNu);

    double u = nu + argPerigee;
    double cosU = std::cos(u);
    double sinU = std::sin(u);
    double cosO = std::cos(raan);
    double sinO = std::sin(raan);

    // ECI coordinates
    double xEci = r * (cosO * cosU - sinO * sinU * cosI);
    double yEci = r * (sinO * cosU + cosO * sinU * cosI);
    double zEci = r * (sinU * sinI);

    double vxOrb = vr * cosNu - vt * sinNu;
    double vyOrb = vr * sinNu + vt * cosNu;

    double Px = cosO * std::cos(argPerigee) - sinO * std::sin(argPerigee) * cosI;
    double Py = sinO * std::cos(argPerigee) + cosO * std::sin(argPerigee) * cosI;
    double Pz = std::sin(argPerigee) * sinI;

    double Qx = -cosO * std::sin(argPerigee) - sinO * std::cos(argPerigee) * cosI;
    double Qy = -sinO * std::sin(argPerigee) + cosO * std::cos(argPerigee) * cosI;
    double Qz = std::cos(argPerigee) * sinI;

    double vxEci = vxOrb * Px + vyOrb * Qx;
    double vyEci = vxOrb * Py + vyOrb * Qy;
    double vzEci = vxOrb * Pz + vyOrb * Qz;

    // Earth rotation (ECI -> ECEF)
    double thetaG = EARTH_ROTATION_OMEGA * time;
    double cosG = std::cos(thetaG);
    double sinG = std::sin(thetaG);

    posEcef.x = cosG * xEci + sinG * yEci;
    posEcef.y = -sinG * xEci + cosG * yEci;
    posEcef.z = zEci;

    // Velocity in rotating ECEF frame: v_ecef = R_z(thetaG) * v_eci - omega_E x r_ecef
    double vxRot = cosG * vxEci + sinG * vyEci;
    double vyRot = -sinG * vxEci + cosG * vyEci;
    double vzRot = vzEci;

    velEcef.x = vxRot + EARTH_ROTATION_OMEGA * posEcef.y;
    velEcef.y = vyRot - EARTH_ROTATION_OMEGA * posEcef.x;
    velEcef.z = vzRot;
}

inet::Coord ConstellationManager::computePositionFromElements(const OrbitalElements& el, double time) {
    inet::Coord pos, vel;
    computeSatelliteEcefState(el, time, pos, vel);
    return pos;
}

inet::Coord ConstellationManager::computeVelocityFromElements(const OrbitalElements& el, double time) {
    inet::Coord pos, vel;
    computeSatelliteEcefState(el, time, pos, vel);
    return vel;
}

inet::Coord ConstellationManager::getSatellitePosition(const SatelliteInfo& sat) {
    double t = omnetpp::simTime().dbl();
    int idx = sat.globalId;
    if (idx >= 0 && idx < static_cast<int>(m_ephemerisCache.size())) {
        if (m_ephemerisCache[idx].timestamp == t) {
            return m_ephemerisCache[idx].positionEcef;
        }
        inet::Coord pos, vel;
        computeSatelliteEcefState(sat.elements, t, pos, vel);
        m_ephemerisCache[idx] = EphemerisCacheEntry{t, pos, vel};
        return pos;
    }
    return computePositionFromElements(sat.elements, t);
}

inet::Coord ConstellationManager::getSatelliteVelocity(const SatelliteInfo& sat) {
    double t = omnetpp::simTime().dbl();
    int idx = sat.globalId;
    if (idx >= 0 && idx < static_cast<int>(m_ephemerisCache.size())) {
        if (m_ephemerisCache[idx].timestamp == t) {
            return m_ephemerisCache[idx].velocityEcef;
        }
        inet::Coord pos, vel;
        computeSatelliteEcefState(sat.elements, t, pos, vel);
        m_ephemerisCache[idx] = EphemerisCacheEntry{t, pos, vel};
        return vel;
    }
    return computeVelocityFromElements(sat.elements, t);
}

inet::Coord ConstellationManager::getGroundStationPosition(const GroundStationInfo& gs) {
    return geodeticToEcef(gs.lat, gs.lon, gs.alt);
}

double ConstellationManager::calculateElevation(const inet::Coord& satPos, const inet::Coord& gsPos) {
    inet::Coord satEcef = (satPos.length() > 6000000.0) ? satPos : localToEcef(satPos);
    inet::Coord obsEcef = (gsPos.length() > 6000000.0) ? gsPos : localToEcef(gsPos);

    if (!isAboveHorizonFast(obsEcef, satEcef)) {
        return -90.0;
    }

    double latDeg, lonDeg, altM;
    ecefToGeodetic(obsEcef, latDeg, lonDeg, altM);
    inet::Coord rhoEcef = satEcef - obsEcef;
    double rangeM = rhoEcef.length();
    if (rangeM <= 0.0) return 90.0;

    inet::Coord rhoEnu = ecefToEnu(rhoEcef, latDeg, lonDeg);
    double sinElev = std::clamp(rhoEnu.z / rangeM, -1.0, 1.0);
    return std::asin(sinElev) * 180.0 / M_PI;
}

double ConstellationManager::calculateRange(const inet::Coord& posA, const inet::Coord& posB) {
    inet::Coord ecefA = (posA.length() > 6000000.0) ? posA : localToEcef(posA);
    inet::Coord ecefB = (posB.length() > 6000000.0) ? posB : localToEcef(posB);
    return (ecefA - ecefB).length() / 1000.0; // km
}

bool ConstellationManager::checkLOS(const inet::Coord& posA, const inet::Coord& posB, double minElevationDeg) {
    inet::Coord ecefA = (posA.length() > 6000000.0) ? posA : localToEcef(posA);
    inet::Coord ecefB = (posB.length() > 6000000.0) ? posB : localToEcef(posB);

    inet::Coord diff = ecefB - ecefA;
    double diffLen2 = diff.x * diff.x + diff.y * diff.y + diff.z * diff.z;
    if (diffLen2 <= 0.0) return true;

    double t = -(ecefA.x * diff.x + ecefA.y * diff.y + ecefA.z * diff.z) / diffLen2;
    if (t >= 0.0 && t <= 1.0) {
        inet::Coord closest = ecefA + diff * t;
        if (closest.length() < WGS84_B) {
            return false; // Obstructed by Earth ellipsoid
        }
    }

    if (minElevationDeg > 0.0) {
        double elevA = calculateElevation(ecefB, ecefA);
        if (elevA < minElevationDeg) return false;
    }

    return true;
}

ConstellationManager::TopocentricMetrics ConstellationManager::calculateTopocentricMetrics(
    int satId,
    const inet::Coord& observerPos,
    const inet::Coord& observerVel,
    double carrierFreqGhz,
    double minElevationDeg) {

    TopocentricMetrics m;
    if (satId < 0 || satId >= static_cast<int>(satellites.size())) {
        return m;
    }

    const SatelliteInfo& sat = satellites[satId];
    inet::Coord satEcef = getSatellitePosition(sat);
    inet::Coord satVel = getSatelliteVelocity(sat);

    inet::Coord obsEcef = (observerPos.length() > 6000000.0) ? observerPos : localToEcef(observerPos);
    inet::Coord obsVel = observerVel;

    // 1. Fast Horizon Culling
    if (!isAboveHorizonFast(obsEcef, satEcef)) {
        m.isVisible = false;
        m.elevationDeg = -90.0;
        return m;
    }

    // 2. Relative vectors in ECEF & ENU
    inet::Coord rhoEcef = satEcef - obsEcef;
    double slantRangeM = rhoEcef.length();
    m.slantRangeKm = slantRangeM / 1000.0;

    double latDeg, lonDeg, altM;
    ecefToGeodetic(obsEcef, latDeg, lonDeg, altM);
    m.rhoEnu = ecefToEnu(rhoEcef, latDeg, lonDeg);

    if (slantRangeM <= 0.0) {
        m.elevationDeg = 90.0;
        m.azimuthDeg = 0.0;
        m.isVisible = true;
        return m;
    }

    // 3. Elevation & Azimuth
    double sinElev = std::clamp(m.rhoEnu.z / slantRangeM, -1.0, 1.0);
    m.elevationDeg = std::asin(sinElev) * 180.0 / M_PI;

    m.azimuthDeg = std::atan2(m.rhoEnu.x, m.rhoEnu.y) * 180.0 / M_PI;
    if (m.azimuthDeg < 0.0) m.azimuthDeg += 360.0;

    double maskDeg = minElevationDeg;
    if (!azimuthHorizonMask.empty()) {
        maskDeg = std::max(maskDeg, getAzimuthElevationMask(m.azimuthDeg));
    }

    m.isTerrainBlocked = (m.elevationDeg < maskDeg);
    m.isVisible = (m.elevationDeg >= minElevationDeg && !m.isTerrainBlocked);

    if (m.isTerrainBlocked) {
        m.diffractionLossDb = NTNChannelModel::calculateObstacleDiffractionLoss(m.elevationDeg, maskDeg, carrierFreqGhz, m.slantRangeKm);
    } else {
        m.diffractionLossDb = 0.0;
    }

    // 4. Exact Doppler shift: f_d = -(v_rel . rho) / (c * d) * f_c
    inet::Coord vRel = satVel - obsVel;
    double vLos = (vRel.x * rhoEcef.x + vRel.y * rhoEcef.y + vRel.z * rhoEcef.z) / slantRangeM;
    double fcHz = carrierFreqGhz * 1e9;
    m.dopplerShiftHz = -(vLos / C_LIGHT_VACUUM) * fcHz;

    // Doppler rate: d(f_d)/dt
    double vRelLen2 = vRel.x * vRel.x + vRel.y * vRel.y + vRel.z * vRel.z;
    m.dopplerRateHzPerSec = -(fcHz / C_LIGHT_VACUUM) * ((vRelLen2 - vLos * vLos) / slantRangeM);

    return m;
}

double ConstellationManager::getAzimuthElevationMask(double azimuthDeg) const {
    if (azimuthHorizonMask.empty()) {
        return 10.0;
    }
    double az = std::fmod(azimuthDeg, 360.0);
    if (az < 0.0) az += 360.0;
    int numSectors = static_cast<int>(azimuthHorizonMask.size());
    double sectorWidth = 360.0 / numSectors;
    int sectorIdx = std::clamp(static_cast<int>(az / sectorWidth), 0, numSectors - 1);
    return azimuthHorizonMask[sectorIdx];
}

double ConstellationManager::calculateLinkBudget(const ISLLink& link) {
    // Simplified link budget for ISL
    // P_rx = P_tx + G_tx + G_rx - L_fs - L_atm - L_pointing - L_margin
    
    double freqHz = (islType == "laser") ? (3e8 / (islWavelengthNm * 1e-9)) : (islFrequencyGhz * 1e9);
    double wavelength = 3e8 / freqHz;
    
    // Free space loss
    double fsplDb = 20 * log10(4 * M_PI * link.distanceKm * 1000 / wavelength);
    
    // Pointing loss
    double pointingLossDb = 12 * pow(islPointingAccuracyDeg / 1.0, 2);  // Approximate
    
    // Atmospheric loss (negligible for space-space, significant for space-ground)
    double atmLossDb = 0.0;
    
    double rxPowerDbm = islTxPowerDbm + 30 + 30 - fsplDb - pointingLossDb - atmLossDb;  // Assume 30 dBi antennas
    
    // Quality based on margin above sensitivity
    double margin = rxPowerDbm - islRxSensitivityDbm;
    double quality = std::min(1.0, std::max(0.0, margin / 30.0));  // Normalize to 0-1
    
    return quality;
}

void ConstellationManager::establishISL(int satA, int satB) {
    // Signal to satellite modules to establish ISL
    if (satA >= 0 && satA < satellites.size() && satellites[satA].module) {
        // Send message or call method on satellite module
    }
    if (satB >= 0 && satB < satellites.size() && satellites[satB].module) {
        // Send message or call method on satellite module
    }
}

void ConstellationManager::breakISL(int satA, int satB) {
    // Signal to satellite modules to break ISL
}

void ConstellationManager::updateISLQuality() {
    for (auto& link : islLinks) {
        if (link.active) {
            link.linkQuality = calculateLinkBudget(link);
            link.lastQualityUpdate = omnetpp::simTime();
        }
    }
}

void ConstellationManager::triggerHandover(int ueId, int fromSat, int toSat) {
    totalHandovers++;
    emitHandover(ueId, fromSat, toSat, "signal_quality");
    
    // Notify UE and both satellites
    EV_INFO << "Handover triggered for UE " << ueId << ": sat " << fromSat << " -> " << toSat << "\n";
}

bool ConstellationManager::evaluateHandover(int ueId, int currentSat, int candidateSat) {
    // Evaluate if handover is beneficial
    // Compare link quality, load, elevation, etc.
    return true;  // Simplified
}

ConstellationManager::SatelliteInfo* ConstellationManager::getSatelliteByName(const std::string& name) {
    auto it = satNameToIndex.find(name);
    if (it != satNameToIndex.end()) {
        return &satellites[it->second];
    }
    return nullptr;
}

ConstellationManager::SatelliteInfo* ConstellationManager::getSatelliteById(int globalId) {
    if (globalId >= 0 && globalId < satellites.size()) {
        return &satellites[globalId];
    }
    return nullptr;
}

ConstellationManager::GroundStationInfo* ConstellationManager::getGroundStationByName(const std::string& name) {
    auto it = gsNameToIndex.find(name);
    if (it != gsNameToIndex.end()) {
        return &gstations[it->second];
    }
    return nullptr;
}

std::vector<int> ConstellationManager::findVisibleSatellites(const inet::Coord& observerPos, double minElevationDeg) {
    std::vector<int> visible;
    inet::Coord obsEcef = (observerPos.length() > 6000000.0) ? observerPos : localToEcef(observerPos);

    double latDeg, lonDeg, altM;
    ecefToGeodetic(obsEcef, latDeg, lonDeg, altM);

    for (size_t i = 0; i < satellites.size(); ++i) {
        inet::Coord satEcef = getSatellitePosition(satellites[i]);

        // Fast horizon culling filter: O(1) vector check skips trigonometry
        if (!isAboveHorizonFast(obsEcef, satEcef)) {
            continue;
        }

        inet::Coord rhoEcef = satEcef - obsEcef;
        double rangeM = rhoEcef.length();
        if (rangeM <= 0.0) {
            visible.push_back(i);
            continue;
        }

        inet::Coord rhoEnu = ecefToEnu(rhoEcef, latDeg, lonDeg);
        double elevation = std::asin(std::clamp(rhoEnu.z / rangeM, -1.0, 1.0)) * 180.0 / M_PI;
        if (elevation >= minElevationDeg) {
            visible.push_back(i);
        }
    }
    return visible;
}

void ConstellationManager::emitSatelliteDeployed(const SatelliteInfo& sat) {
    emit(satDeployedSignal, sat.globalId);
}

void ConstellationManager::emitISLEstablished(int satA, int satB) {
    emit(islEstablishedSignal, satA * 10000 + satB);  // Encode pair
}

void ConstellationManager::emitISLBroken(int satA, int satB) {
    emit(islBrokenSignal, satA * 10000 + satB);
}

void ConstellationManager::emitHandover(int ueId, int fromSat, int toSat, const std::string& reason) {
    // Could emit structured data
    emit(handoverSignal, ueId);
}

void ConstellationManager::configureFromYAML(const std::string& yamlContent) {
    // Simplified YAML parsing - in production use a proper YAML library
    // For now, just log that we received config
    EV_INFO << "Received YAML configuration (" << yamlContent.length() << " chars)\n";
}

void ConstellationManager::computeISLMeshShortestPaths() {
    int N = satellites.size();
    int M = gstations.size();
    if (N == 0) return;

    // 1. Build adjacency list for current active ISL topology
    m_islAdjacency.assign(N, std::vector<GraphEdge>());
    for (const auto& link : islLinks) {
        if (!link.active) continue;
        int u = link.satA;
        int v = link.satB;
        if (u < 0 || u >= N || v < 0 || v >= N) continue;

        double propDelayMs = (link.distanceKm / 299792.458) * 1000.0;
        double weightMs = propDelayMs + 0.050; // Propagation + OEO processing delay

        m_islAdjacency[u].push_back({v, weightMs, link.linkQuality});
        m_islAdjacency[v].push_back({u, weightMs, link.linkQuality});
    }

    // 2. Compute shortest path from each satellite to all ground stations via Dijkstra
    m_cachedRoutes.assign(N, std::vector<ISLRouteResult>(M));

    for (int g = 0; g < M; ++g) {
        const auto& targetSats = gstations[g].visibleSats;
        if (targetSats.empty()) continue;

        for (int s = 0; s < N; ++s) {
            std::vector<double> dist(N, std::numeric_limits<double>::infinity());
            std::vector<int> prev(N, -1);
            std::vector<double> minQuality(N, 1.0);

            using DistPair = std::pair<double, int>;
            std::priority_queue<DistPair, std::vector<DistPair>, std::greater<DistPair>> pq;

            dist[s] = 0.0;
            pq.push({0.0, s});

            while (!pq.empty()) {
                auto topItem = pq.top();
                double d = topItem.first;
                int u = topItem.second;
                pq.pop();

                if (d > dist[u]) continue;

                for (const auto& edge : m_islAdjacency[u]) {
                    int v = edge.targetSat;
                    double altDist = d + edge.weightMs;
                    if (altDist < dist[v]) {
                        dist[v] = altDist;
                        prev[v] = u;
                        minQuality[v] = std::min(minQuality[u], edge.linkQuality);
                        pq.push({altDist, v});
                    }
                }
            }

            int bestTargetSat = -1;
            double bestDist = std::numeric_limits<double>::infinity();
            for (int tSat : targetSats) {
                if (tSat >= 0 && tSat < N && dist[tSat] < bestDist) {
                    bestDist = dist[tSat];
                    bestTargetSat = tSat;
                }
            }

            ISLRouteResult res;
            res.sourceSatId = s;
            res.gatewayIndex = g;

            if (bestTargetSat != -1 && bestDist < std::numeric_limits<double>::infinity()) {
                res.routeFound = true;
                res.targetSatId = bestTargetSat;
                res.totalLatencyMs = bestDist;
                res.bottleneckQuality = minQuality[bestTargetSat];

                std::vector<int> path;
                for (int at = bestTargetSat; at != -1; at = prev[at]) {
                    path.push_back(at);
                    if (at == s) break;
                }
                std::reverse(path.begin(), path.end());
                res.pathSats = path;
                res.hopCount = std::max(0, static_cast<int>(path.size()) - 1);
            } else {
                res.routeFound = false;
            }

            m_cachedRoutes[s][g] = res;
        }
    }

    if (N > 0 && M > 0) {
        const auto& r0 = m_cachedRoutes[0][0];
        if (r0.routeFound) {
            emit(m_sigIslHopCount, static_cast<long>(r0.hopCount));
            emit(m_sigIslRouteLatency, r0.totalLatencyMs);
        } else {
            emit(m_sigIslMeshOutage, 1L);
        }
    }
}

ConstellationManager::ISLRouteResult ConstellationManager::getShortestRouteToGateway(int servingSatId, int gatewayIndex) {
    if (servingSatId >= 0 && servingSatId < static_cast<int>(m_cachedRoutes.size())) {
        if (gatewayIndex >= 0 && gatewayIndex < static_cast<int>(m_cachedRoutes[servingSatId].size())) {
            return m_cachedRoutes[servingSatId][gatewayIndex];
        }
    }
    ISLRouteResult res;
    res.sourceSatId = servingSatId;
    res.gatewayIndex = gatewayIndex;
    res.routeFound = false;
    return res;
}

ConstellationManager::ISLRouteResult ConstellationManager::getShortestRouteToAnyGateway(int servingSatId) {
    ISLRouteResult best;
    best.totalLatencyMs = std::numeric_limits<double>::infinity();
    if (servingSatId >= 0 && servingSatId < static_cast<int>(m_cachedRoutes.size())) {
        for (const auto& r : m_cachedRoutes[servingSatId]) {
            if (r.routeFound && r.totalLatencyMs < best.totalLatencyMs) {
                best = r;
            }
        }
    }
    return best;
}

} // namespace ntn
} // namespace artery