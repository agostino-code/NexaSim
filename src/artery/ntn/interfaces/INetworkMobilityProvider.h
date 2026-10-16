#ifndef ARTERY_NTN_INTERFACES_INETWORKMOBILITYPROVIDER_H
#define ARTERY_NTN_INTERFACES_INETWORKMOBILITYPROVIDER_H

#include "artery/ntn/interfaces/MobilityTypes.h"

namespace artery {
namespace ntn {

/**
 * @brief Abstract source of node mobility for NTN/hybrid decision logic.
 *
 * Core handover and switching strategies must not depend on a concrete
 * mobility framework (INET IMobility, TraCI, SGP4, ...). They query this
 * interface instead; the framework-specific adapter lives in a small,
 * separately compiled translation unit (see ntn::InetMobilityProvider).
 */
class INetworkMobilityProvider {
public:
    virtual ~INetworkMobilityProvider() = default;

    //! @return true when a valid mobility sample can be produced
    virtual bool hasMobility() const = 0;

    //! Current kinematic state of the node
    virtual MobilitySample getMobilitySample() const = 0;

    //! Human readable provider name for logging / diagnostics
    virtual const char* getMobilityProviderName() const = 0;

    /**
     * @brief Linear dead-reckoning of the mobility state.
     *
     * Default implementation extrapolates the current velocity vector over
     * the requested horizon. Concrete providers may override this with a
     * framework-aware implementation (e.g. TraCI route look-ahead or SGP4
     * orbital propagation).
     *
     * @param horizonS Look-ahead horizon in seconds (must be >= 0).
     */
    virtual MobilitySample predictMobilitySample(double horizonS) const
    {
        MobilitySample sample = getMobilitySample();
        if (horizonS <= 0.0 || !sample.isValid()) {
            return sample;
        }
        sample.x += sample.vx * horizonS;
        sample.y += sample.vy * horizonS;
        sample.z += sample.vz * horizonS;
        sample.timestampS += horizonS;
        return sample;
    }
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_INTERFACES_INETWORKMOBILITYPROVIDER_H
