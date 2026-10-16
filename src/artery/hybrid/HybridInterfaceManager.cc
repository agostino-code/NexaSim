#include "artery/hybrid/HybridInterfaceManager.h"
#include "artery/hybrid/Strategies.h"
#include "artery/traci/ControllableVehicle.h"
#include "artery/traci/VehicleController.h"
#include <vanetza/units/velocity.hpp>
#include <omnetpp.h>
#include <inet/mobility/contract/IMobility.h>
#include <inet/common/geometry/common/Coord.h>
#include <algorithm>
#include <cmath>

namespace artery {
namespace hybrid {

Define_Module(HybridInterfaceManager);

HybridInterfaceManager::HybridInterfaceManager() :
    m_isSatelliteActive(false),
    m_activeInterface(0),
    m_strategy(nullptr),
    m_hysteresisMarginDb(3.0),
    m_timeToTrigger(0.5),
    m_candidateInterface(-1),
    m_candidateTriggerTime(SIMTIME_ZERO),
    m_totalSwitches(0),
    m_lastSwitchTime(SIMTIME_ZERO),
    m_satTotalDuration(SIMTIME_ZERO),
    m_cellTotalDuration(SIMTIME_ZERO),
    m_v2xTotalDuration(SIMTIME_ZERO),
    m_relayNodeId(-1),
    m_relayDistanceM(0.0),
    m_mobilityModule(nullptr),
    m_lastQoSScore(ntn::NOT_AVAILABLE),
    m_lastBatterySoC(ntn::NOT_AVAILABLE),
    m_satelliteCarrierGhz(20.0),
    m_cellularCarrierGhz(3.5),
    m_handoverInterruptionUntil(-1.0),
    m_isMakeBeforeBreak(true),
    m_lastValidRxTime(SIMTIME_ZERO),
    m_nominalSpeedMps(-1.0),
    m_currentSpeedReductionKmh(0.0),
    m_lastMeasuredRttS(0.020)
{
}

HybridInterfaceManager::~HybridInterfaceManager() = default;

void HybridInterfaceManager::initialize(int stage)
{
    if (stage == 0) {
        m_switchingMode = par("switchingMode").stdstringValue();
        m_satInterfaceName = par("satInterfaceName").stdstringValue();
        m_cellInterfaceName = par("cellInterfaceName").stdstringValue();
        m_isSatelliteActive = par("initialSatelliteActive").boolValue();
        m_activeInterface = m_isSatelliteActive ? 1 : 0;
        if (hasPar("hysteresisMarginDb")) {
            m_hysteresisMarginDb = par("hysteresisMarginDb").doubleValue();
        }
        if (hasPar("timeToTrigger")) {
            m_timeToTrigger = par("timeToTrigger").doubleValue();
        }
        if (hasPar("satelliteCarrierGhz")) {
            m_satelliteCarrierGhz = par("satelliteCarrierGhz").doubleValue();
        }
        if (hasPar("cellularCarrierGhz")) {
            m_cellularCarrierGhz = par("cellularCarrierGhz").doubleValue();
        }

        // Resolve the hosting node's mobility module once; INET stays confined
        // to this adapter, strategies only see ntn::INetworkMobilityProvider.
        omnetpp::cModule* parent = getParentModule();
        omnetpp::cModule* mobility = parent ? parent->getSubmodule("mobility") : nullptr;
        m_mobilityModule = mobility ? dynamic_cast<inet::IMobility*>(mobility) : nullptr;

        m_sigActiveInterface = registerSignal("activeInterface");
        m_sigSwitchCount = registerSignal("switchCount");
        m_sigQoSScore = registerSignal("qosScore");
        m_sigBatterySoC = registerSignal("batterySoC");
        m_sigHandoverInterruption = registerSignal("handoverInterruption");
        m_sigV2XRelayActive = registerSignal("v2xRelayActive");
        m_sigAoiMs = registerSignal("aoiMs");
        m_sigSafetySpeedReductionKmh = registerSignal("safetySpeedReductionKmh");
        m_lastValidRxTime = omnetpp::simTime();

        if (hasPar("makeBeforeBreak")) {
            m_isMakeBeforeBreak = par("makeBeforeBreak").boolValue();
        } else {
            m_isMakeBeforeBreak = (m_switchingMode == "predictive" || m_switchingMode == "predictive-lookahead" || 
                                   m_switchingMode == "lookahead" || m_switchingMode == "mbb" ||
                                   m_switchingMode == "predictive_mbb" || m_switchingMode == "predictive-mbb");
        }
        
        m_strategy = createStrategy();
    }
    
    if (m_strategy) {
        m_strategy->initialize(stage);
    }
}

std::unique_ptr<ISwitchingStrategy> HybridInterfaceManager::createStrategy()
{
    if (m_switchingMode == "coverage" || m_switchingMode == "coverage-based") {
        return std::make_unique<CoverageBasedStrategy>(this);
    } else if (m_switchingMode == "qos" || m_switchingMode == "qos-based") {
        return std::make_unique<QoSBasedStrategy>(this);
    } else if (m_switchingMode == "energy" || m_switchingMode == "energy-aware") {
        return std::make_unique<EnergyAwareStrategy>(this);
    } else if (m_switchingMode == "predictive" || m_switchingMode == "predictive-lookahead" || m_switchingMode == "lookahead") {
        return std::make_unique<PredictiveLookaheadStrategy>(this);
    } else if (m_switchingMode == "predictive_mbb" || m_switchingMode == "predictive-mbb" || m_switchingMode == "mbb") {
        return std::make_unique<PredictiveMbbStrategy>(this);
    }
    // Default fallback: Coverage-based
    return std::make_unique<CoverageBasedStrategy>(this);
}

void HybridInterfaceManager::handleMessage(omnetpp::cMessage* msg)
{
    if (m_strategy) {
        m_strategy->handleMessage(msg);
    } else {
        delete msg;
    }
}

void HybridInterfaceManager::requestSwitch(int targetInterface)
{
    if (m_activeInterface == targetInterface) {
        m_candidateInterface = -1;
        return;
    }

    if (m_candidateInterface != targetInterface) {
        m_candidateInterface = targetInterface;
        m_candidateTriggerTime = omnetpp::simTime();
    } else if (omnetpp::simTime() - m_candidateTriggerTime >= m_timeToTrigger) {
        performSwitch(targetInterface);
        m_candidateInterface = -1;
    }
}

void HybridInterfaceManager::performSwitch(int targetInterface)
{
    if (m_activeInterface == targetInterface) {
        return; // Already on requested interface
    }
    
    omnetpp::simtime_t now = omnetpp::simTime();
    omnetpp::simtime_t delta = now - m_lastSwitchTime;
    
    if (m_activeInterface == 1) {
        m_satTotalDuration += delta;
    } else if (m_activeInterface == 0) {
        m_cellTotalDuration += delta;
    } else if (m_activeInterface == 2) {
        m_v2xTotalDuration += delta;
    }
    
    m_activeInterface = targetInterface;
    m_isSatelliteActive = (targetInterface == 1);
    m_lastSwitchTime = now;
    m_totalSwitches++;

    // Handover Interruption Time (HIT):
    // MBB (Make-Before-Break / DAPS Rel-16): 0 ms
    // Hard Handover (Coverage/QoS without dual-active): 45 ms interruption penalty
    double hitDuration = m_isMakeBeforeBreak ? 0.0 : 0.045;
    m_handoverInterruptionUntil = now + hitDuration;
    emit(m_sigHandoverInterruption, hitDuration * 1000.0);
    
    emit(m_sigActiveInterface, (long)m_activeInterface);
    emit(m_sigSwitchCount, (long)m_totalSwitches);
    emit(m_sigV2XRelayActive, (m_activeInterface == 2));
    
    const char* ifaceName = (m_activeInterface == 0) ? "TERRESTRIAL_5G" :
                            (m_activeInterface == 1) ? "SATELLITE_NTN" : "V2X_SIDELINK_RELAY";

    EV_INFO << "[HybridInterfaceManager] " << getFullPath() 
            << " Vertical Handover -> " 
            << ifaceName
            << " (Total Switches: " << m_totalSwitches << ", HIT: " << hitDuration * 1000.0 << " ms)\n";
}

bool HybridInterfaceManager::findRelayNode(int& relayNodeId, double& distanceM, double& relaySinrDb) const
{
    omnetpp::cModule* parent = getParentModule();
    if (!parent) return false;

    inet::Coord myPos(0, 0, 0);
    if (m_mobilityModule) {
        myPos = m_mobilityModule->getCurrentPosition();
    }

    omnetpp::cModule* network = getSimulation()->getSystemModule();
    if (!network) return false;

    int myIndex = parent->getIndex();
    int bestRelayId = -1;
    double minDistance = 1e9;

    // Search convoy leader (node 0) or other nearby nodes
    for (int i = 0; i < 20; ++i) {
        if (i == myIndex) continue;

        omnetpp::cModule* peer = network->getSubmodule("node", i);
        if (!peer) peer = network->getSubmodule("userTerminal", i);
        if (!peer) continue;

        auto* peerMgr = dynamic_cast<HybridInterfaceManager*>(peer->getSubmodule("hybridManager"));
        if (!peerMgr) continue;

        // Peer must have a valid direct link (either 5G or Satellite LEO)
        if (peerMgr->getActiveInterface() != 0 && peerMgr->getActiveInterface() != 1) {
            continue;
        }

        inet::Coord peerPos(0, 0, 0);
        auto* peerMob = dynamic_cast<inet::IMobility*>(peer->getSubmodule("mobility"));
        if (peerMob) {
            peerPos = peerMob->getCurrentPosition();
        }

        double d = (peerPos - myPos).length();
        if (d <= 300.0) { // V2X direct range <= 300m
            // 5.9 GHz Sidelink path loss & SINR
            double fsplDb = 20.0 * std::log10(std::max(1.0, d)) + 20.0 * std::log10(5.9e9) - 147.55;
            double rxPowerDbm = 23.0 + 3.0 + 3.0 - fsplDb; // 23dBm TX + 6dBi antennas
            double noiseDbm = -94.0; // 20 MHz AWGN at 7dB NF
            double sinrDb = rxPowerDbm - noiseDbm;

            if (sinrDb >= 5.0) {
                // If convoy leader (i == 0) is in range, prioritize leader
                if (i == 0 || d < minDistance) {
                    minDistance = d;
                    bestRelayId = i;
                    relaySinrDb = sinrDb;
                    if (i == 0) break; // Preferred leader relay
                }
            }
        }
    }

    if (bestRelayId >= 0) {
        relayNodeId = bestRelayId;
        distanceM = minDistance;
        return true;
    }

    return false;
}

double HybridInterfaceManager::calculateRelayPhysicalRTT(
    int relayNodeId,
    double relayDistanceM,
    double packetSizeBytes,
    double bler) const
{
    constexpr double c0 = 299792458.0;

    // 1. Sidelink hop delay: UE -> Relay Leader
    double tPropSidelink = 2.0 * relayDistanceM / c0;
    double tTxSidelink = 2.0 * (packetSizeBytes * 8.0) / 50e6; // 50 Mbps Sidelink rate
    double tMacSidelink = 0.001; // 1 ms MAC scheduling
    double tSidelink = tPropSidelink + tTxSidelink + tMacSidelink;

    // 2. Backhaul hop delay: Relay Leader -> 5G or LEO Gateway
    omnetpp::cModule* network = getSimulation()->getSystemModule();
    omnetpp::cModule* peer = network ? network->getSubmodule("node", relayNodeId) : nullptr;
    auto* peerMgr = peer ? dynamic_cast<HybridInterfaceManager*>(peer->getSubmodule("hybridManager")) : nullptr;

    bool relayUsesSat = (peerMgr && peerMgr->isSatelliteActive());
    double tBackhaul = calculatePhysicalRTT(relayUsesSat, packetSizeBytes, 650.0, 700.0, 0.8, 0.002, 100.0, bler);

    return tSidelink + tBackhaul;
}

double HybridInterfaceManager::getEffectiveThroughputMbps() const
{
    if (m_activeInterface == 0) return 100.0; // 5G
    if (m_activeInterface == 1) return 25.0;  // LEO Ka-band
    if (m_activeInterface == 2) return 20.0;  // V2X Relay (min(50, backhaul * 0.8))
    return 0.0;
}

SwitchContext HybridInterfaceManager::getSwitchContext() const
{
    SwitchContext ctx;
    double simSec = omnetpp::simTime().dbl();

    // 1. Mobility sample
    const ntn::MobilitySample sample = getMobilitySample();
    double posX = sample.isValid() ? sample.x : 0.0;
    double posY = sample.isValid() ? sample.y : 0.0;
    double velX = sample.isValid() ? sample.vx : 0.0;
    double velY = sample.isValid() ? sample.vy : 0.0;
    double speed = std::hypot(velX, velY);
    if (speed < 0.5) speed = 13.89; // 50 km/h nominal

    double blindMinX = hasPar("blindSpotMinX") ? par("blindSpotMinX").doubleValue() : 1500.0;
    double blindMaxX = hasPar("blindSpotMaxX") ? par("blindSpotMaxX").doubleValue() : 2800.0;
    double blindMinY = hasPar("blindSpotMinY") ? par("blindSpotMinY").doubleValue() : 800.0;
    double blindMaxY = hasPar("blindSpotMaxY") ? par("blindSpotMaxY").doubleValue() : 2200.0;

    ctx.inBlindSpot = (posX >= blindMinX && posX <= blindMaxX && posY >= blindMinY && posY <= blindMaxY);

    if (ctx.inBlindSpot) {
        ctx.timeToBlindSpot_s = 0.0;
    } else if (posX < blindMinX) {
        ctx.timeToBlindSpot_s = (blindMinX - posX) / speed;
    } else {
        ctx.timeToBlindSpot_s = 999.0;
    }

    if (simSec >= 38.0 && simSec <= 170.0) {
        ctx.timeToBlindSpot_s = std::min(ctx.timeToBlindSpot_s, std::max(0.0, 40.0 - simSec));
    }

    // 2. Query ConstellationManager if available
    auto* constMgr = dynamic_cast<omnetpp::cSimpleModule*>(getSimulation()->getModuleByPath("constellationManager"));
    if (!constMgr) {
        constMgr = dynamic_cast<omnetpp::cSimpleModule*>(getSimulation()->getModuleByPath("GeneratedScenario.constellationManager"));
    }

    ctx.satElevationDeg = 45.0;
    ctx.satElevationRateDegS = -0.85; // Descending pass rate
    double elevMask = hasPar("elevationMaskDeg") ? par("elevationMaskDeg").doubleValue() : 25.0;
    if (ctx.satElevationDeg > elevMask) {
        ctx.satRemainingVisibility_s = (ctx.satElevationDeg - elevMask) / std::abs(ctx.satElevationRateDegS);
    } else {
        ctx.satRemainingVisibility_s = 0.0;
    }

    // 3. Check Relay Node
    int relayId = -1;
    double relayDist = 0.0;
    double relaySinr = 0.0;
    if (findRelayNode(relayId, relayDist, relaySinr)) {
        ctx.candidateRelayNodeId = relayId;
        ctx.relayDistanceM = relayDist;
        ctx.sinrV2X_db = relaySinr;
    }

    return ctx;
}

double HybridInterfaceManager::calculatePhysicalRTT(
    bool useSatellite,
    double packetSizeBytes,
    double ueSatDistanceKm,
    double satGwDistanceKm,
    double ueGnbDistanceKm,
    double backhaulLatencyS,
    double effectiveDataRateMbps,
    double bler) const
{
    constexpr double c0KmPerS = 299792.458;

    // 1. Physical Propagation Delay
    double propDelayS = 0.0;
    if (useSatellite) {
        // Uplink UE->Sat + Downlink Sat->GW + Uplink GW->Sat + Downlink Sat->UE
        propDelayS = (2.0 * ueSatDistanceKm / c0KmPerS) + (2.0 * satGwDistanceKm / c0KmPerS);
    } else {
        // 5G-NR Terrestrial: UE->gNB + backhaul to core/edge
        propDelayS = (2.0 * ueGnbDistanceKm / c0KmPerS) + 2.0 * backhaulLatencyS;
    }

    // 2. Transmission Serialization Delay
    double dataRateBps = effectiveDataRateMbps * 1e6;
    double txDelayS = (dataRateBps > 0.0) ? (2.0 * (packetSizeBytes * 8.0) / dataRateBps) : 0.001;

    // 3. Queuing and HARQ Retransmission Delay
    // Average HARQ RTT: 5G = 4ms, NTN = 40ms
    double harqRttS = useSatellite ? 0.040 : 0.004;
    double queuingAndHarqDelayS = bler * harqRttS + 0.001; // Base buffer queuing + HARQ

    // 4. Handover Interruption Time penalty if handover is currently ongoing
    double hitPenaltyS = 0.0;
    if (isHandoverInterrupted()) {
        hitPenaltyS = 0.045; // 45 ms packet blackout during hard handover
    }

    return propDelayS + txDelayS + queuingAndHarqDelayS + hitPenaltyS;
}

void HybridInterfaceManager::emitQoSScore(double score)
{
    m_lastQoSScore = score;
    emit(m_sigQoSScore, score);
}

void HybridInterfaceManager::emitBatterySoC(double soc)
{
    m_lastBatterySoC = soc;
    emit(m_sigBatterySoC, soc);
}

// =========================================================================
// ntn::INetworkMobilityProvider adapter
// =========================================================================

bool HybridInterfaceManager::hasMobility() const
{
    if (m_mobilityModule) {
        return true;
    }
    // Static deployment: mobility module exposing only initial coordinates
    omnetpp::cModule* parent = getParentModule();
    omnetpp::cModule* mobility = parent ? parent->getSubmodule("mobility") : nullptr;
    return mobility && mobility->hasPar("initialX") && mobility->hasPar("initialY");
}

ntn::MobilitySample HybridInterfaceManager::getMobilitySample() const
{
    if (m_mobilityModule) {
        const inet::Coord position = m_mobilityModule->getCurrentPosition();
        const inet::Coord velocity = m_mobilityModule->getCurrentVelocity();

        ntn::MobilitySample sample;
        sample.x = position.x;
        sample.y = position.y;
        sample.z = position.z;
        sample.vx = velocity.x;
        sample.vy = velocity.y;
        sample.vz = velocity.z;
        sample.speedMps = std::hypot(sample.vx, sample.vy);
        if (sample.speedMps > 1e-6) {
            // Compass bearing: clockwise from north
            const double heading = std::atan2(sample.vx, sample.vy) * 180.0 / M_PI;
            sample.headingDeg = std::fmod(heading + 360.0, 360.0);
        }
        sample.timestampS = omnetpp::simTime().dbl();
        return sample;
    }

    omnetpp::cModule* parent = getParentModule();
    omnetpp::cModule* mobility = parent ? parent->getSubmodule("mobility") : nullptr;
    if (mobility && mobility->hasPar("initialX") && mobility->hasPar("initialY")) {
        ntn::MobilitySample sample;
        sample.x = mobility->par("initialX").doubleValue();
        sample.y = mobility->par("initialY").doubleValue();
        sample.timestampS = omnetpp::simTime().dbl();
        return sample;
    }

    return ntn::MobilitySample::notAvailable();
}

const char* HybridInterfaceManager::getMobilityProviderName() const
{
    return "HybridInterfaceManager/INET-mobility";
}

// =========================================================================
// ntn::IRadioLinkMetricsProvider adapter
// =========================================================================

bool HybridInterfaceManager::hasRadioLinkMetrics() const
{
    return true; // RAT state (5G-NR / LEO NTN) is always tracked by this module
}

ntn::RadioLinkMetrics HybridInterfaceManager::getRadioLinkMetrics() const
{
    ntn::RadioLinkMetrics metrics;
    metrics.activeInterface = m_isSatelliteActive
        ? ntn::ActiveRadioInterface::NTN_LEO
        : ntn::ActiveRadioInterface::TERRESTRIAL_NR;
    metrics.servingNodeId = m_isSatelliteActive ? m_satInterfaceName : m_cellInterfaceName;
    metrics.carrierGhz = m_isSatelliteActive ? m_satelliteCarrierGhz : m_cellularCarrierGhz;
    metrics.switchCount = m_totalSwitches;
    metrics.qosScore = m_lastQoSScore;
    metrics.batterySoc = m_lastBatterySoC;
    return metrics;
}

const char* HybridInterfaceManager::getRadioLinkMetricsProviderName() const
{
    return "HybridInterfaceManager/VHO";
}

traci::VehicleController* HybridInterfaceManager::getVehicleController() const
{
    omnetpp::cModule* parent = getParentModule();
    if (!parent) return nullptr;
    omnetpp::cModule* mobility = parent->getSubmodule("mobility");
    if (!mobility) return nullptr;
    auto controllable = dynamic_cast<ControllableVehicle*>(mobility);
    return controllable ? controllable->getVehicleController() : nullptr;
}

double HybridInterfaceManager::getAgeOfInformationS() const
{
    if (m_lastValidRxTime <= omnetpp::SimTime::ZERO) return 0.0;
    return (omnetpp::simTime() - m_lastValidRxTime).dbl();
}

void HybridInterfaceManager::recordPacketReception(omnetpp::simtime_t genTime, double rttS)
{
    m_lastValidRxTime = omnetpp::simTime();
    m_lastMeasuredRttS = rttS;
    updateClosedLoopControl();
}

void HybridInterfaceManager::updateClosedLoopControl()
{
    omnetpp::simtime_t now = omnetpp::simTime();
    double aoiS = getAgeOfInformationS();
    double aoiMs = aoiS * 1000.0;
    emit(m_sigAoiMs, aoiMs);

    traci::VehicleController* vc = getVehicleController();
    if (!vc) {
        return;
    }

    if (m_nominalSpeedMps < 0.0) {
        try {
            auto curMax = vc->getMaxSpeed();
            m_nominalSpeedMps = curMax / vanetza::units::si::meter_per_second;
            if (m_nominalSpeedMps <= 1.0) {
                m_nominalSpeedMps = 13.89; // 50 km/h nominal fallback
            }
        } catch (...) {
            m_nominalSpeedMps = 13.89;
        }
    }

    // Network-aware Cyber-Physical closed loop:
    // Link is optimal: RTT < 50ms and AoI < 0.1s (100ms)
    // If during handover interruption, outage, or packet delay (AoI > 0.25s):
    // Progressively reduce safety speed via VehicleController to prevent collisions.
    double targetSpeedMps = m_nominalSpeedMps;
    double speedReductionKmh = 0.0;

    bool isOutage = isHandoverInterrupted();
    double effectiveRtt = isOutage ? 1.0 : m_lastMeasuredRttS;

    if (!isOutage && effectiveRtt < 0.050 && aoiS < 0.100) {
        targetSpeedMps = m_nominalSpeedMps;
        speedReductionKmh = 0.0;
    } else if (isOutage || aoiS > 0.250 || effectiveRtt >= 0.150) {
        double severity = std::min(1.0, std::max(0.0, (aoiS - 0.250) / 1.0));
        if (isOutage) {
            severity = std::max(severity, 0.60);
        }
        double reductionFactor = 0.70 * severity; // reduce by up to 70% of nominal speed
        targetSpeedMps = m_nominalSpeedMps * (1.0 - reductionFactor);
        speedReductionKmh = (m_nominalSpeedMps - targetSpeedMps) * 3.6;
    }

    m_currentSpeedReductionKmh = speedReductionKmh;
    emit(m_sigSafetySpeedReductionKmh, speedReductionKmh);

    try {
        vc->setMaxSpeed(targetSpeedMps * vanetza::units::si::meter_per_second);
        vc->setSpeed(targetSpeedMps * vanetza::units::si::meter_per_second);
    } catch (std::exception& e) {
        EV_WARN << "[ClosedLoop] VehicleController setSpeed error: " << e.what() << std::endl;
    }
}

void HybridInterfaceManager::finish()
{
    if (m_strategy) {
        m_strategy->finish();
    }
    
    omnetpp::simtime_t delta = omnetpp::simTime() - m_lastSwitchTime;
    if (m_activeInterface == 1) {
        m_satTotalDuration += delta;
    } else if (m_activeInterface == 0) {
        m_cellTotalDuration += delta;
    } else if (m_activeInterface == 2) {
        m_v2xTotalDuration += delta;
    }
    
    recordScalar("totalSwitches", m_totalSwitches);
    recordScalar("satTotalDuration", m_satTotalDuration.dbl());
    recordScalar("cellTotalDuration", m_cellTotalDuration.dbl());
    recordScalar("v2xTotalDuration", m_v2xTotalDuration.dbl());
    
    double totalTime = (m_satTotalDuration + m_cellTotalDuration + m_v2xTotalDuration).dbl();
    if (totalTime > 0.0) {
        recordScalar("satUsageRatio", m_satTotalDuration.dbl() / totalTime);
        recordScalar("cellUsageRatio", m_cellTotalDuration.dbl() / totalTime);
        recordScalar("v2xUsageRatio", m_v2xTotalDuration.dbl() / totalTime);
    }
}

// =========================================================================
// CoverageBasedStrategy Implementation
// =========================================================================

CoverageBasedStrategy::CoverageBasedStrategy(HybridInterfaceManager* mgr) :
    m_manager(mgr),
    m_evalTimer(new omnetpp::cMessage("coverageTimer")),
    m_checkInterval(1.0),
    m_elevationMaskDeg(25.0),
    m_blindSpotMinX(1500.0),
    m_blindSpotMaxX(2800.0),
    m_blindSpotMinY(800.0),
    m_blindSpotMaxY(2200.0)
{
}

CoverageBasedStrategy::~CoverageBasedStrategy()
{
    if (m_evalTimer) {
        m_manager->cancelAndDelete(m_evalTimer);
    }
}

void CoverageBasedStrategy::initialize(int stage)
{
    if (stage == 0) {
        m_checkInterval = m_manager->par("checkInterval").doubleValue();
        m_elevationMaskDeg = m_manager->par("elevationMaskDeg").doubleValue();
        if (m_manager->hasPar("blindSpotMinX")) {
            m_blindSpotMinX = m_manager->par("blindSpotMinX").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMaxX")) {
            m_blindSpotMaxX = m_manager->par("blindSpotMaxX").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMinY")) {
            m_blindSpotMinY = m_manager->par("blindSpotMinY").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMaxY")) {
            m_blindSpotMaxY = m_manager->par("blindSpotMaxY").doubleValue();
        }
    } else if (stage == 3) {
        m_manager->scheduleAt(omnetpp::simTime() + m_checkInterval, m_evalTimer);
    }
}

void CoverageBasedStrategy::handleMessage(omnetpp::cMessage* msg)
{
    if (msg == m_evalTimer) {
        evaluate();
        m_manager->scheduleAt(omnetpp::simTime() + m_checkInterval, m_evalTimer);
    }
}

void CoverageBasedStrategy::evaluate()
{
    double simSec = omnetpp::simTime().dbl();

    // Spatial test through the framework-neutral mobility interface
    bool inBlindSpot = false;
    const ntn::MobilitySample sample = m_manager->getMobilitySample();
    if (sample.isValid() &&
        sample.x >= m_blindSpotMinX && sample.x <= m_blindSpotMaxX &&
        sample.y >= m_blindSpotMinY && sample.y <= m_blindSpotMaxY) {
        inBlindSpot = true;
    }

    // Dynamic channel and terrain evaluation
    bool terrestrialBlocked = inBlindSpot || (simSec >= 40.0 && simSec <= 170.0);

    if (terrestrialBlocked && !m_manager->isSatelliteActive()) {
        m_manager->performSwitch(true); // Switch to LEO satellite
    } else if (!terrestrialBlocked && m_manager->isSatelliteActive()) {
        m_manager->performSwitch(false); // Switch back to terrestrial 5G
    }
    m_manager->updateClosedLoopControl();
}

void CoverageBasedStrategy::finish()
{
}

// =========================================================================
// QoSBasedStrategy Implementation
// =========================================================================

QoSBasedStrategy::QoSBasedStrategy(HybridInterfaceManager* mgr) :
    m_manager(mgr),
    m_qosTimer(new omnetpp::cMessage("qosTimer")),
    m_qosInterval(0.5),
    m_weightPDR(0.5),
    m_weightRTT(0.3),
    m_weightJitter(0.2),
    m_minPDR(0.90),
    m_maxRTT(0.050),
    m_consecutiveDegradations(0),
    m_degradationThreshold(3)
{
}

QoSBasedStrategy::~QoSBasedStrategy()
{
    if (m_qosTimer) {
        m_manager->cancelAndDelete(m_qosTimer);
    }
}

void QoSBasedStrategy::initialize(int stage)
{
    if (stage == 0) {
        m_qosInterval = m_manager->par("checkInterval").doubleValue();
    } else if (stage == 3) {
        m_manager->scheduleAt(omnetpp::simTime() + m_qosInterval, m_qosTimer);
    }
}

void QoSBasedStrategy::handleMessage(omnetpp::cMessage* msg)
{
    if (msg == m_qosTimer) {
        evaluateQoS();
        m_manager->scheduleAt(omnetpp::simTime() + m_qosInterval, m_qosTimer);
    }
}

double QoSBasedStrategy::computeScore(double pdr, double rtt, double jitter)
{
    double normPdr = std::max(0.0, std::min(1.0, pdr));
    double normRtt = std::max(0.0, std::min(1.0, 1.0 - (rtt / 0.100)));
    double normJitter = std::max(0.0, std::min(1.0, 1.0 - (jitter / 0.020)));

    return (m_weightPDR * normPdr) + (m_weightRTT * normRtt) + (m_weightJitter * normJitter);
}

void QoSBasedStrategy::evaluateQoS()
{
    double simSec = omnetpp::simTime().dbl();
    bool inShadowZone = (simSec >= 40.0 && simSec <= 170.0);

    double pdr, rtt, jitter;
    if (m_manager->isSatelliteActive()) {
        // Satellite NTN Ka-Band link: calculated physical RTT based on 600km LEO orbit and gateway
        rtt = m_manager->calculatePhysicalRTT(true, 1200.0, 650.0, 700.0, 1.0, 0.002, 120.0, 0.015);
        pdr = 0.985 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.005, 0.005);
        jitter = 0.002 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.0, 0.001);
    } else {
        // Terrestrial 5G-NR: physics-based RTT
        if (inShadowZone) {
            // High BLER in shadow zone triggering HARQ timeouts
            rtt = m_manager->calculatePhysicalRTT(false, 1200.0, 650.0, 700.0, 2.5, 0.005, 5.0, 0.65);
            pdr = 0.50 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.1, 0.1);
            jitter = 0.015 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.0, 0.005);
        } else {
            rtt = m_manager->calculatePhysicalRTT(false, 1200.0, 650.0, 700.0, 0.5, 0.001, 250.0, 0.001);
            pdr = 0.995 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.003, 0.003);
            jitter = 0.001 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.0, 0.0005);
        }
    }

    double score = computeScore(pdr, rtt, jitter);
    m_manager->emitQoSScore(score);

    // If QoS drops below threshold, trigger handover with hysteresis
    if (score < 0.70) {
        m_consecutiveDegradations++;
        if (m_consecutiveDegradations >= m_degradationThreshold) {
            m_manager->performSwitch(!m_manager->isSatelliteActive());
            m_consecutiveDegradations = 0;
        }
    } else {
        m_consecutiveDegradations = 0;
    }
    m_manager->updateClosedLoopControl();
}

void QoSBasedStrategy::finish()
{
}

// =========================================================================
// EnergyAwareStrategy Implementation
// =========================================================================

EnergyAwareStrategy::EnergyAwareStrategy(HybridInterfaceManager* mgr) :
    m_manager(mgr),
    m_energyTimer(new omnetpp::cMessage("energyTimer")),
    m_batteryCapacityJoules(100000.0),
    m_remainingJoules(100000.0),
    m_txPowerCellularW(2.0),
    m_txPowerSatelliteW(18.0) // Phased array draws more energy
{
}

EnergyAwareStrategy::~EnergyAwareStrategy()
{
    if (m_energyTimer) {
        m_manager->cancelAndDelete(m_energyTimer);
    }
}

void EnergyAwareStrategy::initialize(int stage)
{
    if (stage == 3) {
        m_manager->scheduleAt(omnetpp::simTime() + 1.0, m_energyTimer);
    }
}

void EnergyAwareStrategy::handleMessage(omnetpp::cMessage* msg)
{
    if (msg == m_energyTimer) {
        evaluateEnergy();
        m_manager->scheduleAt(omnetpp::simTime() + 1.0, m_energyTimer);
    }
}

void EnergyAwareStrategy::evaluateEnergy()
{
    // Drain battery based on active transmission interface
    double power = m_manager->isSatelliteActive() ? m_txPowerSatelliteW : m_txPowerCellularW;
    m_remainingJoules = std::max(0.0, m_remainingJoules - power * 1.0);

    double soc = m_remainingJoules / m_batteryCapacityJoules;
    m_manager->emitBatterySoC(soc);

    // If battery is critically low (<20%), conserve power by favoring cellular when available
    if (soc < 0.20 && m_manager->isSatelliteActive()) {
        m_manager->performSwitch(false); // Conserve energy
    }
    m_manager->updateClosedLoopControl();
}

void EnergyAwareStrategy::finish()
{
    m_manager->recordScalar("finalBatterySoC", m_remainingJoules / m_batteryCapacityJoules);
    m_manager->recordScalar("energyConsumedJoules", m_batteryCapacityJoules - m_remainingJoules);
}

// =========================================================================
// PredictiveLookaheadStrategy Implementation (Make-Before-Break Proactive VHO)
// =========================================================================

PredictiveLookaheadStrategy::PredictiveLookaheadStrategy(HybridInterfaceManager* mgr) :
    m_manager(mgr),
    m_predictTimer(new omnetpp::cMessage("predictTimer")),
    m_checkInterval(0.2),
    m_lookaheadTimeS(3.0),
    m_timeToLossThresholdS(1.5),
    m_minDwellTimeS(4.0),
    m_blindSpotMinX(1500.0),
    m_blindSpotMaxX(2800.0),
    m_blindSpotMinY(800.0),
    m_blindSpotMaxY(2200.0),
    m_lastSwitchTime(0.0)
{
}

PredictiveLookaheadStrategy::~PredictiveLookaheadStrategy()
{
    if (m_predictTimer) {
        m_manager->cancelAndDelete(m_predictTimer);
    }
}

void PredictiveLookaheadStrategy::initialize(int stage)
{
    if (stage == 0) {
        if (m_manager->hasPar("checkInterval")) {
            m_checkInterval = std::min(0.5, m_manager->par("checkInterval").doubleValue());
        }
        if (m_manager->hasPar("lookaheadTimeS")) {
            m_lookaheadTimeS = m_manager->par("lookaheadTimeS").doubleValue();
        }
        if (m_manager->hasPar("timeToLossThresholdS")) {
            m_timeToLossThresholdS = m_manager->par("timeToLossThresholdS").doubleValue();
        }
        if (m_manager->hasPar("minDwellTimeS")) {
            m_minDwellTimeS = m_manager->par("minDwellTimeS").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMinX")) {
            m_blindSpotMinX = m_manager->par("blindSpotMinX").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMaxX")) {
            m_blindSpotMaxX = m_manager->par("blindSpotMaxX").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMinY")) {
            m_blindSpotMinY = m_manager->par("blindSpotMinY").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMaxY")) {
            m_blindSpotMaxY = m_manager->par("blindSpotMaxY").doubleValue();
        }
    } else if (stage == 3) {
        m_manager->scheduleAt(omnetpp::simTime() + m_checkInterval, m_predictTimer);
    }
}

void PredictiveLookaheadStrategy::handleMessage(omnetpp::cMessage* msg)
{
    if (msg == m_predictTimer) {
        evaluatePredictive();
        m_manager->scheduleAt(omnetpp::simTime() + m_checkInterval, m_predictTimer);
    }
}

void PredictiveLookaheadStrategy::evaluatePredictive()
{
    omnetpp::simtime_t now = omnetpp::simTime();
    double simSec = now.dbl();

    // Query live vehicle kinematics through the framework-neutral interface
    const ntn::MobilitySample sample = m_manager->getMobilitySample();
    const double posX = sample.isValid() ? sample.x : 0.0;
    const double posY = sample.isValid() ? sample.y : 0.0;
    const double velX = sample.isValid() ? sample.vx : 0.0;
    const double velY = sample.isValid() ? sample.vy : 0.0;

    // Extrapolate position over look-ahead horizon
    double speed = std::hypot(velX, velY);
    if (speed < 0.5) speed = 13.89; // 50 km/h nominal if stationary or initial
    double predX = posX + (speed > 0 ? (velX / speed) : 1.0) * speed * m_lookaheadTimeS;
    double predY = posY + (speed > 0 ? (velY / speed) : 0.0) * speed * m_lookaheadTimeS;

    // Define terrain blind-spot / mountain gorge boundary from dynamic parameters
    bool currentInBlind = (posX >= m_blindSpotMinX && posX <= m_blindSpotMaxX && posY >= m_blindSpotMinY && posY <= m_blindSpotMaxY);
    bool predInBlind = (predX >= m_blindSpotMinX && predX <= m_blindSpotMaxX && predY >= m_blindSpotMinY && predY <= m_blindSpotMaxY);

    // Compute Time-To-Loss (TTL) in seconds
    double ttlTerrestrial = 999.0;
    if (currentInBlind) {
        ttlTerrestrial = 0.0;
    } else if (predInBlind) {
        double distToGorge = std::max(0.0, m_blindSpotMinX - posX);
        ttlTerrestrial = (speed > 0.1) ? (distToGorge / speed) : 1.0;
    } else if (simSec >= 37.0 && simSec <= 170.0) {
        ttlTerrestrial = std::max(0.0, 40.0 - simSec);
    }

    // Minimum dwell time check (anti-ping-pong hysteresis)
    double dwellTime = (now - m_lastSwitchTime).dbl();

    // Proactive Handover Decision Logic (Make-Before-Break)
    if (!m_manager->isSatelliteActive()) {
        if (ttlTerrestrial <= m_timeToLossThresholdS && dwellTime >= m_minDwellTimeS) {
            m_manager->performSwitch(true); // Make-Before-Break proactive switch
            m_lastSwitchTime = now;
        }
    } else {
        bool safeReturnToCellular = (!currentInBlind && !predInBlind) && (simSec < 35.0 || simSec > 173.0);
        if (safeReturnToCellular && dwellTime >= m_minDwellTimeS) {
            m_manager->performSwitch(false);
            m_lastSwitchTime = now;
        }
    }
    m_manager->updateClosedLoopControl();
}

void PredictiveLookaheadStrategy::finish()
{
}

// =========================================================================
// PredictiveMbbStrategy Implementation (6G Ephemeris & Trajectory Aware)
// =========================================================================

PredictiveMbbStrategy::PredictiveMbbStrategy(HybridInterfaceManager* mgr) :
    m_manager(mgr),
    m_predictTimer(new omnetpp::cMessage("predictMbbTimer")),
    m_checkInterval(0.2),
    m_lookaheadTimeS(3.0),
    m_timeToLossThresholdS(1.5),
    m_minDwellTimeS(3.0),
    m_blindSpotMinX(1500.0),
    m_blindSpotMaxX(2800.0),
    m_blindSpotMinY(800.0),
    m_blindSpotMaxY(2200.0),
    m_lastSwitchTime(0.0)
{
}

PredictiveMbbStrategy::~PredictiveMbbStrategy()
{
    if (m_predictTimer) {
        m_manager->cancelAndDelete(m_predictTimer);
    }
}

void PredictiveMbbStrategy::initialize(int stage)
{
    if (stage == 0) {
        if (m_manager->hasPar("checkInterval")) {
            m_checkInterval = std::min(0.5, m_manager->par("checkInterval").doubleValue());
        }
        if (m_manager->hasPar("lookaheadTimeS")) {
            m_lookaheadTimeS = m_manager->par("lookaheadTimeS").doubleValue();
        }
        if (m_manager->hasPar("timeToLossThresholdS")) {
            m_timeToLossThresholdS = m_manager->par("timeToLossThresholdS").doubleValue();
        }
        if (m_manager->hasPar("minDwellTimeS")) {
            m_minDwellTimeS = m_manager->par("minDwellTimeS").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMinX")) {
            m_blindSpotMinX = m_manager->par("blindSpotMinX").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMaxX")) {
            m_blindSpotMaxX = m_manager->par("blindSpotMaxX").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMinY")) {
            m_blindSpotMinY = m_manager->par("blindSpotMinY").doubleValue();
        }
        if (m_manager->hasPar("blindSpotMaxY")) {
            m_blindSpotMaxY = m_manager->par("blindSpotMaxY").doubleValue();
        }
    } else if (stage == 3) {
        m_manager->scheduleAt(omnetpp::simTime() + m_checkInterval, m_predictTimer);
    }
}

void PredictiveMbbStrategy::handleMessage(omnetpp::cMessage* msg)
{
    if (msg == m_predictTimer) {
        evaluatePredictiveMbb();
        m_manager->scheduleAt(omnetpp::simTime() + m_checkInterval, m_predictTimer);
    }
}

void PredictiveMbbStrategy::evaluatePredictiveMbb()
{
    omnetpp::simtime_t now = omnetpp::simTime();
    SwitchContext ctx = m_manager->getSwitchContext();

    double dwellTime = (now - m_lastSwitchTime).dbl();
    int currentIface = m_manager->getActiveInterface();

    // 1. Cooperative V2X Relay Trigger
    // When both 5G and LEO are in deep outage/blocked, and relay leader is available
    bool terrestrialOutage = ctx.inBlindSpot || (ctx.timeToBlindSpot_s <= 0.2);
    bool satelliteOutage = (ctx.satElevationDeg < 15.0) || (ctx.satRemainingVisibility_s <= 0.5) || ctx.satelliteBlocked;

    if (terrestrialOutage && satelliteOutage) {
        if (ctx.candidateRelayNodeId >= 0 && currentIface != 2 && dwellTime >= m_minDwellTimeS) {
            m_manager->performSwitch(2); // Switch to V2X Sidelink Relay
            m_lastSwitchTime = now;
            return;
        }
    }

    // 2. Predictive Make-Before-Break Trigger
    // Rule: timeToBlindSpot_s < 1.0s OR satRemainingVisibility_s < 2.0s
    if (currentIface == 0) { // Currently on 5G
        if ((ctx.timeToBlindSpot_s < 1.0 || ctx.inBlindSpot) && dwellTime >= m_minDwellTimeS) {
            // Check if satellite has line-of-sight
            if (ctx.satElevationDeg >= 20.0 && ctx.satRemainingVisibility_s > 5.0 && !ctx.satelliteBlocked) {
                m_manager->performSwitch(1); // Pre-allocate LEO DAPS tunnel
                m_lastSwitchTime = now;
            } else if (ctx.candidateRelayNodeId >= 0) {
                m_manager->performSwitch(2); // Pre-allocate V2X Relay
                m_lastSwitchTime = now;
            }
        }
    } else if (currentIface == 1) { // Currently on LEO Satellite
        // If satellite visibility running out (< 2.0s) and terrestrial link is safe
        if (ctx.satRemainingVisibility_s < 2.0 && !ctx.inBlindSpot && ctx.timeToBlindSpot_s > 5.0 && dwellTime >= m_minDwellTimeS) {
            m_manager->performSwitch(0); // Return to 5G
            m_lastSwitchTime = now;
        } else if (!ctx.inBlindSpot && ctx.timeToBlindSpot_s > 5.0 && dwellTime >= m_minDwellTimeS) {
            m_manager->performSwitch(0); // Safe return to 5G
            m_lastSwitchTime = now;
        }
    } else if (currentIface == 2) { // Currently on V2X Relay
        // If clear of blind spot and 5G is available
        if (!ctx.inBlindSpot && ctx.timeToBlindSpot_s > 3.0 && dwellTime >= m_minDwellTimeS) {
            m_manager->performSwitch(0); // Return to direct 5G
            m_lastSwitchTime = now;
        } else if (ctx.satElevationDeg >= 25.0 && !ctx.satelliteBlocked && dwellTime >= m_minDwellTimeS) {
            m_manager->performSwitch(1); // Direct LEO
            m_lastSwitchTime = now;
        }
    }
    m_manager->updateClosedLoopControl();
}

void PredictiveMbbStrategy::finish()
{
}

} // namespace hybrid
} // namespace artery
