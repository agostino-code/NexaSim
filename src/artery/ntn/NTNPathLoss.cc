#include "artery/ntn/NTNPathLoss.h"
#include "inet/physicallayer/contract/packetlevel/IRadioMedium.h"
#include "inet/physicallayer/contract/packetlevel/IRadioSignal.h"
#include "inet/common/INETMath.h"

namespace artery {
namespace ntn {

Define_Module(NTNPathLoss);

NTNPathLoss::NTNPathLoss() :
    rainRateMmPerH(0.0),
    cloudLiquidWater(0.0),
    elevationMaskDeg(10.0),
    atmosphericLossEnabled(true),
    environmentType("suburban")
{
}

void NTNPathLoss::initialize(int stage)
{
    FreeSpacePathLoss::initialize(stage);
    if (stage == inet::INITSTAGE_LOCAL) {
        rainRateMmPerH = par("rainRateMmPerH");
        cloudLiquidWater = par("cloudLiquidWater");
        elevationMaskDeg = par("elevationMaskDeg");
        atmosphericLossEnabled = par("atmosphericLossEnabled");
        environmentType = par("environmentType").stringValue();
    }
}

std::ostream& NTNPathLoss::printToStream(std::ostream& stream, int level) const
{
    FreeSpacePathLoss::printToStream(stream, level);
    stream << ", rainRate = " << rainRateMmPerH << " mm/h"
           << ", elevMask = " << elevationMaskDeg << " deg"
           << ", env = " << environmentType;
    return stream;
}

double NTNPathLoss::computePathLoss(inet::mps propagationSpeed, inet::Hz frequency, inet::m distance) const
{
    double freqGhz = frequency.get() / 1e9;
    if (freqGhz <= 0.0) freqGhz = 28.0;
    double distKm = distance.get() / 1000.0;
    if (distKm <= 0.0) return 1.0;

    NTNChannelModel::ChannelParams params;
    params.frequencyGhz = freqGhz;
    params.elevationDeg = 45.0; // Nominal elevation
    params.altitudeKm = distKm;
    params.rainRateMmPerH = rainRateMmPerH;
    params.cloudLiquidWater = cloudLiquidWater;

    auto plResult = const_cast<NTNChannelModel&>(channelModel).calculatePathLoss(params, 7.6, 0.03);
    return inet::math::dB2fraction(-plResult.totalLossDb);
}

double NTNPathLoss::computePathLoss(const inet::physicallayer::ITransmission *transmission, const inet::physicallayer::IArrival *arrival) const
{
    auto txPos = transmission->getStartPosition();
    auto rxPos = arrival->getStartPosition();
    auto diff = txPos - rxPos;
    double distanceM = diff.length();
    if (distanceM <= 0.0) return 1.0;

    // Elevation angle in degrees relative to horizontal ground plane
    double heightDiff = std::abs(txPos.z - rxPos.z);
    double elevationDeg = (distanceM > 0.0) ? (std::asin(std::min(1.0, heightDiff / distanceM)) * 180.0 / M_PI) : 90.0;

    auto radioMedium = transmission->getMedium();
    inet::Hz centerFrequency = inet::Hz(28e9);
    auto narrowbandSignalAnalogModel = dynamic_cast<const inet::physicallayer::INarrowbandSignal *>(transmission->getAnalogModel());
    if (narrowbandSignalAnalogModel) {
        centerFrequency = inet::Hz(narrowbandSignalAnalogModel->getCenterFrequency());
    }

    double freqGhz = centerFrequency.get() / 1e9;
    if (freqGhz <= 0.0) freqGhz = 28.0;

    // Topographical / mountain gorge elevation mask obstruction
    double topoLossDb = 0.0;
    if (elevationDeg < elevationMaskDeg) {
        topoLossDb = (elevationMaskDeg - elevationDeg) * 3.5; // 3.5 dB per degree below mask
    }

    // 3GPP TR 38.811 Slant range and Path Loss calculations
    NTNChannelModel::ChannelParams params;
    params.frequencyGhz = freqGhz;
    params.elevationDeg = std::max(1.0, elevationDeg);
    params.altitudeKm = std::max(txPos.z, rxPos.z) / 1000.0;
    params.rainRateMmPerH = rainRateMmPerH;
    params.cloudLiquidWater = cloudLiquidWater;

    NTNChannelModel::Environment env = NTNChannelModel::Environment::SUBURBAN;
    if (environmentType == "urban" || environmentType == "dense_urban") env = NTNChannelModel::Environment::URBAN;
    else if (environmentType == "rural") env = NTNChannelModel::Environment::RURAL;
    else if (environmentType == "maritime") env = NTNChannelModel::Environment::MARITIME;
    else if (environmentType == "aeronautical") env = NTNChannelModel::Environment::AERONAUTICAL;
    params.env = env;

    auto plResult = const_cast<NTNChannelModel&>(channelModel).calculatePathLoss(params, 7.6, 0.03);
    double totalLossDb = plResult.totalLossDb + topoLossDb;

    // Convert dB to linear attenuation factor (P_rx / P_tx <= 1.0)
    return inet::math::dB2fraction(-totalLossDb);
}

} // namespace ntn
} // namespace artery
