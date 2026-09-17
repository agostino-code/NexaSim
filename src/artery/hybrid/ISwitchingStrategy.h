#ifndef ARTERY_HYBRID_ISWITCHINGSTRATEGY_H
#define ARTERY_HYBRID_ISWITCHINGSTRATEGY_H

#include <omnetpp.h>
#include <string>

namespace artery {
namespace hybrid {

class HybridInterfaceManager;

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
