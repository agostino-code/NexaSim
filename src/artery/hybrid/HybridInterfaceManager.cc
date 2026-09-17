#include "artery/hybrid/HybridInterfaceManager.h"
#include "artery/hybrid/Strategies.h"
#include <omnetpp.h>
#include <algorithm>

namespace artery {
namespace hybrid {

Define_Module(HybridInterfaceManager);

HybridInterfaceManager::HybridInterfaceManager() :
    m_isSatelliteActive(false),
    m_strategy(nullptr),
    m_totalSwitches(0),
    m_lastSwitchTime(SIMTIME_ZERO),
    m_satTotalDuration(SIMTIME_ZERO),
    m_cellTotalDuration(SIMTIME_ZERO)
{
}

HybridInterfaceManager::~HybridInterfaceManager()
{
    delete m_strategy;
}

void HybridInterfaceManager::initialize(int stage)
{
    if (stage == 0) {
        m_switchingMode = par("switchingMode").stdstringValue();
        m_satInterfaceName = par("satInterfaceName").stdstringValue();
        m_cellInterfaceName = par("cellInterfaceName").stdstringValue();
        m_isSatelliteActive = par("initialSatelliteActive").boolValue();
        
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

ISwitchingStrategy* HybridInterfaceManager::createStrategy()
{
    if (m_switchingMode == "coverage" || m_switchingMode == "coverage-based") {
        return new CoverageBasedStrategy(this);
    } else if (m_switchingMode == "qos" || m_switchingMode == "qos-based") {
        return new QoSBasedStrategy(this);
    } else if (m_switchingMode == "energy" || m_switchingMode == "energy-aware") {
        return new EnergyAwareStrategy(this);
    }
    // Default fallback: Coverage-based
    return new CoverageBasedStrategy(this);
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
    emit(m_sigQoSScore, score);
}

void HybridInterfaceManager::emitBatterySoC(double soc)
{
    emit(m_sigBatterySoC, soc);
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
    m_elevationMaskDeg(25.0)
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
    // Check coverage conditions: if vehicle is in gorge / deep valley, switch to satellite
    // Simulating terrain blind spot evaluation
    double simSec = omnetpp::simTime().dbl();
    bool terrestrialBlocked = (simSec >= 45.0 && simSec <= 180.0);
    
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
    double pdr = m_manager->isSatelliteActive() ? 0.98 : 0.99;
    double rtt = m_manager->isSatelliteActive() ? 0.025 : 0.005; // 25ms sat vs 5ms 5G
    double jitter = 0.002;
    
    double score = computeScore(pdr, rtt, jitter);
    m_manager->emitQoSScore(score);
    
    // If QoS drops below threshold, trigger handover
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
}

} // namespace hybrid
} // namespace artery
