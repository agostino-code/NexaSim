#ifndef ARTERY_NTN_PROVIDERS_INETMOBILITYPROVIDER_H
#define ARTERY_NTN_PROVIDERS_INETMOBILITYPROVIDER_H

#include "artery/ntn/interfaces/INetworkMobilityProvider.h"

namespace omnetpp {
class cModule;
}

namespace inet {
class IMobility;
}

namespace artery {
namespace ntn {

/**
 * @brief Concrete adapter bridging inet::IMobility into the framework-neutral
 * ntn::INetworkMobilityProvider contract.
 *
 * This is the only translation unit of the NTN module that is allowed to know
 * about INET mobility types; core handover/switching logic consumes the
 * abstract interface instead. The header therefore keeps inet::IMobility as an
 * incomplete type and delegates the cast to the companion .cc file.
 */
class InetMobilityProvider : public INetworkMobilityProvider {
public:
    /**
     * @param mobility Mobility module of the node, or nullptr when the node
     *        does not expose one.
     */
    explicit InetMobilityProvider(inet::IMobility* mobility);

    /**
     * @brief Resolve the @c mobility submodule of @p node and wrap it when it
     * implements inet::IMobility.
     */
    static InetMobilityProvider fromContainingNode(omnetpp::cModule* node);

    bool hasMobility() const override;
    MobilitySample getMobilitySample() const override;
    const char* getMobilityProviderName() const override;

private:
    inet::IMobility* m_mobility = nullptr;
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_PROVIDERS_INETMOBILITYPROVIDER_H
