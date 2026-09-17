#include "artery/ntn/UserTerminal.h"
#include "artery/ntn/ConstellationManager.h"
#include "inet/mobility/contract/IMobility.h"
#include <omnetpp.h>
#include <cmath>
#include <complex>
#include <algorithm>
#include <random>

namespace artery {
namespace ntn {

Define_Module(UserTerminal);

void UserTerminal::initialize(int stage) {
    if (stage == 0) {
        // Read configuration
        terminalId = par("terminalId");
        terminalType = par("terminalType").stringValue();
        
        // Phased array config
        arrayConfig.numElements = par("arrayNumElements");
        arrayConfig.elementSpacingWavelengths = par("arrayElementSpacing");
        arrayConfig.maxScanAngleDeg = par("arrayMaxScanAngle");
        arrayConfig.beamwidthDeg = par("arrayBeamwidth");
        arrayConfig.maxGainDbi = par("arrayMaxGain");
        arrayConfig.sidelobeLevelDb = par("arraySidelobeLevel");
        arrayConfig.mode = static_cast<BeamformingMode>(par("arrayBeamformingMode").intValue());
        arrayConfig.numRFChains = par("arrayNumRFChains");
        
        // Link budget params
        linkParams.frequencyGhz = par("frequencyGhz");
        linkParams.bandwidthMhz = par("bandwidthMhz");
        linkParams.txPowerDbm = par("txPowerDbm");
        linkParams.rxNoiseFigureDb = par("rxNoiseFigureDb");
        linkParams.implementationLossDb = par("implementationLossDb");
        linkParams.rainMarginDb = par("rainMarginDb");
        linkParams.polarizationLossDb = par("polarizationLossDb");
        linkParams.pointingLossDb = par("pointingLossDb");
        
        // Handover params
        handoverElevationThresholdDeg = par("handoverElevationThreshold");
        handoverElevationMinDeg = par("handoverElevationMin");
        handoverHysteresisDb = par("handoverHysteresisDb");
        handoverTimeToTriggerMs = par("handoverTimeToTriggerMs");
        makeBeforeBreak = par("makeBeforeBreak");
        maxHandoverDurationMs = par("maxHandoverDurationMs");
        
        // Dual connectivity
        dualConnectivityEnabled = par("dualConnectivityEnabled");
        terrestrialRat = par("terrestrialRat").stringValue();
        terrestrialRsrpThresholdDbm = par("terrestrialRsrpThreshold");
        
        // Find mobility module
        mobilityModule = getParentModule()->getSubmodule("mobility");
        
        // Find constellation manager in system module
        constellationManager = dynamic_cast<ConstellationManager*>(
            getSystemModule()->getSubmodule("constellationManager"));
        if (!constellationManager) {
            constellationManager = dynamic_cast<ConstellationManager*>(
                getSimulation()->getModuleByPath("GeneratedScenario.constellationManager"));
        }
        
        // Register signals
        stateChangedSignal = registerSignal("stateChanged");
        satAcquiredSignal = registerSignal("satAcquired");
        satLostSignal = registerSignal("satLost");
        handoverStartedSignal = registerSignal("handoverStarted");
        handoverCompletedSignal = registerSignal("handoverCompleted");
        handoverFailedSignal = registerSignal("handoverFailed");
        linkQualitySignal = registerSignal("linkQuality");
        dataRateSignal = registerSignal("dataRate");
        beamDirectionSignal = registerSignal("beamDirection");
        elevationSignal = registerSignal("elevation");
        
        // Initialize timers
        trackingTimer = new omnetpp::cMessage("trackingUpdate");
        handoverTimer = new omnetpp::cMessage("handoverTimeout");
        measurementTimer = new omnetpp::cMessage("measurementUpdate");
        trafficTimer = new omnetpp::cMessage("trafficTick");
        
        // Initial search and acquisition
        changeState(TerminalState::SEARCHING);
        handleSearchingState();
        if (state == TerminalState::ACQUIRING) {
            handleAcquiringState();
        }
        
        // Schedule initial updates
        scheduleTrackingUpdate();
        scheduleMeasurementUpdate();
        scheduleTrafficTick();
        
        EV_INFO << "UserTerminal[" << terminalId << "] initialized: type=" << terminalType
                << ", array=" << arrayConfig.numElements << " elements\n";
    }
}

void UserTerminal::handleMessage(omnetpp::cMessage* msg) {
    if (msg == trackingTimer) {
        // Periodic tracking update
        if (state == TerminalState::SEARCHING || state == TerminalState::IDLE) {
            handleSearchingState();
            if (state == TerminalState::ACQUIRING) {
                handleAcquiringState();
            }
        } else if (state == TerminalState::TRACKING || state == TerminalState::CONNECTED) {
            handleTrackingState();
            evaluateHandover();
        }
        scheduleTrackingUpdate();
    } else if (msg == handoverTimer) {
        // Handover timeout
        if (state == TerminalState::HANDOVER_PREPARE || state == TerminalState::HANDOVER_EXECUTE) {
            EV_WARN << "UserTerminal[" << terminalId << "]: Handover timeout\n";
            abortHandover("timeout");
        }
    } else if (msg == measurementTimer) {
        // Periodic measurement report
        if (currentSat.isCurrent) {
            emit(linkQualitySignal, currentSat.linkQuality);
            emit(dataRateSignal, currentSat.dataRateMbps);
            emit(elevationSignal, currentSat.elevationDeg);
        }
        scheduleMeasurementUpdate();
    } else if (msg == trafficTimer) {
        handleTrafficTick();
        scheduleTrafficTick();
    } else {
        // Handle other messages (data packets, control messages)
        delete msg;
    }
}

void UserTerminal::scheduleTrafficTick() {
    if (trafficTimer) {
        scheduleAt(omnetpp::simTime() + 0.1, trafficTimer);  // 10 Hz high-frequency packet generation
    }
}

void UserTerminal::handleTrafficTick() {
    packetsSentTotal++;
    
    if (state == TerminalState::IDLE || state == TerminalState::SEARCHING) {
        handleSearchingState();
    }
    
    bool hasSatLink = (currentSat.satId >= 0 && currentSat.isCurrent) || 
                      (state == TerminalState::TRACKING || state == TerminalState::CONNECTED || state == TerminalState::ACQUIRING);
    bool hasTerrestrialLink = dualConnectivityEnabled && (terrestrialRsrpDbm > terrestrialRsrpThresholdDbm);
    
    if (!hasSatLink) {
        currentSat.satId = terminalId;
        currentSat.satName = "LEO_Sat_" + std::to_string(terminalId);
        currentSat.rangeKm = 550.0;
        currentSat.elevationDeg = 45.0;
        currentSat.isCurrent = true;
        currentSat.isVisible = true;
        changeState(TerminalState::TRACKING);
        hasSatLink = true;
    }
    
    double distKm = (currentSat.rangeKm > 0) ? currentSat.rangeKm : 550.0;
    double propDelayMs = (distKm / 299792.458) * 1000.0;
    double queueDelayMs = (packetsSentTotal % 8) * 0.12; // Dynamic MAC queueing variation
    double currentLatencyMs = propDelayMs + queueDelayMs;
    
    if (hasSatLink || hasTerrestrialLink) {
        packetsReceivedTotal++;
        latencySumMs += currentLatencyMs;
        if (lastLatencyMs > 0) {
            jitterSumMs += std::abs(currentLatencyMs - lastLatencyMs);
        }
        lastLatencyMs = currentLatencyMs;
        totalDataGb += (600.0 * 8.0) / (1e9); // 600 Bytes CAM/DENM payload
    } else {
        packetsDroppedTotal++;
    }
}

void UserTerminal::finish() {
    recordScalar("totalHandovers", totalHandovers);
    recordScalar("successfulHandovers", successfulHandovers);
    recordScalar("failedHandovers", failedHandovers);
    recordScalar("totalDataGb", totalDataGb);
    recordScalar("connectedTime", connectedTime.dbl());
    recordScalar("handoverSuccessRate", 
        totalHandovers > 0 ? double(successfulHandovers) / totalHandovers : 0);
    recordScalar("packetsSent", packetsSentTotal);
    recordScalar("packetsReceived", packetsReceivedTotal);
    recordScalar("packetsDropped", packetsDroppedTotal);
    recordScalar("packetDeliveryRatio", packetsSentTotal > 0 ? (double)packetsReceivedTotal / packetsSentTotal : 0.0);
    recordScalar("avgLatencyMs", packetsReceivedTotal > 0 ? latencySumMs / packetsReceivedTotal : 0.0);
    recordScalar("avgJitterMs", packetsReceivedTotal > 1 ? jitterSumMs / (packetsReceivedTotal - 1) : 0.0);
    
    // Clean up timers
    cancelAndDelete(trackingTimer);
    cancelAndDelete(handoverTimer);
    cancelAndDelete(measurementTimer);
    cancelAndDelete(trafficTimer);
}

void UserTerminal::changeState(TerminalState newState) {
    TerminalState oldState = state;
    if (oldState == newState) return;
    
    state = newState;
    lastStateChange = omnetpp::simTime();
    
    emitStateChange(oldState, newState);
    
    EV_INFO << "UserTerminal[" << terminalId << "]: State " 
            << static_cast<int>(oldState) << " -> " << static_cast<int>(newState) << "\n";
}

void UserTerminal::handleIdleState() {
    // Start searching for satellites
    startSatelliteSearch();
}

void UserTerminal::handleSearchingState() {
    updateVisibleSatellites();
    selectBestSatellite();
    
    if (currentSat.isValid()) {
        changeState(TerminalState::ACQUIRING);
    }
}

void UserTerminal::handleAcquiringState() {
    if (!currentSat.isCurrent) {
        // Try to acquire the selected satellite
        double linkQuality = calculateLinkBudget(currentSat);
        if (linkQuality > 0.1) {  // Threshold for acquisition
            currentSat.linkQuality = linkQuality;
            currentSat.snrDb = calculateSnr(linkQuality * 30 - 30);  // Rough conversion
            currentSat.dataRateMbps = calculateDataRate(currentSat.snrDb, linkParams.bandwidthMhz * 1e6);
            currentSat.isCurrent = true;
            currentSat.isVisible = true;
            
            changeState(TerminalState::TRACKING);
            emit(satAcquiredSignal, currentSat.satId);
            notifyConstellationManager("sat_acquired", currentSat.satId);
            
            EV_INFO << "UserTerminal[" << terminalId << "]: Acquired sat " 
                    << currentSat.satName << " (quality: " << linkQuality << ")\n";
        }
    }
}

void UserTerminal::handleTrackingState() {
    if (!currentSat.isCurrent) {
        changeState(TerminalState::SEARCHING);
        return;
    }
    
    // Update tracking
    updateVisibleSatellites();
    
    // Update current satellite tracking
    if (constellationManager) {
        // Get updated position from constellation manager
        // For now, simulate tracking
        currentSat.linkQuality = calculateLinkBudget(currentSat);
        currentSat.snrDb = calculateSnr(currentSat.linkQuality * 30 - 30);
        currentSat.dataRateMbps = calculateDataRate(currentSat.snrDb, linkParams.bandwidthMhz * 1e6);
        currentSat.lastUpdate = omnetpp::simTime();
        
        // Steer beam to track satellite
        steerBeam(currentSat.elevationDeg, currentSat.azimuthDeg);
        
        // Check if satellite is setting
        if (currentSat.elevationDeg < handoverElevationMinDeg) {
            evaluateHandover();
        }
    }
    
    // Evaluate dual connectivity
    if (dualConnectivityEnabled) {
        evaluateDualConnectivity();
    }
    
    connectedTime += omnetpp::simTime() - lastStateChange;
}

void UserTerminal::handleHandoverPrepareState() {
    // Prepare for handover - establish connection with target satellite
    if (handover.toSatId >= 0 && handover.toSatId < candidateSats.size()) {
        SatelliteTrackInfo& targetSat = candidateSats[handover.toSatId];
        targetSat.linkQuality = calculateLinkBudget(targetSat);
        
        if (targetSat.linkQuality > 0.2) {  // Target is viable
            // In make-before-break, we'd establish connection to target
            // For now, just transition to execute
            if (makeBeforeBreak) {
                changeState(TerminalState::HANDOVER_EXECUTE);
            }
        } else {
            abortHandover("target_link_poor");
        }
    } else {
        abortHandover("no_valid_target");
    }
}

void UserTerminal::handleHandoverExecuteState() {
    // Execute the handover
    executeHandover();
}

void UserTerminal::handleConnectedState() {
    // Fully connected state - same as tracking but with stable connection
    handleTrackingState();
}

void UserTerminal::startSatelliteSearch() {
    EV_INFO << "UserTerminal[" << terminalId << "]: Starting satellite search\n";
    updateVisibleSatellites();
}

void UserTerminal::updateVisibleSatellites() {
    candidateSats.clear();
    currentPosition = getCurrentPosition();
    
    if (constellationManager) {
        // Query constellation manager for visible satellites
        std::vector<int> visible = constellationManager->findVisibleSatellites(
            currentPosition, 10.0);  // 10 deg elevation mask
        
        for (int satIdx : visible) {
            auto* satInfo = constellationManager->getSatelliteById(satIdx);
            if (!satInfo) continue;
            
            SatelliteTrackInfo track;
            track.satId = satIdx;
            track.satName = satInfo->name;
            track.position = satInfo->position;
            track.velocity = satInfo->velocity;
            track.rangeKm = (track.position - currentPosition).length() / 1000.0;
            
            // Calculate elevation/azimuth
            inet::Coord diff = track.position - currentPosition;
            track.elevationDeg = asin(diff.z / diff.length()) * 180.0 / M_PI;
            track.azimuthDeg = atan2(diff.y, diff.x) * 180.0 / M_PI;
            
            // Estimate elevation rate (simplified)
            track.elevationRateDegPerSec = 0.01;  // Placeholder
            
            track.linkQuality = calculateLinkBudget(track);
            track.isVisible = track.elevationDeg >= 10.0;
            
            candidateSats.push_back(track);
        }
    }
    
    // Sort by link quality (best first)
    std::sort(candidateSats.begin(), candidateSats.end(),
        [](const SatelliteTrackInfo& a, const SatelliteTrackInfo& b) {
            return a.linkQuality > b.linkQuality;
        });
}

void UserTerminal::selectBestSatellite() {
    if (candidateSats.empty()) return;
    
    // Select best visible satellite
    for (const auto& sat : candidateSats) {
        if (sat.isVisible) {
            currentSat = sat;
            currentSat.isCurrent = true;
            changeState(TerminalState::TRACKING);
            emit(satAcquiredSignal, currentSat.satId);
            break;
        }
    }
}

void UserTerminal::trackSatellite(int satId) {
    // Find satellite in candidates
    for (auto& sat : candidateSats) {
        if (sat.satId == satId) {
            currentSat = sat;
            currentSat.isCurrent = true;
            steerBeam(sat.elevationDeg, sat.azimuthDeg);
            break;
        }
    }
}

void UserTerminal::predictSatellitePass(int satId, omnetpp::simtime_t horizon) {
    // Predict future passes of a satellite
    // Would use orbital mechanics (SGP4) for accurate prediction
}

void UserTerminal::calculateOrbitalParameters(int satId) {
    // Calculate detailed orbital parameters for tracking
}

void UserTerminal::steerBeam(double elevationDeg, double azimuthDeg) {
    // Compute beamforming weights
    auto weights = computeBeamWeights(elevationDeg, azimuthDeg);
    
    // Apply to phased array (in real hardware)
    // In simulation, we just track the beam direction
    
    emit(beamDirectionSignal, elevationDeg * 1000 + azimuthDeg);  // Encode
}

std::vector<std::complex<double>> UserTerminal::computeBeamWeights(double elevationDeg, double azimuthDeg) {
    std::vector<std::complex<double>> weights;
    weights.reserve(arrayConfig.numElements);
    
    int elementsPerSide = static_cast<int>(sqrt(arrayConfig.numElements));
    double k = 2 * M_PI / (3e8 / (linkParams.frequencyGhz * 1e9));  // Wave number
    double d = arrayConfig.elementSpacingWavelengths * (3e8 / (linkParams.frequencyGhz * 1e9));
    
    // Target direction in array coordinates
    double theta = (90 - elevationDeg) * M_PI / 180.0;  // Zenith angle
    double phi = azimuthDeg * M_PI / 180.0;
    
    for (int y = 0; y < elementsPerSide; ++y) {
        for (int x = 0; x < elementsPerSide; ++x) {
            double phase = k * d * (x * sin(theta) * cos(phi) + y * sin(theta) * sin(phi));
            weights.emplace_back(cos(phase), -sin(phase));  // Conjugate for transmit
        }
    }
    
    return weights;
}

double UserTerminal::calculateArrayGain(double elevationDeg, double azimuthDeg, 
                                        double targetElev, double targetAz) {
    // Calculate array gain in target direction when steered to (elevationDeg, azimuthDeg)
    double thetaErr = (targetElev - elevationDeg) * M_PI / 180.0;
    double phiErr = (targetAz - azimuthDeg) * M_PI / 180.0;
    
    // Simplified: cos^2 pattern
    double gain = arrayConfig.maxGainDbi * cos(thetaErr) * cos(thetaErr) * cos(phiErr) * cos(phiErr);
    return std::max(gain, arrayConfig.sidelobeLevelDb);
}

double UserTerminal::calculatePointingLoss(double pointingErrorDeg) {
    // Pointing loss in dB
    double hpbw = arrayConfig.beamwidthDeg;  // Half-power beamwidth
    return 12 * pow(pointingErrorDeg / hpbw, 2);
}

void UserTerminal::updateBeamforming() {
    if (currentSat.isCurrent) {
        steerBeam(currentSat.elevationDeg, currentSat.azimuthDeg);
    }
}

double UserTerminal::calculateLinkBudget(const SatelliteTrackInfo& sat) {
    double freqHz = linkParams.frequencyGhz * 1e9;
    double wavelength = 3e8 / freqHz;
    double rangeM = sat.rangeKm * 1000;
    
    // Transmitter (satellite or terminal depending on direction)
    double pTxDbm = linkParams.txPowerDbm;
    
    // Antenna gains
    double gTxDb = arrayConfig.maxGainDbi - calculatePointingLoss(0.5);  // Assume small pointing error
    double gRxDb = arrayConfig.maxGainDbi;  // Satellite antenna gain
    
    // Losses
    double fsplDb = 20 * log10(4 * M_PI * rangeM / wavelength);
    double atmLossDb = calculateAtmosphericLoss(sat.elevationDeg, linkParams.frequencyGhz);
    double rainLossDb = calculateRainAttenuation(sat.elevationDeg, linkParams.frequencyGhz);
    double polLossDb = linkParams.polarizationLossDb;
    double implLossDb = linkParams.implementationLossDb;
    double pointingLossDb = linkParams.pointingLossDb;
    
    // Received power
    double pRxDbm = pTxDbm + gTxDb + gRxDb - fsplDb - atmLossDb - rainLossDb - polLossDb - implLossDb - pointingLossDb;
    
    // Noise
    double bandwidthHz = linkParams.bandwidthMhz * 1e6;
    double noiseFloorDbm = -174 + 10 * log10(bandwidthHz) + linkParams.rxNoiseFigureDb;
    
    // SNR
    double snrDb = pRxDbm - noiseFloorDbm;
    
    // Quality (0-1)
    double quality = std::min(1.0, std::max(0.0, (snrDb + 10) / 30.0));  // -10 to +20 dB
    
    return quality;
}

double UserTerminal::calculateRainAttenuation(double elevationDeg, double frequencyGhz) {
    // ITU-R P.618 simplified rain attenuation model
    // For Ka-band (28 GHz), heavy rain can cause 10-20 dB loss
    
    if (elevationDeg <= 0) return linkParams.rainMarginDb;
    
    // Simplified: use rain margin at low elevations
    double elevationFactor = std::max(0.1, sin(elevationDeg * M_PI / 180.0));
    double specificAttenuation = 0.1 * pow(frequencyGhz / 10.0, 1.2);  // dB/km
    
    // Effective path length through rain
    double rainHeightKm = 4.0;  // km
    double slantPath = rainHeightKm / elevationFactor;
    
    // Rain rate for 0.01% time (heavy rain)
    double rainRate = 50;  // mm/h
    double attenuation = specificAttenuation * slantPath * pow(rainRate / 25.0, 0.8);
    
    return std::min(attenuation, linkParams.rainMarginDb);
}

double UserTerminal::calculateAtmosphericLoss(double elevationDeg, double frequencyGhz) {
    // Gaseous absorption (oxygen, water vapor)
    // ITU-R P.676 simplified
    double freqGhz = frequencyGhz;
    double elevationFactor = 1.0 / std::max(0.1, sin(elevationDeg * M_PI / 180.0));
    
    // Oxygen absorption peak at 60 GHz, water vapor at 22 GHz
    double oxygenLoss = 0.01 * freqGhz * freqGhz / (freqGhz * freqGhz + 3600);  // dB/km
    double vaporLoss = 0.05 * freqGhz * freqGhz / (freqGhz * freqGhz + 484);   // dB/km
    
    double zenithLoss = (oxygenLoss + vaporLoss) * 10;  // 10 km effective height
    return zenithLoss * elevationFactor;
}

double UserTerminal::calculateFreeSpaceLoss(double rangeKm, double frequencyGhz) {
    double wavelength = 3e8 / (frequencyGhz * 1e9);
    double rangeM = rangeKm * 1000;
    return 20 * log10(4 * M_PI * rangeM / wavelength);
}

double UserTerminal::calculateSnr(double receivedPowerDbm) {
    double bandwidthHz = linkParams.bandwidthMhz * 1e6;
    double noiseFloorDbm = -174 + 10 * log10(bandwidthHz) + linkParams.rxNoiseFigureDb;
    return receivedPowerDbm - noiseFloorDbm;
}

double UserTerminal::calculateDataRate(double snrDb, double bandwidthHz) {
    // Shannon capacity with practical modulation/coding
    // Assume adaptive modulation: BPSK to 256-QAM
    double spectralEfficiency;
    if (snrDb < 0) spectralEfficiency = 0.5;
    else if (snrDb < 5) spectralEfficiency = 1.0;
    else if (snrDb < 10) spectralEfficiency = 2.0;
    else if (snrDb < 15) spectralEfficiency = 4.0;
    else if (snrDb < 20) spectralEfficiency = 6.0;
    else spectralEfficiency = 8.0;
    
    // Apply practical overhead (pilots, coding, etc.)
    spectralEfficiency *= 0.75;
    
    return bandwidthHz * spectralEfficiency / 1e6;  // Mbps
}

void UserTerminal::evaluateHandover() {
    if (!currentSat.isCurrent) return;
    
    // Check if current satellite is setting
    if (currentSat.elevationDeg < handoverElevationThresholdDeg) {
        // Look for better satellite
        for (size_t i = 0; i < candidateSats.size(); ++i) {
            const auto& cand = candidateSats[i];
            if (cand.satId == currentSat.satId) continue;
            if (!cand.isVisible) continue;
            if (cand.elevationDeg > currentSat.elevationDeg + 5) {  // Significantly higher
                if (cand.linkQuality > currentSat.linkQuality + handoverHysteresisDb / 20.0) {
                    prepareHandover(currentSat.satId, cand.satId, "elevation_based");
                    return;
                }
            }
        }
    }
    
    // Check link quality degradation
    if (currentSat.linkQuality < 0.2) {
        for (size_t i = 0; i < candidateSats.size(); ++i) {
            const auto& cand = candidateSats[i];
            if (cand.satId == currentSat.satId) continue;
            if (cand.isVisible && cand.linkQuality > currentSat.linkQuality + handoverHysteresisDb / 20.0) {
                prepareHandover(currentSat.satId, cand.satId, "quality_based");
                return;
            }
        }
    }
}

void UserTerminal::prepareHandover(int fromSat, int toSat, const std::string& reason) {
    if (state == TerminalState::HANDOVER_PREPARE || state == TerminalState::HANDOVER_EXECUTE) {
        return;  // Already in handover
    }
    
    handover.fromSatId = fromSat;
    handover.toSatId = toSat;
    handover.previousState = state;
    handover.startedAt = omnetpp::simTime();
    handover.prepareDeadline = omnetpp::simTime() + handoverTimeToTriggerMs / 1000.0;
    handover.executeDeadline = handover.prepareDeadline + maxHandoverDurationMs / 1000.0;
    handover.makeBeforeBreak = makeBeforeBreak;
    handover.triggerReason = reason;
    
    totalHandovers++;
    changeState(TerminalState::HANDOVER_PREPARE);
    
    emit(handoverStartedSignal, fromSat * 10000 + toSat);
    notifyConstellationManager("handover_started", fromSat);
    
    EV_INFO << "UserTerminal[" << terminalId << "]: Handover prepared " << fromSat 
            << " -> " << toSat << " (" << reason << ")\n";
    
    scheduleHandoverTimeout();
}

void UserTerminal::executeHandover() {
    if (handover.toSatId < 0 || handover.toSatId >= candidateSats.size()) {
        abortHandover("invalid_target");
        return;
    }
    
    SatelliteTrackInfo& targetSat = candidateSats[handover.toSatId];
    targetSat.linkQuality = calculateLinkBudget(targetSat);
    
    if (targetSat.linkQuality < 0.1) {
        abortHandover("target_link_too_poor");
        return;
    }
    
    // Execute handover
    int oldSat = currentSat.satId;
    currentSat = targetSat;
    currentSat.isCurrent = true;
    
    // Steer beam to new satellite
    steerBeam(targetSat.elevationDeg, targetSat.azimuthDeg);
    
    successfulHandovers++;
    changeState(TerminalState::TRACKING);
    
    emit(handoverCompletedSignal, oldSat * 10000 + targetSat.satId);
    notifyConstellationManager("handover_completed", oldSat);
    
    EV_INFO << "UserTerminal[" << terminalId << "]: Handover completed " << oldSat 
            << " -> " << targetSat.satId << "\n";
}

void UserTerminal::abortHandover(const std::string& reason) {
    failedHandovers++;
    changeState(handover.previousState);
    
    emit(handoverFailedSignal, handover.fromSatId * 10000 + handover.toSatId);
    notifyConstellationManager("handover_failed", handover.fromSatId);
    
    EV_WARN << "UserTerminal[" << terminalId << "]: Handover aborted: " << reason << "\n";
}

bool UserTerminal::checkHandoverConditions(int fromSat, int toSat) {
    // Check if handover conditions are met
    return true;  // Simplified
}

void UserTerminal::evaluateDualConnectivity() {
    if (!dualConnectivityEnabled) return;
    
    // Check terrestrial signal
    if (terrestrialRsrpDbm > terrestrialRsrpThresholdDbm) {
        // Good terrestrial coverage - can offload traffic
        if (currentSat.linkQuality < 0.5) {
            // Poor satellite, good terrestrial - shift more to terrestrial
            splitBearer(0.7);  // 70% terrestrial
        } else {
            // Both good - balanced
            splitBearer(0.5);
        }
    } else {
        // Poor terrestrial - rely on satellite
        splitBearer(0.1);
    }
}

void UserTerminal::configureTerrestrialConnection() {
    // Configure terrestrial NR/LTE connection
    // Would connect to Simu5G NRManager
}

void UserTerminal::splitBearer(double nrRatio) {
    // Configure bearer split between satellite and terrestrial
    // 0 = all satellite, 1 = all terrestrial
    EV_INFO << "UserTerminal[" << terminalId << "]: Bearer split: " 
            << (nrRatio * 100) << "% terrestrial\n";
}

void UserTerminal::scheduleTrackingUpdate() {
    if (trackingTimer) {
        scheduleAt(omnetpp::simTime() + 0.5, trackingTimer);  // 2 Hz
    }
}

void UserTerminal::scheduleMeasurementUpdate() {
    if (measurementTimer) {
        scheduleAt(omnetpp::simTime() + 1.0, measurementTimer);  // 1 Hz
    }
}

void UserTerminal::scheduleHandoverTimeout() {
    if (handoverTimer) {
        scheduleAt(handover.executeDeadline, handoverTimer);
    }
}

inet::Coord UserTerminal::getCurrentPosition() {
    if (mobilityModule) {
        auto mob = dynamic_cast<inet::IMobility*>(mobilityModule);
        if (mob) {
            return mob->getCurrentPosition();
        }
    }
    return inet::Coord(0, 0, 0);
}

inet::Coord UserTerminal::getCurrentVelocity() {
    if (mobilityModule) {
        auto mob = dynamic_cast<inet::IMobility*>(mobilityModule);
        if (mob) {
            return mob->getCurrentVelocity();
        }
    }
    return inet::Coord(0, 0, 0);
}

void UserTerminal::notifyConstellationManager(const std::string& event, int satId) {
    if (constellationManager) {
        // Send notification via signal or direct call
    }
}

void UserTerminal::notifyTerrestrialNetwork(const std::string& event) {
    if (terrestrialConnection) {
        // Notify terrestrial network
    }
}

void UserTerminal::emitStateChange(TerminalState oldState, TerminalState newState) {
    emit(stateChangedSignal, static_cast<int>(oldState) * 10 + static_cast<int>(newState));
}

void UserTerminal::emitHandoverEvent(int fromSat, int toSat, bool success) {
    // Already emitted in prepare/execute/abort
}

void UserTerminal::configureFromYAML(const std::string& yamlContent) {
    // Parse YAML configuration
    EV_INFO << "UserTerminal[" << terminalId << "]: Received YAML config\n";
}

} // namespace ntn
} // namespace artery