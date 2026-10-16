#ifndef ARTERY_HYBRID_HYBRIDINTERFACEMANAGER_H
#define ARTERY_HYBRID_HYBRIDINTERFACEMANAGER_H

#include <omnetpp.h>
#include "artery/hybrid/ISwitchingStrategy.h"
#include "artery/ntn/interfaces/INetworkMobilityProvider.h"
#include "artery/ntn/interfaces/IRadioLinkMetricsProvider.h"
#include <string>
#include <memory>

namespace inet {
class IMobility;
}

namespace traci {
class VehicleController;
}

namespace artery {
namespace hybrid {

/**
 * HybridInterfaceManager - Orchestrates vertical handover (VHO) between
 * Terrestrial Cellular (5G-NR) and Non-Terrestrial Satellite (LEO NTN).
 * Inspired by squidslab/simu-scs-hybrid.
 *
 * Besides driving the VHO state machine, this module is the concrete adapter
 * of the framework-neutral ntn::INetworkMobilityProvider and
 * ntn::IRadioLinkMetricsProvider contracts. Switching strategies consume
 * mobility and link state through these interfaces instead of touching
 * inet::IMobility directly, keeping the decision logic framework-agnostic.
 */
class HybridInterfaceManager : public omnetpp::cSimpleModule,
                               public ntn::INetworkMobilityProvider,
                               public ntn::IRadioLinkMetricsProvider {
private:
    std::string m_switchingMode;
    std::string m_satInterfaceName;
    std::string m_cellInterfaceName;
    bool m_isSatelliteActive;
    int m_activeInterface; // 0 = 5G, 1 = Satellite LEO, 2 = V2X Sidelink Relay
    
    std::unique_ptr<ISwitchingStrategy> m_strategy;
    
    // 3GPP Rel-17 NTN Handover parameters & state
    double m_hysteresisMarginDb;
    double m_timeToTrigger;
    int m_candidateInterface; // -1 = none, 0 = 5G, 1 = Satellite, 2 = V2X
    omnetpp::simtime_t m_candidateTriggerTime;

    // Statistics & Counters
    int m_totalSwitches;
    omnetpp::simtime_t m_lastSwitchTime;
    omnetpp::simtime_t m_satTotalDuration;
    omnetpp::simtime_t m_cellTotalDuration;
    omnetpp::simtime_t m_v2xTotalDuration;

    // Sidelink Relay State
    int m_relayNodeId;
    double m_relayDistanceM;

    // Adapter state exposed through the abstract NTN interfaces
    inet::IMobility* m_mobilityModule;
    double m_lastQoSScore;
    double m_lastBatterySoC;
    double m_satelliteCarrierGhz;
    double m_cellularCarrierGhz;

    // Handover Interruption Time (HIT) tracking
    omnetpp::simtime_t m_handoverInterruptionUntil;
    bool m_isMakeBeforeBreak;

    omnetpp::simsignal_t m_sigActiveInterface;
    omnetpp::simsignal_t m_sigSwitchCount;
    omnetpp::simsignal_t m_sigQoSScore;
    omnetpp::simsignal_t m_sigBatterySoC;
    omnetpp::simsignal_t m_sigHandoverInterruption;
    omnetpp::simsignal_t m_sigV2XRelayActive;
    omnetpp::simsignal_t m_sigAoiMs;
    omnetpp::simsignal_t m_sigSafetySpeedReductionKmh;

    // Closed-Loop Cyber-Physical Vehicle Dynamics State
    omnetpp::simtime_t m_lastValidRxTime;
    double m_nominalSpeedMps;
    double m_currentSpeedReductionKmh;
    double m_lastMeasuredRttS;

protected:
    int numInitStages() const override { return 4; }
    void initialize(int stage) override;
    void handleMessage(omnetpp::cMessage* msg) override;
    void finish() override;
    
    std::unique_ptr<ISwitchingStrategy> createStrategy();

public:
    HybridInterfaceManager();
    virtual ~HybridInterfaceManager();
    
    void requestSwitch(bool toSatellite) { requestSwitch(toSatellite ? 1 : 0); }
    void performSwitch(bool toSatellite) { performSwitch(toSatellite ? 1 : 0); }
    void requestSwitch(int targetInterface);
    void performSwitch(int targetInterface);
    int getActiveInterface() const { return m_activeInterface; }
    bool is5GActive() const { return m_activeInterface == 0; }
    bool isSatelliteActive() const { return m_activeInterface == 1; }
    bool isV2XActive() const { return m_activeInterface == 2; }
    int getRelayNodeId() const { return m_relayNodeId; }
    double getRelayDistanceM() const { return m_relayDistanceM; }
    bool findRelayNode(int& relayNodeId, double& distanceM, double& relaySinrDb) const;
    int getTotalSwitches() const { return m_totalSwitches; }
    double getHysteresisMarginDb() const { return m_hysteresisMarginDb; }
    double getTimeToTrigger() const { return m_timeToTrigger; }
    bool isHandoverInterrupted() const { return omnetpp::simTime() < m_handoverInterruptionUntil; }
    bool isMakeBeforeBreak() const { return m_isMakeBeforeBreak; }
    
    // Physics-based RTT calculation (Propagation + Transmission + Queuing/HARQ + HIT + Relay)
    double calculatePhysicalRTT(
        bool useSatellite,
        double packetSizeBytes = 1200.0,
        double ueSatDistanceKm = 650.0,
        double satGwDistanceKm = 700.0,
        double ueGnbDistanceKm = 0.8,
        double backhaulLatencyS = 0.002,
        double effectiveDataRateMbps = 100.0,
        double bler = 0.05
    ) const;
    double calculateRelayPhysicalRTT(
        int relayNodeId,
        double relayDistanceM,
        double packetSizeBytes = 1200.0,
        double bler = 0.05
    ) const;
    double getEffectiveThroughputMbps() const;
    SwitchContext getSwitchContext() const;

    void emitQoSScore(double score);
    void emitBatterySoC(double soc);

    // Closed-Loop Cyber-Physical Control (Network -> Vehicle Dynamics)
    void recordPacketReception(omnetpp::simtime_t genTime, double rttS);
    void updateClosedLoopControl();
    traci::VehicleController* getVehicleController() const;
    double getAgeOfInformationS() const;
    double getSafetySpeedReductionKmh() const { return m_currentSpeedReductionKmh; }

    // --- ntn::INetworkMobilityProvider -------------------------------------
    bool hasMobility() const override;
    ntn::MobilitySample getMobilitySample() const override;
    const char* getMobilityProviderName() const override;

    // --- ntn::IRadioLinkMetricsProvider ------------------------------------
    bool hasRadioLinkMetrics() const override;
    ntn::RadioLinkMetrics getRadioLinkMetrics() const override;
    const char* getRadioLinkMetricsProviderName() const override;
};

} // namespace hybrid
} // namespace artery

#endif
