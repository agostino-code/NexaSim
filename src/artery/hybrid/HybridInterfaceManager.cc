#include "artery/hybrid/HybridInterfaceManager.h"
#include "artery/hybrid/Strategies.h"
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
    m_strategy(nullptr),
    m_hysteresisMarginDb(3.0),
    m_timeToTrigger(0.5),
    m_candidateInterface(-1),
    m_candidateTriggerTime(SIMTIME_ZERO),
    m_totalSwitches(0),
    m_lastSwitchTime(SIMTIME_ZERO),
    m_satTotalDuration(SIMTIME_ZERO),
    m_cellTotalDuration(SIMTIME_ZERO),
    m_mobilityModule(nullptr),
    m_lastQoSScore(ntn::NOT_AVAILABLE),
    m_lastBatterySoC(ntn::NOT_AVAILABLE),
    m_satelliteCarrierGhz(20.0),
    m_cellularCarrierGhz(3.5)
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

void HybridInterfaceManager::performSwitch(bool toSatellite)
{
    if (m_isSatelliteActive == toSatellite) {
        return; // Already on requested interface
    }
    
    omnetpp::simtime_t now = omnetpp::simTime();
    omnetpp::simtime_t delta = now - m_lastSwitchTime;
    
    if (m_isSatelliteActive) {
        m_satTotalDuration += delta;
    } else {
        m_cellTotalDuration += delta;
    }
    
    m_isSatelliteActive = toSatellite;
    m_lastSwitchTime = now;
    m_totalSwitches++;
    
    emit(m_sigActiveInterface, m_isSatelliteActive ? 1 : 0);
    emit(m_sigSwitchCount, m_totalSwitches);
    
    EV_INFO << "[HybridInterfaceManager] " << getFullPath() 
            << " Vertical Handover -> " 
            << (m_isSatelliteActive ? "SATELLITE_NTN" : "TERRESTRIAL_5G")
            << " (Total Switches: " << m_totalSwitches << ")\n";
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

void HybridInterfaceManager::finish()
{
    if (m_strategy) {
        m_strategy->finish();
    }
    
    omnetpp::simtime_t delta = omnetpp::simTime() - m_lastSwitchTime;
    if (m_isSatelliteActive) {
        m_satTotalDuration += delta;
    } else {
        m_cellTotalDuration += delta;
    }
    
    recordScalar("totalSwitches", m_totalSwitches);
    recordScalar("satTotalDuration", m_satTotalDuration.dbl());
    recordScalar("cellTotalDuration", m_cellTotalDuration.dbl());
    
    double totalTime = (m_satTotalDuration + m_cellTotalDuration).dbl();
    if (totalTime > 0.0) {
        recordScalar("satUsageRatio", m_satTotalDuration.dbl() / totalTime);
        recordScalar("cellUsageRatio", m_cellTotalDuration.dbl() / totalTime);
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
        // Satellite NTN Ka-Band link: stable ~24-27ms RTT, PDR 98.5%
        pdr = 0.985 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.005, 0.005);
        rtt = 0.025 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.002, 0.003);
        jitter = 0.002 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.0, 0.001);
    } else {
        // Terrestrial 5G-NR: very low latency (4-6ms) normally, but severe drop in shadow zone
        if (inShadowZone) {
            pdr = 0.50 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.1, 0.1);
            rtt = 0.095 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.01, 0.02);
            jitter = 0.015 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.0, 0.005);
        } else {
            pdr = 0.995 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.003, 0.003);
            rtt = 0.005 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), -0.001, 0.001);
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
}

void PredictiveLookaheadStrategy::finish()
{
}

} // namespace hybrid
} // namespace artery
