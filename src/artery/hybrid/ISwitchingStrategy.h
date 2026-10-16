#ifndef ARTERY_HYBRID_ISWITCHINGSTRATEGY_H
#define ARTERY_HYBRID_ISWITCHINGSTRATEGY_H

#include <omnetpp.h>
#include <string>

namespace artery {
namespace hybrid {

class HybridInterfaceManager;

/**
 * 6G/SAGIN Ephemeris & Trajectory Context for Predictive Switching Strategies
 */
struct SwitchContext {
    double satElevationDeg = 0.0;
    double satElevationRateDegS = 0.0;
    double satRemainingVisibility_s = 999.0;
    double timeToBlindSpot_s = 999.0;
    double dopplerShiftKhz = 0.0;
    double dopplerRate_hz_s = 0.0;
    double sinr5G_db = 25.0;
    double sinrLeo_db = 18.0;
    double sinrV2X_db = 30.0;
    bool inBlindSpot = false;
    bool satelliteBlocked = false;
    int candidateRelayNodeId = -1;
    double relayDistanceM = 0.0;
};

/**
 * Interface for multi-RAT vertical handover switching strategies
 * Compatible with simu-scs-hybrid architecture.
 */
class ISwitchingStrategy {
public:
    virtual ~ISwitchingStrategy() = default;
    virtual void initialize(int stage) = 0;
    virtual void handleMessage(omnetpp::cMessage* msg) = 0;
    virtual void finish() = 0;
    virtual const char* getStrategyName() const = 0;
};

} // namespace hybrid
} // namespace artery

#endif
