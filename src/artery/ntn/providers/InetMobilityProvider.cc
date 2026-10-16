#include "artery/ntn/providers/InetMobilityProvider.h"

#include <inet/common/geometry/common/Coord.h>
#include <inet/mobility/contract/IMobility.h>
#include <omnetpp.h>

#include <cmath>

namespace artery {
namespace ntn {

InetMobilityProvider::InetMobilityProvider(inet::IMobility* mobility) :
    m_mobility(mobility)
{
}

InetMobilityProvider InetMobilityProvider::fromContainingNode(omnetpp::cModule* node)
{
    if (node) {
        if (auto* mobility = dynamic_cast<inet::IMobility*>(node->getSubmodule("mobility"))) {
            return InetMobilityProvider(mobility);
        }
    }
    return InetMobilityProvider(nullptr);
}

bool InetMobilityProvider::hasMobility() const
{
    return m_mobility != nullptr;
}

MobilitySample InetMobilityProvider::getMobilitySample() const
{
    if (!m_mobility) {
        return MobilitySample::notAvailable();
    }

    const inet::Coord position = m_mobility->getCurrentPosition();
    const inet::Coord velocity = m_mobility->getCurrentVelocity();

    MobilitySample sample;
    sample.x = position.x;
    sample.y = position.y;
    sample.z = position.z;
    sample.vx = velocity.x;
    sample.vy = velocity.y;
    sample.vz = velocity.z;
    sample.speedMps = std::hypot(sample.vx, sample.vy);
    if (sample.speedMps > 1e-6) {
        // Compass bearing: clockwise from north
        const double heading = std::atan2(sample.vx, sample.vy) * 180.0 / M_PI;
        sample.headingDeg = std::fmod(heading + 360.0, 360.0);
    }
    sample.timestampS = omnetpp::simTime().dbl();
    return sample;
}

const char* InetMobilityProvider::getMobilityProviderName() const
{
    return "INET mobility";
}

} // namespace ntn
} // namespace artery
