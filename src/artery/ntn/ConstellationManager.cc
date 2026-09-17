#include "artery/ntn/ConstellationManager.h"
#include <omnetpp.h>
#include <cmath>
#include <fstream>
#include <sstream>
#include <algorithm>

namespace artery {
namespace ntn {

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
        
        // ISL params
        islEnabled = par("islEnabled");
        islType = par("islType").stringValue();
        islMaxRangeKm = par("islMaxRangeKm");
        islPortsPerSat = par("islPortsPerSat");
        islWavelengthNm = par("islWavelengthNm");
        islTxPowerDbm = par("islTxPowerDbm");
        islRxSensitivityDbm = par("islRxSensitivityDbm");
        islPointingAccuracyDeg = par("islPointingAccuracyDeg");
        islAcquisitionTimeMs = par("islAcquisitionTimeMs");
        
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
        
        // Load configuration
        loadConfiguration();
        
        // Deploy constellation
        deployConstellation();
        
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
    const double earthRadiusKm = 6371.0;
    const double mu = 398600.4418;  // km^3/s^2
    
    el.semiMajorAxisKm = earthRadiusKm + altitudeKm;
    el.eccentricity = 0.0;  // Circular
    el.inclinationDeg = inclinationDeg;
    
    // RAAN for this plane
    el.raanDeg = planeIdx * (360.0 / P);
    
    // Argument of perigee (0 for circular)
    el.argPerigeeDeg = 0.0;
    
    // Mean anomaly with phasing
    double satellitesPerPlane = T / P;
    double meanAnomalyBase = satIdx * (360.0 / satellitesPerPlane);
    double phasing = F * planeIdx * (360.0 / T);
    el.meanAnomalyDeg = fmod(meanAnomalyBase + phasing, 360.0);
    
    // Mean motion
    double n = sqrt(mu / pow(el.semiMajorAxisKm, 3));  // rad/s
    el.meanMotionRevPerDay = n * 86400.0 / (2 * M_PI);  // rev/day
    
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

void ConstellationManager::computeGroundStationVisibility() {
    for (auto& gs : gstations) {
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
                sat.visibleGroundStations.push_back(gstations.size() - 1);  // Approximate
            }
        }
    }
}

inet::Coord ConstellationManager::getSatellitePosition(const SatelliteInfo& sat) {
    return computePositionFromElements(sat.elements, omnetpp::simTime().dbl());
}

inet::Coord ConstellationManager::getGroundStationPosition(const GroundStationInfo& gs) {
    // Convert lat/lon/alt to coordinate meters
    return inet::Coord(gs.lon * 111000.0, gs.lat * 111000.0, gs.alt);
}

double ConstellationManager::calculateElevation(const inet::Coord& satPos, const inet::Coord& gsPos) {
    // Calculate elevation angle from ground position to satellite in degrees
    inet::Coord diff = satPos - gsPos;
    double range = diff.length();
    double heightDiff = diff.z;
    
    if (range <= 0.0) return 90.0;
    
    double sinElev = std::max(-1.0, std::min(1.0, heightDiff / range));
    double elevation = std::asin(sinElev) * 180.0 / M_PI;
    return elevation;
}

inet::Coord ConstellationManager::computePositionFromElements(const OrbitalElements& el, double time) {
    // Simplified position computation from orbital elements
    // In reality, use SGP4 propagator
    double n = el.meanMotionRevPerDay * 2 * M_PI / 86400.0;  // rad/s
    double M = el.meanAnomalyDeg * M_PI / 180.0 + n * time;
    
    // For circular orbit
    double a = el.semiMajorAxisKm;
    double i = el.inclinationDeg * M_PI / 180.0;
    double raan = el.raanDeg * M_PI / 180.0;
    
    // Position in orbital plane
    double x_orb = a * cos(M);
    double y_orb = a * sin(M);
    double z_orb = 0;
    
    // Rotate to ECI
    double cos_i = cos(i), sin_i = sin(i);
    double cos_raan = cos(raan), sin_raan = sin(raan);
    
    double x = cos_raan * x_orb - sin_raan * cos_i * y_orb;
    double y = sin_raan * x_orb + cos_raan * cos_i * y_orb;
    double z = sin_i * y_orb;
    
    return inet::Coord(x * 1000, y * 1000, z * 1000);  // Convert to meters
}

double ConstellationManager::calculateRange(const inet::Coord& posA, const inet::Coord& posB) {
    return (posA - posB).length() / 1000.0;  // Return in km
}

bool ConstellationManager::checkLOS(const inet::Coord& posA, const inet::Coord& posB, double minElevationDeg) {
    // Check if line of sight is obstructed by Earth
    // Simplified: check if the line passes above Earth's surface
    const double earthRadiusKm = 6371.0;
    
    // Calculate closest approach to Earth center
    inet::Coord diff = posB - posA;
    double t = -(posA.x * diff.x + posA.y * diff.y + posA.z * diff.z) / 
               (diff.x * diff.x + diff.y * diff.y + diff.z * diff.z);
    
    if (t >= 0 && t <= 1) {
        inet::Coord closest = posA + diff * t;
        double distFromCenter = closest.length() / 1000.0;  // km
        
        if (distFromCenter < earthRadiusKm) {
            return false;  // Obstructed by Earth
        }
    }
    
    // Check elevation at endpoints
    double elevA = calculateElevation(posA, posB);  // Simplified
    double elevB = calculateElevation(posB, posA);
    
    return elevA >= minElevationDeg && elevB >= minElevationDeg;
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
    for (size_t i = 0; i < satellites.size(); ++i) {
        inet::Coord satPos = getSatellitePosition(satellites[i]);
        double elevation = calculateElevation(satPos, observerPos);
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
    
    // TODO: Parse YAML and populate shells, groundStations, etc.
    // This would use a library like yaml-cpp
}

} // namespace ntn
} // namespace artery