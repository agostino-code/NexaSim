#include "artery/ntn/LEO_Satellite.h"

namespace artery {
namespace ntn {

Define_Module(LEO_Satellite);

void LEO_Satellite::initialize() {
    EV << "Initializing LEO_Satellite: " << par("satelliteName").stringValue() << "\n";
}

void LEO_Satellite::handleMessage(omnetpp::cMessage* msg) {
    delete msg;
}

} // namespace ntn
} // namespace artery
