#include "artery/ntn/GroundStationManager.h"
#include "artery/ntn/ConstellationManager.h"
#include <cmath>
#include <algorithm>

namespace artery {
namespace ntn {

Define_Module(GroundStationManager);

void GroundStationManager::initialize(int stage) {
    if (stage == 0) {
        if (hasPar("elevationMaskDeg")) {
            m_elevationMaskDeg = par("elevationMaskDeg").doubleValue();
        }
        if (hasPar("feederFrequencyGhz")) {
            m_feederFrequencyGhz = par("feederFrequencyGhz").doubleValue();
        }
        if (hasPar("feederBandwidthMhz")) {
            m_feederBandwidthMhz = par("feederBandwidthMhz").doubleValue();
        }

        m_sigFeederLinkActive = registerSignal("feederLinkActive");
        m_sigFeederLinkSinr = registerSignal("feederLinkSinr");
    } else if (stage == 1) {
        m_constellationManager = dynamic_cast<ConstellationManager*>(
            getSimulation()->getModuleByPath("constellationManager"));
        if (!m_constellationManager) {
            m_constellationManager = dynamic_cast<ConstellationManager*>(
                getSimulation()->getModuleByPath("GeneratedScenario.constellationManager"));
        }

        m_checkTimer = new omnetpp::cMessage("feederCheckTimer");
        scheduleAt(omnetpp::simTime() + 1.0, m_checkTimer);
    }
}

void GroundStationManager::handleMessage(omnetpp::cMessage* msg) {
    if (msg == m_checkTimer) {
        updateFeederLinkStatus();
        scheduleAt(omnetpp::simTime() + 1.0, m_checkTimer);
    } else {
        delete msg;
    }
}

void GroundStationManager::updateFeederLinkStatus() {
    if (!m_constellationManager) return;

    omnetpp::cModule* parent = getParentModule();
    omnetpp::cModule* mobility = parent ? parent->getSubmodule("mobility") : nullptr;
    inet::Coord gsPos(0, 0, 0);
    if (mobility && mobility->hasPar("initialX") && mobility->hasPar("initialY")) {
        gsPos = inet::Coord(mobility->par("initialX").doubleValue(),
                            mobility->par("initialY").doubleValue(),
                            mobility->hasPar("initialZ") ? mobility->par("initialZ").doubleValue() : 50.0);
    }

    auto visibleSats = m_constellationManager->findVisibleSatellites(gsPos, m_elevationMaskDeg);
    if (!visibleSats.empty()) {
        m_feederActive = true;
        m_connectedSatId = visibleSats[0];

        // Feeder link budget (High-gain parabolic dish 55 dBi, Ka-band 28 GHz)
        double metrics = m_constellationManager->calculateTopocentricMetrics(m_connectedSatId, gsPos, inet::Coord(0,0,0), m_feederFrequencyGhz, m_elevationMaskDeg).elevationDeg;
        // SINR model: 15-28 dB depending on elevation angle
        m_lastSinrDb = 15.0 + 13.0 * std::sin(metrics * M_PI / 180.0);
    } else {
        m_feederActive = false;
        m_connectedSatId = -1;
        m_lastSinrDb = -20.0;
    }

    emit(m_sigFeederLinkActive, m_feederActive ? 1L : 0L);
    emit(m_sigFeederLinkSinr, m_lastSinrDb);

    EV_DEBUG << "[GroundStationManager] " << getFullPath() 
             << " Feeder Active: " << m_feederActive 
             << ", SatId: " << m_connectedSatId 
             << ", SINR: " << m_lastSinrDb << " dB\n";
}

void GroundStationManager::finish() {
    cancelAndDelete(m_checkTimer);
}

} // namespace ntn
} // namespace artery
