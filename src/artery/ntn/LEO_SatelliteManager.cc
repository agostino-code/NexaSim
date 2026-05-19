#include "artery/ntn/LEO_SatelliteManager.h"

namespace artery {
namespace ntn {

Define_Module(LEO_SatelliteManager);

void LEO_SatelliteManager::initialize() {
    EV << "Initializing LEO_SatelliteManager: " << par("satelliteName").stringValue() << "\n";
}

void LEO_SatelliteManager::handleMessage(omnetpp::cMessage* msg) {
    delete msg;
}

} // namespace ntn
} // namespace artery
