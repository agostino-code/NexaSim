#ifndef ARTERY_NR_NRMANAGER_H
#define ARTERY_NR_NRMANAGER_H

#include <omnetpp.h>

namespace artery {
namespace nr {

class NRManager : public omnetpp::cSimpleModule {
protected:
    virtual void initialize() override;
};

} // namespace nr
} // namespace artery

#endif
