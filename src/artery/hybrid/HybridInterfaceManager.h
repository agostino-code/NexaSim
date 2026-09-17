#ifndef ARTERY_HYBRID_HYBRIDINTERFACEMANAGER_H
#define ARTERY_HYBRID_HYBRIDINTERFACEMANAGER_H

#include <omnetpp.h>
#include "artery/hybrid/ISwitchingStrategy.h"
#include <string>

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
    
    ISwitchingStrategy* m_strategy;
    
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
    
    ISwitchingStrategy* createStrategy();

public:
    HybridInterfaceManager();
    virtual ~HybridInterfaceManager();
    
    void performSwitch(bool toSatellite);
    bool isSatelliteActive() const { return m_isSatelliteActive; }
    int getTotalSwitches() const { return m_totalSwitches; }
    
    void emitQoSScore(double score);
    void emitBatterySoC(double soc);
};

} // namespace hybrid
} // namespace artery

#endif
