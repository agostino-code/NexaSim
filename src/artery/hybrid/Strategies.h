#ifndef ARTERY_HYBRID_STRATEGIES_H
#define ARTERY_HYBRID_STRATEGIES_H

#include "artery/hybrid/ISwitchingStrategy.h"
#include "artery/hybrid/HybridInterfaceManager.h"
#include <omnetpp.h>

namespace artery {
namespace hybrid {

/**
 * Coverage-Based Switching Strategy:
 * Switches to satellite when 5G-NR terrestrial coverage is lost or degraded,
 * and falls back to 5G when terrestrial signal is restored.
 */
class CoverageBasedStrategy : public ISwitchingStrategy {
private:
    HybridInterfaceManager* m_manager;
    omnetpp::cMessage* m_evalTimer;
    double m_checkInterval;
    double m_elevationMaskDeg;
    double m_blindSpotMinX;
    double m_blindSpotMaxX;
    double m_blindSpotMinY;
    double m_blindSpotMaxY;

public:
    CoverageBasedStrategy(HybridInterfaceManager* mgr);
    virtual ~CoverageBasedStrategy();

    void initialize(int stage) override;
    void handleMessage(omnetpp::cMessage* msg) override;
    void finish() override;
    const char* getStrategyName() const override { return "CoverageBased"; }

private:
    void evaluate();
};

/**
 * QoS-Based Switching Strategy:
 * Evaluates Packet Delivery Ratio (PDR), End-to-End Latency/RTT and Jitter.
 * Computes a normalized multi-criteria utility score to select the best interface.
 */
class QoSBasedStrategy : public ISwitchingStrategy {
private:
    HybridInterfaceManager* m_manager;
    omnetpp::cMessage* m_qosTimer;
    double m_qosInterval;
    
    // Weights
    double m_weightPDR;
    double m_weightRTT;
    double m_weightJitter;
    
    double m_minPDR;
    double m_maxRTT;
    
    int m_consecutiveDegradations;
    int m_degradationThreshold;

public:
    QoSBasedStrategy(HybridInterfaceManager* mgr);
    virtual ~QoSBasedStrategy();

    void initialize(int stage) override;
    void handleMessage(omnetpp::cMessage* msg) override;
    void finish() override;
    const char* getStrategyName() const override { return "QoSBased"; }

private:
    void evaluateQoS();
    double computeScore(double pdr, double rtt, double jitter);
};

/**
 * Energy-Aware Strategy:
 * Balances transmission QoS against remaining vehicle battery State of Charge (SoC).
 * Reduces power-hungry satellite phased-array transmissions when SoC is low.
 */
class EnergyAwareStrategy : public ISwitchingStrategy {
private:
    HybridInterfaceManager* m_manager;
    omnetpp::cMessage* m_energyTimer;
    double m_batteryCapacityJoules;
    double m_remainingJoules;
    double m_txPowerCellularW;
    double m_txPowerSatelliteW;

public:
    EnergyAwareStrategy(HybridInterfaceManager* mgr);
    virtual ~EnergyAwareStrategy();

    void initialize(int stage) override;
    void handleMessage(omnetpp::cMessage* msg) override;
    void finish() override;
    const char* getStrategyName() const override { return "EnergyAware"; }

private:
    void evaluateEnergy();
};

/**
 * Predictive Look-Ahead Strategy:
 * Uses vehicle kinematic state (position and velocity vector) from IMobility
 * to extrapolate trajectory over a look-ahead horizon (3.0s).
 * Evaluates Time-To-Loss (TTL) and triggers proactive Make-Before-Break
 * handover ~1.5s BEFORE entering a tunnel / blind-spot gorge or cell boundary,
 * completely avoiding packet loss and interruption time.
 */
class PredictiveLookaheadStrategy : public ISwitchingStrategy {
private:
    HybridInterfaceManager* m_manager;
    omnetpp::cMessage* m_predictTimer;
    double m_checkInterval;
    double m_lookaheadTimeS;
    double m_timeToLossThresholdS;
    double m_minDwellTimeS;
    double m_blindSpotMinX;
    double m_blindSpotMaxX;
    double m_blindSpotMinY;
    double m_blindSpotMaxY;
    omnetpp::simtime_t m_lastSwitchTime;

public:
    PredictiveLookaheadStrategy(HybridInterfaceManager* mgr);
    virtual ~PredictiveLookaheadStrategy();

    void initialize(int stage) override;
    void handleMessage(omnetpp::cMessage* msg) override;
    void finish() override;
    const char* getStrategyName() const override { return "PredictiveLookahead"; }

private:
    void evaluatePredictive();
};

} // namespace hybrid
} // namespace artery

#endif
