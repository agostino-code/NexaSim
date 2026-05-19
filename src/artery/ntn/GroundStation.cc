#include "artery/ntn/GroundStation.h"

namespace artery {
namespace ntn {

Define_Module(GroundStation);

void GroundStation::initialize() {
    EV << "Initializing GroundStation\n";
}

void GroundStation::handleMessage(omnetpp::cMessage* msg) {
    delete msg;
}

} // namespace ntn
} // namespace artery
