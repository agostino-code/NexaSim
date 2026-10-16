#include "artery/ntn/UnifiedMobilityManager.h"
#include "artery/ntn/ConstellationManager.h"
#include "artery/nr/NRManager.h"
#include <omnetpp.h>
#include <cmath>
#include <algorithm>

namespace artery {
namespace ntn {

Define_Module(UnifiedMobilityManager);

void UnifiedMobilityManager::initialize(int stage) {
    if (stage == 0) {
        // Read policy parameters
        policy.rsrpThresholdDbm = par("rsrpThresholdDbm");
        policy.rsrqThresholdDb = par("rsrqThresholdDb");
        policy.sinrThresholdDb = par("sinrThresholdDb");
        policy.elevationThresholdDeg = par("elevationThresholdDeg");
        policy.elevationMinDeg = par("elevationMinDeg");
        policy.hysteresisDb = par("hysteresisDb");
        policy.timeToTriggerMs = par("timeToTriggerMs");
        policy.maxHandoverDurationMs = par("maxHandoverDurationMs");
        policy.makeBeforeBreak = par("makeBeforeBreak");
        policy.mbBOverlapMs = par("mbBOverlapMs");
        policy.loadThreshold = par("loadThreshold");
        policy.loadBalancingEnabled = par("loadBalancingEnabled");
        policy.qosBasedSteering = par("qosBasedSteering");
        
        dualConnectivityEnabled = par("dualConnectivityEnabled");
        evaluationIntervalMs = par("evaluationIntervalMs");
        
        if (hasPar("originLatitude")) originLatitude = par("originLatitude").doubleValue();
        if (hasPar("originLongitude")) originLongitude = par("originLongitude").doubleValue();
        if (hasPar("originAltitude")) originAltitude = par("originAltitude").doubleValue();
        if (hasPar("trajectoryType")) trajectoryType = par("trajectoryType").stringValue();

        // Find other managers
        constellationManager = dynamic_cast<ConstellationManager*>(
            getSimulation()->getModuleByPath("constellationManager"));
        nrManager = dynamic_cast<nr::NRManager*>(
            getSimulation()->getModuleByPath("nrManager"));
        
        // Register signals
        handoverTriggeredSignal = registerSignal("handoverTriggered");
        handoverCompletedSignal = registerSignal("handoverCompleted");
        handoverFailedSignal = registerSignal("handoverFailed");
        dualConnectivityChangedSignal = registerSignal("dualConnectivityChanged");
        trafficSteeringSignal = registerSignal("trafficSteering");
        ueMeasurementSignal = registerSignal("ueMeasurement");
        
        // Schedule periodic evaluation
        evaluationTimer = new omnetpp::cMessage("evaluationTimer");
        scheduleAt(omnetpp::simTime() + evaluationIntervalMs / 1000.0, evaluationTimer);
        
        EV_INFO << "UnifiedMobilityManager initialized\n";
    }
}

void UnifiedMobilityManager::handleMessage(omnetpp::cMessage* msg) {
    if (msg == evaluationTimer) {
        evaluateAllUEs();
        scheduleAt(omnetpp::simTime() + evaluationIntervalMs / 1000.0, evaluationTimer);
    } else {
        delete msg;
    }
}

void UnifiedMobilityManager::finish() {
    recordScalar("totalHandovers", totalHandovers);
    recordScalar("successfulHandovers", successfulHandovers);
    recordScalar("failedHandovers", failedHandovers);
    recordScalar("dualConnectivityActivations", dualConnectivityActivations);
    recordScalar("trafficSteeringEvents", trafficSteeringEvents);
    recordScalar("handoverSuccessRate", 
        totalHandovers > 0 ? double(successfulHandovers) / totalHandovers : 0);
    
    cancelAndDelete(evaluationTimer);
}

void UnifiedMobilityManager::registerNetworkNode(const NetworkNode& node) {
    networkNodes[node.id] = node;
    EV_INFO << "UnifiedMobilityManager: Registered " << node.id 
            << " (" << static_cast<int>(node.type) << ")\n";
}

void UnifiedMobilityManager::unregisterNetworkNode(const std::string& nodeId) {
    networkNodes.erase(nodeId);
}

void UnifiedMobilityManager::updateNetworkNode(const std::string& nodeId, const NetworkNode& node) {
    auto it = networkNodes.find(nodeId);
    if (it != networkNodes.end()) {
        it->second = node;
    }
}

void UnifiedMobilityManager::registerUE(int ueId, const UEContext& context) {
    ueContexts[ueId] = context;
}

void UnifiedMobilityManager::unregisterUE(int ueId) {
    ueContexts.erase(ueId);
}

void UnifiedMobilityManager::updateUEMeasurements(int ueId, const UEContext& measurements) {
    auto it = ueContexts.find(ueId);
    if (it != ueContexts.end()) {
        UEContext& ue = it->second;
        ue.currentRsrpDbm = measurements.currentRsrpDbm;
        ue.currentRsrqDb = measurements.currentRsrqDb;
        ue.currentSinrDb = measurements.currentSinrDb;
        ue.targetRsrpDbm = measurements.targetRsrpDbm;
        ue.targetRsrqDb = measurements.targetRsrqDb;
        ue.targetSinrDb = measurements.targetSinrDb;
        ue.currentElevationDeg = measurements.currentElevationDeg;
        ue.targetElevationDeg = measurements.targetElevationDeg;
        ue.elevationRateDegPerSec = measurements.elevationRateDegPerSec;
        
        emit(ueMeasurementSignal, ueId);
    }
}

void UnifiedMobilityManager::evaluateAllUEs() {
    for (auto& [ueId, ue] : ueContexts) {
        if (!ue.handoverInProgress) {
            evaluateUE(ueId);
        }
    }
}

void UnifiedMobilityManager::evaluateUE(int ueId) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    
    // Check if current connection is degrading
    bool currentDegraded = (ue.currentRsrpDbm < policy.rsrpThresholdDbm ||
                           ue.currentRsrqDb < policy.rsrqThresholdDb ||
                           ue.currentSinrDb < policy.sinrThresholdDb);
    
    // For NTN, check elevation
    bool elevationLow = false;
    if (ue.currentNetwork == NetworkType::NTN_LEO) {
        elevationLow = ue.currentElevationDeg < policy.elevationThresholdDeg;
    }
    
    // Check load balancing
    bool loadHigh = false;
    if (policy.loadBalancingEnabled) {
        auto nodeIt = networkNodes.find(ue.currentNodeId);
        if (nodeIt != networkNodes.end()) {
            loadHigh = nodeIt->second.currentLoad > policy.loadThreshold;
        }
    }
    
    if (currentDegraded || elevationLow || loadHigh) {
        if (shouldTriggerHandover(ue)) {
            auto* targetNode = findBestTargetNode(ue);
            if (targetNode) {
                HandoverType type = determineHandoverType(ue, targetNode->id);
                HandoverTrigger trigger = determineHandoverTrigger(ue);
                initiateHandover(ueId, targetNode->id, type, trigger);
            }
        }
    }
    
    // Evaluate dual connectivity
    if (dualConnectivityEnabled && !ue.dualConnectivityActive) {
        evaluateDualConnectivity(ueId);
    }
    
    // Evaluate traffic steering
    if (ue.dualConnectivityActive) {
        evaluateTrafficSteering(ueId);
    }
}

bool UnifiedMobilityManager::shouldTriggerHandover(const UEContext& ue) {
    // Check if we have a viable target
    auto* target = findBestTargetNode(ue);
    if (!target) return false;
    
    // Check hysteresis
    double currentQuality = std::max(ue.currentRsrpDbm, ue.currentRsrqDb + 100);  // Normalize
    double targetQuality = std::max(target->currentLoad < 0.5 ? -80.0 : -100.0, -100.0);  // Simplified
    
    return targetQuality > currentQuality + policy.hysteresisDb;
}

UnifiedMobilityManager::HandoverType UnifiedMobilityManager::determineHandoverType(
    const UEContext& ue, const std::string& targetNodeId) {
    
    auto currentIt = networkNodes.find(ue.currentNodeId);
    auto targetIt = networkNodes.find(targetNodeId);
    
    if (currentIt == networkNodes.end() || targetIt == networkNodes.end()) {
        return HandoverType::HARD_HANDOVER;
    }
    
    NetworkType currentType = currentIt->second.type;
    NetworkType targetType = targetIt->second.type;
    
    if (currentType == NetworkType::TERRESTRIAL_NR && targetType == NetworkType::TERRESTRIAL_NR) {
        return HandoverType::INTRA_NR;
    } else if ((currentType == NetworkType::TERRESTRIAL_NR && targetType == NetworkType::NTN_LEO) ||
               (currentType == NetworkType::NTN_LEO && targetType == NetworkType::TERRESTRIAL_NR)) {
        return policy.makeBeforeBreak ? HandoverType::MAKE_BEFORE_BREAK : HandoverType::INTER_NR_NTN;
    } else if (currentType == NetworkType::NTN_LEO && targetType == NetworkType::NTN_LEO) {
        return HandoverType::INTRA_NTN;
    } else if (targetType == NetworkType::GROUND_STATION) {
        return HandoverType::NTN_TO_GS;
    }
    
    return HandoverType::HARD_HANDOVER;
}

UnifiedMobilityManager::HandoverTrigger UnifiedMobilityManager::determineHandoverTrigger(const UEContext& ue) {
    if (ue.currentElevationDeg < policy.elevationThresholdDeg && ue.currentNetwork == NetworkType::NTN_LEO) {
        return HandoverTrigger::ELEVATION_ANGLE;
    }
    
    auto nodeIt = networkNodes.find(ue.currentNodeId);
    if (nodeIt != networkNodes.end() && nodeIt->second.currentLoad > policy.loadThreshold) {
        return HandoverTrigger::LOAD_BALANCING;
    }
    
    if (ue.currentRsrpDbm < policy.rsrpThresholdDbm) {
        return HandoverTrigger::SIGNAL_STRENGTH;
    }
    
    if (policy.qosBasedSteering && ue.requiredLatencyMs < 10) {
        return HandoverTrigger::QOS_REQUIREMENT;
    }
    
    return HandoverTrigger::SIGNAL_STRENGTH;
}

void UnifiedMobilityManager::initiateHandover(int ueId, const std::string& targetNodeId, 
                                              HandoverType type, HandoverTrigger trigger) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    ue.previousNodeId = ue.currentNodeId;
    ue.previousNetwork = ue.currentNetwork;
    ue.handoverInProgress = true;
    ue.targetNodeId = targetNodeId;
    ue.targetNetwork = networkNodes[targetNodeId].type;
    ue.handoverType = type;
    ue.trigger = trigger;
    ue.handoverStartTime = omnetpp::simTime();
    ue.preparationPhase = 1;
    ue.handoverState = HandoverState::MEASUREMENT_REPORTED;

    if (ue.targetNetwork == NetworkType::NTN_LEO) {
        auto nodeIt = networkNodes.find(targetNodeId);
        double alt = (nodeIt != networkNodes.end() && nodeIt->second.altitude > 0) ? nodeIt->second.altitude : 550000.0;
        double elev = std::max(5.0, ue.targetElevationDeg);
        ue.propagationDelayMs = computeSlantRangePropagationDelayMs(alt, elev);
    } else {
        ue.propagationDelayMs = 0.5;
    }

    totalHandovers++;
    emit(handoverTriggeredSignal, ueId);
    
    EV_INFO << "UnifiedMobilityManager: Handover initiated for UE " << ueId 
            << " from " << ue.currentNodeId << " to " << targetNodeId 
            << " (type: " << static_cast<int>(type) << ", trigger: " << static_cast<int>(trigger) << ")\n";
    
    // Notify network nodes
    notifyNetworkNodes(ue, "handover_initiated");
    
    // For make-before-break, start dual connectivity
    if (type == HandoverType::MAKE_BEFORE_BREAK && dualConnectivityEnabled) {
        activateDualConnectivity(ueId, ue.currentNodeId, targetNodeId);
    } else {
        // Hard handover - execute after preparation
        ue.preparationPhase = 3;
        executeHandover(ueId);
    }
}

void UnifiedMobilityManager::executeHandover(int ueId) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    
    std::string oldNodeId = ue.currentNodeId;
    std::string newNodeId = ue.targetNodeId;
    
    // Execute handover in respective managers
    if (ue.targetNetwork == NetworkType::TERRESTRIAL_NR && nrManager) {
        // nrManager->handoverUE(ueId, oldNodeId, newNodeId);
    } else if (ue.targetNetwork == NetworkType::NTN_LEO && constellationManager) {
        // constellationManager->triggerHandover(ueId, oldNodeId, newNodeId);
    }
    
    // Update UE context
    ue.currentNodeId = newNodeId;
    ue.currentNetwork = ue.targetNetwork;
    ue.handoverInProgress = false;
    ue.handoverState = HandoverState::HANDOVER_COMPLETED;
    ue.preparationPhase = 0;
    
    successfulHandovers++;
    emit(handoverCompletedSignal, ueId);
    
    EV_INFO << "UnifiedMobilityManager: Handover completed for UE " << ueId 
            << " to " << newNodeId << "\n";
    
    notifyNetworkNodes(ue, "handover_completed");
}

void UnifiedMobilityManager::completeHandover(int ueId, bool success) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    
    if (success) {
        successfulHandovers++;
        emit(handoverCompletedSignal, ueId);
        ue.handoverState = HandoverState::HANDOVER_COMPLETED;
    } else {
        failedHandovers++;
        emit(handoverFailedSignal, ueId);
        ue.currentNodeId = ue.previousNodeId;
        ue.currentNetwork = ue.previousNetwork;
        ue.handoverState = HandoverState::IDLE;
    }

    ue.handoverInProgress = false;
    ue.preparationPhase = 0;
}

void UnifiedMobilityManager::abortHandover(int ueId, const std::string& reason) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;

    UEContext& ue = it->second;
    failedHandovers++;
    ue.handoverInProgress = false;
    ue.handoverState = HandoverState::IDLE;
    ue.preparationPhase = 0;
    
    emit(handoverFailedSignal, ueId);
    
    EV_WARN << "UnifiedMobilityManager: Handover aborted for UE " << ueId << ": " << reason << "\n";
}

void UnifiedMobilityManager::evaluateDualConnectivity(int ueId) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    
    // Find one NR and one NTN node
    std::string nrNodeId, ntnNodeId;
    for (const auto& [id, node] : networkNodes) {
        if (node.type == NetworkType::TERRESTRIAL_NR && nrNodeId.empty()) {
            nrNodeId = id;
        } else if (node.type == NetworkType::NTN_LEO && ntnNodeId.empty()) {
            ntnNodeId = id;
        }
    }
    
    if (!nrNodeId.empty() && !ntnNodeId.empty()) {
        activateDualConnectivity(ueId, nrNodeId, ntnNodeId);
    }
}

void UnifiedMobilityManager::activateDualConnectivity(int ueId, const std::string& nrNodeId, const std::string& ntnNodeId) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    ue.dualConnectivityActive = true;
    ue.nrNodeId = nrNodeId;
    ue.ntnNodeId = ntnNodeId;
    ue.nrRatio = 0.5;  // Start with balanced
    
    dualConnectivityActivations++;
    emit(dualConnectivityChangedSignal, ueId);
    
    EV_INFO << "UnifiedMobilityManager: Dual connectivity activated for UE " << ueId 
            << " (NR: " << nrNodeId << ", NTN: " << ntnNodeId << ")\n";
    
    // Notify managers
    if (nrManager) {
        // nrManager->configureDualConnectivity(ueId, true);
    }
    if (constellationManager) {
        // constellationManager->configureDualConnectivity(ueId, true);
    }
}

void UnifiedMobilityManager::deactivateDualConnectivity(int ueId) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    ue.dualConnectivityActive = false;
    
    emit(dualConnectivityChangedSignal, ueId);
}

void UnifiedMobilityManager::updateBearerSplit(int ueId, double nrRatio) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    ue.nrRatio = std::clamp(nrRatio, 0.0, 1.0);
    
    if (nrManager) {
        // nrManager->splitBearer(ueId, nrRatio);
    }
    if (constellationManager) {
        // constellationManager->splitBearer(ueId, 1.0 - nrRatio);
    }
}

void UnifiedMobilityManager::evaluateTrafficSteering(int ueId) {
    auto it = ueContexts.find(ueId);
    if (it == ueContexts.end()) return;
    
    UEContext& ue = it->second;
    if (!ue.dualConnectivityActive) return;
    
    auto nrIt = networkNodes.find(ue.nrNodeId);
    auto ntnIt = networkNodes.find(ue.ntnNodeId);
    
    if (nrIt == networkNodes.end() || ntnIt == networkNodes.end()) return;
    
    double nrUtility = calculateUtility(ue, nrIt->second);
    double ntnUtility = calculateUtility(ue, ntnIt->second);
    
    // Determine optimal split
    double nrRatio;
    if (nrUtility > ntnUtility * 1.5) {
        nrRatio = 0.8;
    } else if (ntnUtility > nrUtility * 1.5) {
        nrRatio = 0.2;
    } else {
        nrRatio = 0.5;
    }
    
    if (std::abs(nrRatio - ue.nrRatio) > 0.1) {
        steerTraffic(ueId, nrRatio, "utility_optimization");
    }
}

double UnifiedMobilityManager::calculateUtility(const UEContext& ue, const NetworkNode& node) {
    double utility = 0;
    
    // Throughput utility (logarithmic)
    utility += 0.3 * std::log10(1 + node.maxThroughputMbps / 10.0);
    
    // Latency utility (inverse)
    utility += 0.3 * (100.0 / std::max(1.0, node.latencyMs));
    
    // Load utility (lower load = better)
    utility += 0.2 * (1.0 - node.currentLoad);
    
    // Reliability
    utility += 0.1 * (node.supportsQoS ? 1.0 : 0.5);
    
    // Slice support
    for (const auto& slice : node.supportedSlices) {
        if (slice == ue.sliceName) {
            utility += 0.1;
            break;
        }
    }
    
    return utility;
}

void UnifiedMobilityManager::steerTraffic(int ueId, double nrRatio, const std::string& reason) {
    updateBearerSplit(ueId, nrRatio);
    trafficSteeringEvents++;
    emit(trafficSteeringSignal, ueId);
    
    EV_INFO << "UnifiedMobilityManager: Traffic steered for UE " << ueId 
            << " to NR ratio: " << (nrRatio * 100) << "% (" << reason << ")\n";
}

void UnifiedMobilityManager::evaluateSatelliteVisibility(int ueId) {
    if (!constellationManager) return;
    inet::Coord pos = getUEPosition3D(ueId);
    auto visibleSats = constellationManager->findVisibleSatellites(pos, policy.elevationMinDeg);
    auto it = ueContexts.find(ueId);
    if (it != ueContexts.end() && !visibleSats.empty()) {
        int bestSat = visibleSats[0];
        auto metrics = constellationManager->calculateTopocentricMetrics(bestSat, pos, inet::Coord(0,0,0), 28.0, policy.elevationMinDeg);
        it->second.currentElevationDeg = metrics.elevationDeg;
    }
}

void UnifiedMobilityManager::predictSatellitePasses(int ueId) {
    // Predictive lookahead for upcoming passes
}

void UnifiedMobilityManager::setOrigin(double latDeg, double lonDeg, double altM) {
    originLatitude = latDeg;
    originLongitude = lonDeg;
    originAltitude = altM;
}

inet::Coord UnifiedMobilityManager::localToEcef(const inet::Coord& localPos) const {
    constexpr double a = 6378137.0;
    constexpr double f = 1.0 / 298.257223563;
    constexpr double e2 = 2.0 * f - f * f;

    double phi = originLatitude * M_PI / 180.0;
    double lam = originLongitude * M_PI / 180.0;
    double sinPhi = std::sin(phi);
    double cosPhi = std::cos(phi);
    double sinLam = std::sin(lam);
    double cosLam = std::cos(lam);

    double N = a / std::sqrt(1.0 - e2 * sinPhi * sinPhi);
    double x0 = (N + originAltitude) * cosPhi * cosLam;
    double y0 = (N + originAltitude) * cosPhi * sinLam;
    double z0 = (N * (1.0 - e2) + originAltitude) * sinPhi;

    double dx = -sinLam * localPos.x - sinPhi * cosLam * localPos.y + cosPhi * cosLam * localPos.z;
    double dy =  cosLam * localPos.x - sinPhi * sinLam * localPos.y + cosPhi * sinLam * localPos.z;
    double dz =  0.0 * localPos.x    + cosPhi * localPos.y          + sinPhi * localPos.z;

    return inet::Coord(x0 + dx, y0 + dy, z0 + dz);
}

inet::Coord UnifiedMobilityManager::localToGeodetic(const inet::Coord& localPos) const {
    inet::Coord ecef = localToEcef(localPos);
    constexpr double a = 6378137.0;
    constexpr double f = 1.0 / 298.257223563;
    constexpr double b = a * (1.0 - f);
    constexpr double e2 = 2.0 * f - f * f;
    constexpr double ep2 = (a * a - b * b) / (b * b);

    double p = std::sqrt(ecef.x * ecef.x + ecef.y * ecef.y);
    double lonDeg = std::atan2(ecef.y, ecef.x) * 180.0 / M_PI;
    if (p < 1e-6) {
        double latDeg = ecef.z >= 0.0 ? 90.0 : -90.0;
        double altM = std::abs(ecef.z) - b;
        return inet::Coord(lonDeg, latDeg, altM);
    }
    double theta = std::atan2(ecef.z * a, p * b);
    double sTh = std::sin(theta);
    double cTh = std::cos(theta);
    double phi = std::atan2(ecef.z + ep2 * b * sTh * sTh * sTh, p - e2 * a * cTh * cTh * cTh);
    double latDeg = phi * 180.0 / M_PI;
    double sinPhi = std::sin(phi);
    double N = a / std::sqrt(1.0 - e2 * sinPhi * sinPhi);
    double altM = p / std::cos(phi) - N;
    return inet::Coord(lonDeg, latDeg, altM);
}

inet::Coord UnifiedMobilityManager::geodeticToLocal(double latDeg, double lonDeg, double altM) const {
    constexpr double a = 6378137.0;
    constexpr double f = 1.0 / 298.257223563;
    constexpr double e2 = 2.0 * f - f * f;

    double phi = latDeg * M_PI / 180.0;
    double lam = lonDeg * M_PI / 180.0;
    double sinPhi = std::sin(phi);
    double cosPhi = std::cos(phi);
    double sinLam = std::sin(lam);
    double cosLam = std::cos(lam);

    double N = a / std::sqrt(1.0 - e2 * sinPhi * sinPhi);
    double x = (N + altM) * cosPhi * cosLam;
    double y = (N + altM) * cosPhi * sinLam;
    double z = (N * (1.0 - e2) + altM) * sinPhi;

    inet::Coord targetEcef(x, y, z);
    inet::Coord originEcef = localToEcef(inet::Coord(0, 0, 0));
    inet::Coord diff = targetEcef - originEcef;

    double phi0 = originLatitude * M_PI / 180.0;
    double lam0 = originLongitude * M_PI / 180.0;
    double sPhi0 = std::sin(phi0);
    double cPhi0 = std::cos(phi0);
    double sLam0 = std::sin(lam0);
    double cLam0 = std::cos(lam0);

    double east  = -sLam0 * diff.x + cLam0 * diff.y;
    double north = -sPhi0 * cLam0 * diff.x - sPhi0 * sLam0 * diff.y + cPhi0 * diff.z;
    double up    =  cPhi0 * cLam0 * diff.x + cPhi0 * sLam0 * diff.y + sPhi0 * diff.z;
    return inet::Coord(east, north, up);
}

double UnifiedMobilityManager::calculate3DElevation(const inet::Coord& ueLocalPos, const inet::Coord& satLocalPos) const {
    inet::Coord diff = satLocalPos - ueLocalPos;
    double slantDist = diff.length();
    if (slantDist < 1e-3) return 90.0;

    double sinElev = diff.z / slantDist;
    sinElev = std::clamp(sinElev, -1.0, 1.0);
    return std::asin(sinElev) * 180.0 / M_PI;
}

bool UnifiedMobilityManager::check3DLOS(const inet::Coord& ueLocalPos, const inet::Coord& satLocalPos, double minElevationDeg) const {
    double elev = calculate3DElevation(ueLocalPos, satLocalPos);
    return elev >= minElevationDeg;
}

void UnifiedMobilityManager::updateUEPosition3D(int ueId, const inet::Coord& pos, const inet::Coord& vel) {
    uePositions3D[ueId] = pos;
    ueVelocities3D[ueId] = vel;
}

inet::Coord UnifiedMobilityManager::getUEPosition3D(int ueId) const {
    auto it = uePositions3D.find(ueId);
    if (it != uePositions3D.end()) {
        return it->second;
    }
    return inet::Coord(0, 0, 1.5);
}

UnifiedMobilityManager::NetworkNode* UnifiedMobilityManager::findBestTargetNode(const UEContext& ue, NetworkType preferredType) {
    NetworkNode* best = nullptr;
    double bestScore = -1;
    
    for (auto& [id, node] : networkNodes) {
        if (id == ue.currentNodeId) continue;
        if (node.currentLoad > policy.loadThreshold) continue;
        
        // Prefer target type
        if (preferredType != NetworkType::TERRESTRIAL_NR && node.type != preferredType) {
            continue;
        }
        
        double score = calculateUtility(ue, node);
        
        // Boost score for preferred type
        if (node.type == preferredType) {
            score *= 1.2;
        }
        
        if (score > bestScore) {
            bestScore = score;
            best = &node;
        }
    }
    
    return best;
}

double UnifiedMobilityManager::calculateHandoverCost(const UEContext& ue, const NetworkNode& target) {
    // Calculate cost of handover (signaling, interruption, etc.)
    double cost = 0;
    
    // Base cost
    cost += 10;  // Signaling overhead
    
    // Interruption time cost
    cost += 5 * (policy.maxHandoverDurationMs / 10.0);
    
    // Ping-pong prevention
    // ... 
    
    return cost;
}

void UnifiedMobilityManager::notifyNetworkNodes(const UEContext& ue, const std::string& event) {
    // Send notifications to current and target nodes
}

void UnifiedMobilityManager::configureFromYAML(const std::string& yamlContent) {
    EV_INFO << "UnifiedMobilityManager: Received YAML config\n";
}

} // namespace ntn
} // namespace artery