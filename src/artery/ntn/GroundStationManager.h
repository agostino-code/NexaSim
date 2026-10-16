#ifndef ARTERY_NTN_GROUNDSTATIONMANAGER_H
#define ARTERY_NTN_GROUNDSTATIONMANAGER_H

#include <omnetpp.h>
#include <inet/common/geometry/common/Coord.h>

namespace artery {
namespace ntn {

class ConstellationManager;

class GroundStationManager : public omnetpp::cSimpleModule {
private:
    double m_elevationMaskDeg = 10.0;
    double m_feederFrequencyGhz = 28.0;
    double m_feederBandwidthMhz = 1000.0;
    
    ConstellationManager* m_constellationManager = nullptr;
    omnetpp::cMessage* m_checkTimer = nullptr;
    
    bool m_feederActive = false;
    double m_lastSinrDb = 0.0;
    int m_connectedSatId = -1;

    omnetpp::simsignal_t m_sigFeederLinkActive;
    omnetpp::simsignal_t m_sigFeederLinkSinr;

protected:
    virtual void initialize(int stage) override;
    virtual int numInitStages() const override { return 2; }
    virtual void handleMessage(omnetpp::cMessage* msg) override;
    virtual void finish() override;

    void updateFeederLinkStatus();

public:
    bool isFeederLinkActive() const { return m_feederActive; }
    double getFeederLinkSinr() const { return m_lastSinrDb; }
    int getConnectedSatelliteId() const { return m_connectedSatId; }
};

} // namespace ntn
} // namespace artery

#endif
