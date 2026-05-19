#ifndef ARTERY_NTN_GROUNDSTATIONMANAGER_H
#define ARTERY_NTN_GROUNDSTATIONMANAGER_H

#include <omnetpp.h>

namespace artery {
namespace ntn {

class GroundStationManager : public omnetpp::cSimpleModule {
protected:
    virtual void initialize() override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
};

} // namespace ntn
} // namespace artery

#endif
