#ifndef ARTERY_NTN_INTERFACES_IRADIOLINKMETRICSPROVIDER_H
#define ARTERY_NTN_INTERFACES_IRADIOLINKMETRICSPROVIDER_H

#include <cmath>
#include <string>

namespace artery {
namespace ntn {

//! Radio interface currently selected by the vertical handover logic.
enum class ActiveRadioInterface {
    UNKNOWN = -1,
    NONE = 0,
    TERRESTRIAL_NR = 1,
    NTN_LEO = 2,
    V2X_SIDELINK = 3,
};

/**
 * @brief Snapshot of the radio link measured/provided by a RAT manager.
 *
 * Fields that a concrete provider cannot (yet) observe are left as
 * NOT_AVAILABLE instead of being fabricated, so consumers can distinguish a
 * genuine measurement from an unavailable one.
 */
struct RadioLinkMetrics {
    ActiveRadioInterface activeInterface = ActiveRadioInterface::UNKNOWN;
    std::string servingNodeId;

    double carrierGhz = NOT_AVAILABLE;      //!< Active carrier frequency [GHz]
    double bandwidthMhz = NOT_AVAILABLE;    //!< Channel bandwidth [MHz]
    double rsrpDbm = NOT_AVAILABLE;         //!< Reference signal received power [dBm]
    double rsrqDb = NOT_AVAILABLE;          //!< Reference signal received quality [dB]
    double sinrDb = NOT_AVAILABLE;          //!< Signal to interference plus noise [dB]

    // NTN geometry towards the serving satellite / node
    double elevationDeg = NOT_AVAILABLE;    //!< Elevation angle of the serving node [deg]
    double slantRangeKm = NOT_AVAILABLE;    //!< Slant range to the serving node [km]
    double dopplerKhz = NOT_AVAILABLE;      //!< Doppler shift of the active carrier [kHz]

    double qosScore = NOT_AVAILABLE;        //!< Multi-criteria utility score (0..1)
    long switchCount = 0;                   //!< Cumulative vertical handovers
    double batterySoc = NOT_AVAILABLE;      //!< Battery state of charge (0..1)
    bool geometryValid = false;             //!< True when elevation/range/Doppler are measured
};

/**
 * @brief Abstract source of radio link quality and RAT state.
 *
 * This decouples QoS-based switching, telemetry export and NTN handover
 * prediction from the concrete implementation (INET radio, Simu5G stack or
 * co-simulation model).
 */
class IRadioLinkMetricsProvider {
public:
    virtual ~IRadioLinkMetricsProvider() = default;

    //! @return true when getRadioLinkMetrics() carries at least the RAT state
    virtual bool hasRadioLinkMetrics() const = 0;

    //! Current radio link snapshot
    virtual RadioLinkMetrics getRadioLinkMetrics() const = 0;

    //! Human readable provider name for logging / diagnostics
    virtual const char* getRadioLinkMetricsProviderName() const = 0;
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_INTERFACES_IRADIOLINKMETRICSPROVIDER_H
