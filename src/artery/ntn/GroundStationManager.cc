#include "artery/ntn/GroundStationManager.h"

namespace artery {
namespace ntn {

Define_Module(GroundStationManager);

void GroundStationManager::initialize() {
    EV << "Initializing GroundStationManager\n";
}

void GroundStationManager::handleMessage(omnetpp::cMessage* msg) {
    delete msg;
}

} // namespace ntn
} // namespace artery
