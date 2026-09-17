#ifndef ARTERY_NTN_NTNPATHLOSS_H
#define ARTERY_NTN_NTNPATHLOSS_H

#include "inet/physicallayer/pathloss/FreeSpacePathLoss.h"
#include "artery/ntn/NTNChannelModel.h"

namespace artery {
namespace ntn {

/**
 * @brief Dynamic 3GPP TR 38.811 & ITU-R NTN PathLoss implementation for INET Physical Layer.
 * Calculates exact real-time pathloss including FSPL, elevation-dependent LOS probability,
 * atmospheric gaseous absorption (ITU-R P.676), rain/snow attenuation (ITU-R P.838),
 * and topographical elevation masking for 3D LEO, Aerial and Terrestrial networks.
 */
class NTNPathLoss : public inet::physicallayer::FreeSpacePathLoss
{
protected:
    double rainRateMmPerH;
    double cloudLiquidWater;
    double elevationMaskDeg;
    bool atmosphericLossEnabled;
    std::string environmentType;
    NTNChannelModel channelModel;

    virtual void initialize(int stage) override;

public:
    NTNPathLoss();
    virtual std::ostream& printToStream(std::ostream& stream, int level) const override;
    virtual double computePathLoss(inet::mps propagationSpeed, inet::Hz frequency, inet::m distance) const override;
    virtual double computePathLoss(const inet::physicallayer::ITransmission *transmission, const inet::physicallayer::IArrival *arrival) const override;
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_NTNPATHLOSS_H
