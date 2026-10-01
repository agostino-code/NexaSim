#ifndef ARTERY_HYBRID_HYBRIDINTERFACEMANAGER_H
#define ARTERY_HYBRID_HYBRIDINTERFACEMANAGER_H

#include <omnetpp.h>
#include "artery/hybrid/ISwitchingStrategy.h"
#include <string>
#include <memory>

namespace artery {
namespace hybrid {

/**
 * HybridInterfaceManager - Orchestrates vertical handover (VHO) between
 * Terrestrial Cellular (5G-NR) and Non-Terrestrial Satellite (LEO NTN).
 * Inspired by squidslab/simu-scs-hybrid.
 */
class HybridInterfaceManager : public omnetpp::cSimpleModule {
private:
    std::string m_switchingMode;
    std::string m_satInterfaceName;
    std::string m_cellInterfaceName;
    bool m_isSatelliteActive;
    
    std::unique_ptr<ISwitchingStrategy> m_strategy;
    
    // 3GPP Rel-17 NTN Handover parameters & state
    double m_hysteresisMarginDb;
    double m_timeToTrigger;
    int m_candidateInterface; // -1 = none, 0 = 5G, 1 = Satellite
    omnetpp::simtime_t m_candidateTriggerTime;

    // Statistics & Counters
    int m_totalSwitches;
    omnetpp::simtime_t m_lastSwitchTime;
    omnetpp::simtime_t m_satTotalDuration;
    omnetpp::simtime_t m_cellTotalDuration;
    
    omnetpp::simsignal_t m_sigActiveInterface;
    omnetpp::simsignal_t m_sigSwitchCount;
    omnetpp::simsignal_t m_sigQoSScore;
    omnetpp::simsignal_t m_sigBatterySoC;

protected:
    int numInitStages() const override { return 4; }
    void initialize(int stage) override;
    void handleMessage(omnetpp::cMessage* msg) override;
    void finish() override;
    
    std::unique_ptr<ISwitchingStrategy> createStrategy();

public:
    HybridInterfaceManager();
    virtual ~HybridInterfaceManager();
    
    void requestSwitch(bool toSatellite);
    void performSwitch(bool toSatellite);
    bool isSatelliteActive() const { return m_isSatelliteActive; }
    int getTotalSwitches() const { return m_totalSwitches; }
    double getHysteresisMarginDb() const { return m_hysteresisMarginDb; }
    double getTimeToTrigger() const { return m_timeToTrigger; }
    
    void emitQoSScore(double score);
    void emitBatterySoC(double soc);
};

} // namespace hybrid
} // namespace artery

#endif
