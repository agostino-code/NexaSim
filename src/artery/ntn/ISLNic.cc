#include "artery/ntn/ISLNic.h"
#include <omnetpp.h>
#include <cmath>
#include <algorithm>

namespace artery {
namespace ntn {

Define_Module(ISLNic);

void ISLNic::initialize(int stage) {
    if (stage == 0) {
        // Read parameters
        params.type = static_cast<LinkType>(par("linkType").longValue());
        params.wavelengthNm = par("wavelengthNm");
        params.frequencyGhz = par("frequencyGhz");
        params.txPowerDbm = par("txPowerDbm");
        params.rxSensitivityDbm = par("rxSensitivityDbm");
        params.txApertureCm = par("txApertureCm");
        params.rxApertureCm = par("rxApertureCm");
        params.pointingAccuracyDeg = par("pointingAccuracyDeg");
        params.acquisitionTimeMs = par("acquisitionTimeMs");
        params.maxRangeKm = par("maxRangeKm");
        params.dataRateGbps = par("dataRateGbps");
        params.beamDivergenceUrad = par("beamDivergenceUrad");
        
        portIndex = par("portIndex");
        maxPorts = par("maxPorts");
        
        // Find mobility module
        mobilityModule = getParentModule()->getSubmodule("mobility");
        if (!mobilityModule) {
            EV_WARN << "ISLNic: No mobility module found in parent\n";
        }
        
        // Find constellation manager
        constellationManager = getSimulation()->getModuleByPath("constellationManager");
        if (!constellationManager) {
            EV_WARN << "ISLNic: ConstellationManager not found\n";
        }
        
        // Register signals
        linkEstablishedSignal = registerSignal("linkEstablished");
        linkLostSignal = registerSignal("linkLost");
        linkQualitySignal = registerSignal("linkQuality");
        acquisitionTimeSignal = registerSignal("acquisitionTime");
        pointingErrorSignal = registerSignal("pointingError");
        dataRateSignal = registerSignal("dataRate");
        
        EV_INFO << "ISLNic[" << portIndex << "] initialized: type=" 
                << (params.type == LinkType::LASER ? "laser" : "rf")
                << ", maxRange=" << params.maxRangeKm << "km\n";
    }
}

void ISLNic::handleMessage(omnetpp::cMessage* msg) {
    // Handle acquisition/tracking timers
    for (auto& [satId, linkInfo] : links) {
        if (msg == linkInfo.acquisitionTimer) {
            handleAcquisitionTimer(satId);
            return;
        }
        if (msg == linkInfo.trackingTimer) {
            handleTrackingTimer(satId);
            return;
        }
    }
    
    // Handle incoming ISL messages
    // In a real implementation, this would come from the radio medium
    handleRemoteMessage(msg, -1);
    
    delete msg;
}

void ISLNic::finish() {
    recordScalar("totalLinksEstablished", totalLinksEstablished);
    recordScalar("totalLinksLost", totalLinksLost);
    recordScalar("totalDataTransmittedGb", totalDataTransmittedGb);
    
    // Clean up timers
    for (auto& [satId, linkInfo] : links) {
        if (linkInfo.acquisitionTimer) {
            cancelAndDelete(linkInfo.acquisitionTimer);
        }
        if (linkInfo.trackingTimer) {
            cancelAndDelete(linkInfo.trackingTimer);
        }
    }
}

void ISLNic::initiateAcquisition(int remoteSatId, const inet::Coord& remotePos) {
    if (links.find(remoteSatId) != links.end()) {
        return;  // Already exists
    }
    
    LinkStateInfo info;
    info.remoteSatId = remoteSatId;
    info.state = LinkState::ACQUIRING;
    info.rangeKm = calculateRange(getOwnPosition(), remotePos);
    calculatePointingAngles(remoteSatId, info.elevationDeg, info.azimuthDeg);
    info.lastUpdate = omnetpp::simTime();
    
    // Create acquisition timer
    info.acquisitionTimer = new omnetpp::cMessage(("acq_" + std::to_string(remoteSatId)).c_str());
    scheduleAt(omnetpp::simTime() + params.acquisitionTimeMs / 1000.0, info.acquisitionTimer);
    
    links[remoteSatId] = info;
    
    EV_INFO << "ISLNic[" << portIndex << "]: Starting acquisition to sat " << remoteSatId 
            << " at range " << info.rangeKm << "km\n";
}

void ISLNic::updateTracking(int remoteSatId) {
    auto it = links.find(remoteSatId);
    if (it == links.end()) return;
    
    LinkStateInfo& info = it->second;
    if (info.state != LinkState::TRACKING && info.state != LinkState::ESTABLISHED) return;
    
    // Update position and pointing
    inet::Coord remotePos = getRemotePosition(remoteSatId);
    info.rangeKm = calculateRange(getOwnPosition(), remotePos);
    calculatePointingAngles(remoteSatId, info.elevationDeg, info.azimuthDeg);
    
    // Simulate pointing error
    double pointingError = params.pointingAccuracyDeg * (uniform(0, 1) - 0.5) * 2;
    handlePointingError(remoteSatId, pointingError);
    
    // Calculate link quality
    info.linkQuality = calculateLinkBudget(remoteSatId, info.rangeKm, info.elevationDeg);
    info.ber = calculateBER(info.linkQuality);
    info.lastUpdate = omnetpp::simTime();
    
    // Emit quality signal
    emit(linkQualitySignal, info.linkQuality);
    emit(pointingErrorSignal, pointingError);
    emit(dataRateSignal, calculateDataRate(info.linkQuality * 30));  // Rough SNR from quality
    
    // Check if link should be lost
    if (info.linkQuality < 0.1 || info.rangeKm > params.maxRangeKm) {
        loseLink(remoteSatId, "link_degraded");
    }
    
    // Schedule next tracking update
    if (info.trackingTimer) {
        cancelEvent(info.trackingTimer);
    } else {
        info.trackingTimer = new omnetpp::cMessage(("track_" + std::to_string(remoteSatId)).c_str());
    }
    scheduleAt(omnetpp::simTime() + 0.1, info.trackingTimer);  // 10 Hz tracking
}

void ISLNic::establishLink(int remoteSatId) {
    auto it = links.find(remoteSatId);
    if (it == links.end()) return;
    
    LinkStateInfo& info = it->second;
    if (info.state == LinkState::ESTABLISHED) return;
    
    info.state = LinkState::ESTABLISHED;
    info.establishedAt = omnetpp::simTime();
    
    // Cancel acquisition timer
    if (info.acquisitionTimer) {
        cancelAndDelete(info.acquisitionTimer);
        info.acquisitionTimer = nullptr;
    }
    
    // Start tracking
    startTracking(remoteSatId);
    
    totalLinksEstablished++;
    emit(linkEstablishedSignal, remoteSatId);
    
    // Notify constellation manager
    notifyConstellationManager(remoteSatId, LinkState::ESTABLISHED);
    
    EV_INFO << "ISLNic[" << portIndex << "]: Link established with sat " << remoteSatId 
            << " (quality: " << info.linkQuality << ")\n";
}

void ISLNic::loseLink(int remoteSatId, const std::string& reason) {
    auto it = links.find(remoteSatId);
    if (it == links.end()) return;
    
    LinkStateInfo& info = it->second;
    if (info.state == LinkState::LOST) return;
    
    info.state = LinkState::LOST;
    
    // Cancel timers
    if (info.acquisitionTimer) {
        cancelAndDelete(info.acquisitionTimer);
        info.acquisitionTimer = nullptr;
    }
    if (info.trackingTimer) {
        cancelAndDelete(info.trackingTimer);
        info.trackingTimer = nullptr;
    }
    
    totalLinksLost++;
    emit(linkLostSignal, remoteSatId);
    
    // Notify constellation manager
    notifyConstellationManager(remoteSatId, LinkState::LOST);
    
    EV_WARN << "ISLNic[" << portIndex << "]: Link lost with sat " << remoteSatId 
            << " (" << reason << ")\n";
    
    // Remove after a delay to allow cleanup
    links.erase(it);
}

void ISLNic::handlePointingError(int remoteSatId, double errorDeg) {
    auto it = links.find(remoteSatId);
    if (it == links.end()) return;
    
    // Pointing error affects link quality
    double pointingLoss = calculatePointingLoss(fabs(errorDeg));
    it->second.linkQuality *= (1.0 - pointingLoss / 30.0);  // Simplified
    
    emit(pointingErrorSignal, errorDeg);
}

void ISLNic::startAcquisition(int remoteSatId) {
    auto it = links.find(remoteSatId);
    if (it == links.end()) return;
    
    it->second.state = LinkState::ACQUIRING;
    // Acquisition logic would go here
    // For simulation, we transition to tracking after acquisition time
}

void ISLNic::startTracking(int remoteSatId) {
    auto it = links.find(remoteSatId);
    if (it == links.end()) return;
    
    it->second.state = LinkState::TRACKING;
    
    // Start tracking timer
    if (it->second.trackingTimer) {
        cancelEvent(it->second.trackingTimer);
    } else {
        it->second.trackingTimer = new omnetpp::cMessage(("track_" + std::to_string(remoteSatId)).c_str());
    }
    scheduleAt(omnetpp::simTime() + 0.1, it->second.trackingTimer);
}

double ISLNic::calculatePointingAngles(int remoteSatId, double& elevation, double& azimuth) {
    inet::Coord ownPos = getOwnPosition();
    inet::Coord remotePos = getRemotePosition(remoteSatId);
    
    inet::Coord diff = remotePos - ownPos;
    double range = diff.length();
    
    if (range <= 0) {
        elevation = 90;
        azimuth = 0;
        return 0;
    }
    
    // Simplified: elevation from horizontal plane
    elevation = asin(diff.z / range) * 180.0 / M_PI;
    azimuth = atan2(diff.y, diff.x) * 180.0 / M_PI;
    
    return range / 1000.0;  // Return range in km
}

void ISLNic::handleAcquisitionTimer(int remoteSatId) {
    auto it = links.find(remoteSatId);
    if (it == links.end()) return;
    
    LinkStateInfo& info = it->second;
    info.acquisitionTimer = nullptr;
    
    if (info.state == LinkState::ACQUIRING) {
        // Check if acquisition successful
        double range = info.rangeKm;
        if (range <= params.maxRangeKm) {
            establishLink(remoteSatId);
        } else {
            loseLink(remoteSatId, "out_of_range");
        }
    }
}

void ISLNic::handleTrackingTimer(int remoteSatId) {
    updateTracking(remoteSatId);
}

void ISLNic::handleRemoteMessage(omnetpp::cMessage* msg, int remoteSatId) {
    // Handle incoming data packets from remote satellite
    // In a full implementation, this would process actual data
    if (remoteSatId >= 0) {
        auto it = links.find(remoteSatId);
        if (it != links.end() && it->second.state == LinkState::ESTABLISHED) {
            // Process data packet
            totalDataTransmittedGb += 0.001;  // Placeholder
        }
    }
    delete msg;
}

inet::Coord ISLNic::getOwnPosition() {
    if (mobilityModule) {
        // Try to get position from mobility module
        // This would use the mobility module's API
    }
    return inet::Coord(0, 0, 0);  // Placeholder
}

inet::Coord ISLNic::getRemotePosition(int remoteSatId) {
    if (constellationManager) {
        // Query constellation manager for remote satellite position
        // This would use the ConstellationManager's API
    }
    return inet::Coord(0, 0, 0);  // Placeholder
}

double ISLNic::calculateRange(const inet::Coord& posA, const inet::Coord& posB) {
    return (posA - posB).length() / 1000.0;  // km
}

void ISLNic::notifyConstellationManager(int remoteSatId, LinkState newState) {
    if (constellationManager) {
        // Send notification to constellation manager
        // In practice, use a signal or direct method call
    }
}

double ISLNic::calculateFreeSpaceLoss(double rangeKm, double frequencyHz) {
    double wavelength = 3e8 / frequencyHz;
    double rangeM = rangeKm * 1000;
    return 20 * log10(4 * M_PI * rangeM / wavelength);
}

double ISLNic::calculatePointingLoss(double pointingErrorDeg) {
    // Gaussian beam pointing loss
    // L_pointing = 12 * (theta_error / theta_3dB)^2 dB
    // For laser, theta_3dB ~ lambda / (pi * w0)
    double theta3dB = params.wavelengthNm * 1e-9 / (M_PI * params.txApertureCm * 0.01);
    double theta3dBDeg = theta3dB * 180.0 / M_PI;
    return 12 * pow(pointingErrorDeg / theta3dBDeg, 2);
}

double ISLNic::calculateAtmosphericLoss(double elevationDeg, double frequencyHz) {
    // Simplified atmospheric loss model
    // For space-space links, negligible
    // For space-ground, use ITU-R models
    if (params.type == LinkType::LASER) {
        return 0.0;  // Space-space laser: negligible atmosphere
    }
    
    // RF: oxygen and water vapor absorption
    double freqGhz = frequencyHz / 1e9;
    double secant = 1.0 / sin(elevationDeg * M_PI / 180.0);
    double zenithAttenuation = 0.01 * freqGhz;  // Simplified dB/km
    return zenithAttenuation * secant * 10;  // Approximate path length
}

double ISLNic::calculateLinkBudget(int remoteSatId, double rangeKm, double elevationDeg) {
    double freqHz = (params.type == LinkType::LASER) ? 
        (3e8 / (params.wavelengthNm * 1e-9)) : (params.frequencyGhz * 1e9);
    
    // Transmitter
    double pTxDbm = params.txPowerDbm;
    
    // Antenna gains
    double gTxDb = 10 * log10(M_PI * M_PI * pow(params.txApertureCm * 0.01 / 
        (3e8 / freqHz), 2));  // Approximate
    double gRxDb = gTxDb;  // Same aperture
    
    // Losses
    double fsplDb = calculateFreeSpaceLoss(rangeKm, freqHz);
    double pointingLossDb = calculatePointingLoss(params.pointingAccuracyDeg);
    double atmLossDb = calculateAtmosphericLoss(elevationDeg, freqHz);
    
    // Received power
    double pRxDbm = pTxDbm + gTxDb + gRxDb - fsplDb - pointingLossDb - atmLossDb;
    
    // SNR
    double noiseFloorDbm = params.rxSensitivityDbm;  // Simplified
    double snrDb = pRxDbm - noiseFloorDbm;
    
    // Normalize to 0-1 quality
    double quality = std::min(1.0, std::max(0.0, (snrDb + 20) / 40.0));  // -20 to +20 dB SNR
    
    return quality;
}

double ISLNic::calculateBER(double linkQuality) {
    // Simplified BER from link quality
    // Quality 1.0 -> BER ~1e-12, Quality 0.1 -> BER ~1e-3
    return pow(10, -12 * linkQuality - 3 * (1 - linkQuality));
}

double ISLNic::calculateDataRate(double snrDb) {
    // Shannon capacity approximation
    double bandwidthHz = params.dataRateGbps * 1e9 / 2;  // Assume 2 bps/Hz
    double capacity = bandwidthHz * log2(1 + pow(10, snrDb / 10));
    return std::min(capacity / 1e9, params.dataRateGbps);  // Cap at max data rate
}

void ISLNic::configureLink(const LinkParameters& p) {
    params = p;
}

} // namespace ntn
} // namespace artery