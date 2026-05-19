#ifndef ARTERY_NTN_LEO_SATELLITEMANAGER_H
#define ARTERY_NTN_LEO_SATELLITEMANAGER_H

#include <omnetpp.h>

namespace artery {
namespace ntn {

class LEO_SatelliteManager : public omnetpp::cSimpleModule {
protected:
    virtual void initialize() override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
};

} // namespace ntn
} // namespace artery

#endif
