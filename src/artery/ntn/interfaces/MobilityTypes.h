#ifndef ARTERY_NTN_INTERFACES_MOBILITYTYPES_H
#define ARTERY_NTN_INTERFACES_MOBILITYTYPES_H

#include <cmath>
#include <limits>

namespace artery {
namespace ntn {

/**
 * @brief Framework-neutral kinematic state of a simulated node.
 *
 * This is the common currency exchanged between the abstract NTN/hybrid
 * interfaces and their concrete adapters. It deliberately carries no INET,
 * Simu5G or space_veins types so that core handover logic can be compiled and
 * unit-tested without pulling any of those frameworks.
 *
 * Coordinates are expressed in the local simulation reference frame:
 *  - x: easting  [m]
 *  - y: northing [m]
 *  - z: height above the reference plane (or above WGS84 for aerial nodes) [m]
 */
struct MobilitySample {
    double x = 0.0;          //!< Easting [m]
    double y = 0.0;          //!< Northing [m]
    double z = 0.0;          //!< Height [m]
    double vx = 0.0;         //!< Velocity along X [m/s]
    double vy = 0.0;         //!< Velocity along Y [m/s]
    double vz = 0.0;         //!< Velocity along Z [m/s]
    double speedMps = 0.0;   //!< Horizontal speed magnitude [m/s]
    double headingDeg = 0.0; //!< Heading clockwise from north [deg]
    double timestampS = 0.0; //!< Simulation time of the sample [s]

    bool isValid() const
    {
        return std::isfinite(x) && std::isfinite(y) && std::isfinite(z);
    }

    //! Sample with non-finite coordinates, used when no measurement is available
    static MobilitySample notAvailable()
    {
        MobilitySample sample;
        sample.x = sample.y = sample.z = std::numeric_limits<double>::quiet_NaN();
        return sample;
    }
};

//! @return true when the sample carries a usable (finite) value
inline bool isFinite(double value)
{
    return std::isfinite(value);
}

constexpr double NOT_AVAILABLE = std::numeric_limits<double>::quiet_NaN();

//! Horizontal (ground-plane) distance between two samples [m]
inline double horizontalDistanceM(const MobilitySample& a, const MobilitySample& b)
{
    return std::hypot(a.x - b.x, a.y - b.y);
}

//! Three-dimensional (slant) distance between two samples [m]
inline double slantRangeM(const MobilitySample& a, const MobilitySample& b)
{
    return std::sqrt((a.x - b.x) * (a.x - b.x) +
                     (a.y - b.y) * (a.y - b.y) +
                     (a.z - b.z) * (a.z - b.z));
}

/**
 * @brief Elevation angle of @p target as seen from @p observer [deg].
 * Zero degrees means the target is on the observer's horizontal plane,
 * 90 degrees means it is at the observer's zenith.
 */
inline double elevationDeg(const MobilitySample& observer, const MobilitySample& target)
{
    const double ground = horizontalDistanceM(observer, target);
    const double height = target.z - observer.z;
    return std::atan2(height, ground) * 180.0 / M_PI;
}

//! Range rate (closing speed, positive when approaching) [m/s]
inline double rangeRateMps(const MobilitySample& observer, const MobilitySample& target)
{
    const double dx = target.x - observer.x;
    const double dy = target.y - observer.y;
    const double dz = target.z - observer.z;
    const double range = std::sqrt(dx * dx + dy * dy + dz * dz);
    if (range < 1e-6) {
        return 0.0;
    }
    const double dvx = target.vx - observer.vx;
    const double dvy = target.vy - observer.vy;
    const double dvz = target.vz - observer.vz;
    const double rangeRate = -(dx * dvx + dy * dvy + dz * dvz) / range;
    return rangeRate;
}

/**
 * @brief Doppler shift of a carrier caused by the relative motion [Hz].
 * @param rangeRate Positive when the two nodes are approaching.
 * @param carrierHz Carrier frequency [Hz].
 */
inline double dopplerShiftHz(double rangeRate, double carrierHz)
{
    constexpr double C_LIGHT = 299792458.0; // m/s
    return (rangeRate / C_LIGHT) * carrierHz;
}

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_INTERFACES_MOBILITYTYPES_H
