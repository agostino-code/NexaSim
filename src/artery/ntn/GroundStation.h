#ifndef ARTERY_NTN_GROUNDSTATION_H
#define ARTERY_NTN_GROUNDSTATION_H

#include <omnetpp.h>

namespace artery {
namespace ntn {

class GroundStation : public omnetpp::cSimpleModule {
protected:
    virtual void initialize() override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
};

} // namespace ntn
} // namespace artery

#endif
