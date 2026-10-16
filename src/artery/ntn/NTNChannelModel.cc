#include "artery/ntn/NTNChannelModel.h"
#include <omnetpp.h>
#include <cmath>
#include <random>
#include <algorithm>

namespace artery {
namespace ntn {

namespace {
// 3GPP TR 38.811 Elevation evaluation grid
constexpr double ELEV_GRID[6] = {10.0, 20.0, 30.0, 50.0, 70.0, 90.0};

double interpolateTable6(const double xGrid[6], const double yGrid[6], double x) {
    if (x <= xGrid[0]) return yGrid[0];
    if (x >= xGrid[5]) return yGrid[5];
    for (int i = 0; i < 5; ++i) {
        if (x >= xGrid[i] && x <= xGrid[i + 1]) {
            double frac = (x - xGrid[i]) / (xGrid[i + 1] - xGrid[i]);
            return yGrid[i] + frac * (yGrid[i + 1] - yGrid[i]);
        }
    }
    return yGrid[5];
}
}

double NTNChannelModel::besselJ1(double x) {
    if (std::abs(x) < 1e-12) {
        return 0.0;
    }
    double ans = 0.0;
    double term = x / 2.0;
    double x2_4 = (x * x) / 4.0;
    for (int m = 0; m < 25; ++m) {
        ans += term;
        term = -term * x2_4 / ((m + 1) * (m + 2));
        if (std::abs(term) < 1e-15) {
            break;
        }
    }
    return ans;
}

double NTNChannelModel::calculateBesselAntennaGain(
    double offBoresightDeg, double maxGainDbi, double apertureDiameterM, double frequencyGhz) {

    double lambdaM = 0.299792458 / std::max(0.1, frequencyGhz);
    double psiRad = std::abs(offBoresightDeg) * M_PI / 180.0;
    double u = M_PI * (apertureDiameterM / lambdaM) * std::sin(psiRad);

    if (std::abs(u) < 1e-5) {
        return maxGainDbi;
    }

    double ratio = 2.0 * besselJ1(u) / u;
    double patternPower = ratio * ratio;
    double relGainDb = (patternPower > 1e-5) ? 10.0 * std::log10(patternPower) : -50.0;

    // Floor relative sidelobes at -35 dB per 3GPP TR 38.811
    relGainDb = std::max(-35.0, relGainDb);
    return maxGainDbi + relGainDb;
}

double NTNChannelModel::calculateClutterLoss(double elevationDeg, FrequencyBand band, Environment env, bool isLOS) {
    if (isLOS) return 0.0; // Clutter loss is 0 dB in LOS per 3GPP TR 38.811 Section 6.6.2

    double elev = std::clamp(elevationDeg, 10.0, 90.0);

    // 3GPP TR 38.811 Table 6.6.2-2 (Ka-Band / high frequencies >= 6 GHz)
    if (band == FrequencyBand::KA_BAND || band == FrequencyBand::Q_V_BAND || band == FrequencyBand::W_BAND || band == FrequencyBand::KU_BAND) {
        if (env == Environment::URBAN || env == Environment::TROPICAL) {
            constexpr double clKaUrban[6] = {34.3, 27.2, 21.0, 15.5, 12.0, 10.0};
            return interpolateTable6(ELEV_GRID, clKaUrban, elev);
        } else if (env == Environment::SUBURBAN) {
            constexpr double clKaSuburban[6] = {28.5, 21.6, 16.2, 11.0, 8.0, 6.0};
            return interpolateTable6(ELEV_GRID, clKaSuburban, elev);
        } else {
            // Rural / Desert / Maritime
            constexpr double clKaRural[6] = {18.0, 13.0, 9.5, 6.0, 4.0, 2.5};
            return interpolateTable6(ELEV_GRID, clKaRural, elev);
        }
    } else {
        // 3GPP TR 38.811 Table 6.6.2-1 (S-band / sub-6 GHz)
        if (env == Environment::URBAN || env == Environment::TROPICAL) {
            constexpr double clSUrban[6] = {19.4, 15.6, 12.5, 8.4, 5.7, 4.0};
            return interpolateTable6(ELEV_GRID, clSUrban, elev);
        } else if (env == Environment::SUBURBAN) {
            constexpr double clSSuburban[6] = {15.2, 11.8, 9.0, 5.6, 3.5, 2.0};
            return interpolateTable6(ELEV_GRID, clSSuburban, elev);
        } else {
            // Rural
            constexpr double clSRural[6] = {10.5, 7.8, 5.4, 2.8, 1.5, 0.8};
            return interpolateTable6(ELEV_GRID, clSRural, elev);
        }
    }
}

double NTNChannelModel::getShadowFadingStdDev(double elevationDeg, FrequencyBand band, Environment env, bool isLOS) {
    double elev = std::clamp(elevationDeg, 10.0, 90.0);

    if (band == FrequencyBand::KA_BAND || band == FrequencyBand::Q_V_BAND || band == FrequencyBand::W_BAND || band == FrequencyBand::KU_BAND) {
        // 3GPP TR 38.811 Table 6.6.2-2
        if (env == Environment::URBAN || env == Environment::TROPICAL) {
            if (isLOS) {
                constexpr double sfLos[6] = {2.5, 2.0, 1.6, 1.2, 0.8, 0.6};
                return interpolateTable6(ELEV_GRID, sfLos, elev);
            } else {
                constexpr double sfNlos[6] = {7.2, 6.8, 6.0, 5.0, 4.2, 3.5};
                return interpolateTable6(ELEV_GRID, sfNlos, elev);
            }
        } else if (env == Environment::SUBURBAN) {
            if (isLOS) {
                constexpr double sfLos[6] = {2.0, 1.5, 1.2, 1.0, 0.7, 0.5};
                return interpolateTable6(ELEV_GRID, sfLos, elev);
            } else {
                constexpr double sfNlos[6] = {6.5, 5.8, 5.0, 4.0, 3.2, 2.5};
                return interpolateTable6(ELEV_GRID, sfNlos, elev);
            }
        } else {
            if (isLOS) {
                constexpr double sfLos[6] = {1.8, 1.2, 1.0, 0.8, 0.5, 0.4};
                return interpolateTable6(ELEV_GRID, sfLos, elev);
            } else {
                constexpr double sfNlos[6] = {5.5, 4.8, 4.0, 3.2, 2.5, 2.0};
                return interpolateTable6(ELEV_GRID, sfNlos, elev);
            }
        }
    } else {
        // 3GPP TR 38.811 Table 6.6.2-1
        if (env == Environment::URBAN || env == Environment::TROPICAL) {
            if (isLOS) {
                constexpr double sfLos[6] = {3.5, 3.4, 2.9, 3.0, 3.1, 2.7};
                return interpolateTable6(ELEV_GRID, sfLos, elev);
            } else {
                constexpr double sfNlos[6] = {8.5, 8.0, 7.5, 6.5, 5.5, 4.5};
                return interpolateTable6(ELEV_GRID, sfNlos, elev);
            }
        } else if (env == Environment::SUBURBAN) {
            if (isLOS) {
                constexpr double sfLos[6] = {2.8, 2.5, 2.0, 1.8, 1.4, 1.0};
                return interpolateTable6(ELEV_GRID, sfLos, elev);
            } else {
                constexpr double sfNlos[6] = {7.5, 6.8, 6.0, 5.0, 4.0, 3.0};
                return interpolateTable6(ELEV_GRID, sfNlos, elev);
            }
        } else {
            if (isLOS) {
                constexpr double sfLos[6] = {2.0, 1.6, 1.3, 1.0, 0.7, 0.5};
                return interpolateTable6(ELEV_GRID, sfLos, elev);
            } else {
                constexpr double sfNlos[6] = {6.0, 5.2, 4.5, 3.5, 2.8, 2.0};
                return interpolateTable6(ELEV_GRID, sfNlos, elev);
            }
        }
    }
}

NTNChannelModel::PathLossResult NTNChannelModel::calculatePathLoss(
    const ChannelParams& params,
    double satelliteVelocityKmps,
    double groundVelocityKmps,
    omnetpp::cRNG* rng) {

    PathLossResult result;

    // Slant range
    double slantRange = calculateSlantRange(params.altitudeKm, params.elevationDeg);

    // Free space loss
    result.freeSpaceLossDb = calculateFSPL(slantRange, params.frequencyGhz);

    // 3GPP TR 38.811 LOS probability
    result.losProbability = calculateLOSProbability(params.elevationDeg, params.env);

    // Discrete 3GPP LOS / NLOS state decision
    bool isLOS = true;
    if (rng) {
        isLOS = (omnetpp::uniform(rng, 0.0, 1.0) < result.losProbability);
    } else {
        uint32_t hash = static_cast<uint32_t>(params.elevationDeg * 100.0) ^ static_cast<uint32_t>(slantRange * 10.0);
        isLOS = ((hash % 1000) / 1000.0 < result.losProbability);
    }
    result.isLOS = isLOS;

    FrequencyBand band = (params.frequencyGhz >= 6.0) ? FrequencyBand::KA_BAND : FrequencyBand::S_BAND;

    // 3GPP TR 38.811 Clutter Loss (CL)
    result.clutterLossDb = calculateClutterLoss(params.elevationDeg, band, params.env, isLOS);

    // 3GPP TR 38.811 Shadow Fading (SF)
    double sigmaSF = getShadowFadingStdDev(params.elevationDeg, band, params.env, isLOS);
    if (rng) {
        result.shadowingDb = omnetpp::normal(rng, 0.0, sigmaSF);
    } else {
        double u1 = std::max(1e-6, ((static_cast<uint32_t>(slantRange * 17.0) % 997) + 1) / 1000.0);
        double u2 = ((static_cast<uint32_t>(params.elevationDeg * 23.0) % 997) + 1) / 1000.0;
        double z0 = std::sqrt(-2.0 * std::log(u1)) * std::cos(2.0 * M_PI * u2);
        result.shadowingDb = z0 * sigmaSF;
    }

    // Atmospheric losses (ITU-R P.676-12)
    result.atmosphericLossDb = calculateGaseousAbsorption(params.elevationDeg, params.frequencyGhz);

    // Rain attenuation (ITU-R P.838-3 / P.618-13)
    result.rainLossDb = calculateRainAttenuation(params.elevationDeg, params.frequencyGhz, params.rainRateMmPerH);

    // Cloud attenuation (ITU-R P.840)
    result.cloudLossDb = calculateCloudAttenuation(params.elevationDeg, params.frequencyGhz,
                                                    params.cloudLiquidWater, params.cloudTempC);

    // Scintillation
    result.scintillationLossDb = calculateScintillation(params.elevationDeg, params.frequencyGhz, params.scintillationSigma);

    // Polarization loss
    result.polarizationLossDb = params.polarizationLossDb;

    // Phased array antenna patterns (3GPP TR 38.811 Section 6.4.1)
    result.satAntennaGainDbi = calculateBesselAntennaGain(0.0, 30.0, 0.8, params.frequencyGhz);
    result.utAntennaGainDbi = calculateBesselAntennaGain(0.0, 34.0, 0.45, params.frequencyGhz);

    // Doppler shift
    result.dopplerShiftHz = calculateDopplerShift(satelliteVelocityKmps, groundVelocityKmps,
                                                   params.frequencyGhz, params.elevationDeg, 0.0);

    // 3D Obstacle & Azimuthal Horizon Masking (ITU-R P.526)
    if (params.obstacleElevationMaskDeg > 0.0 && params.elevationDeg < params.obstacleElevationMaskDeg) {
        result.isObstacleBlocked = true;
        result.isLOS = false;
        result.diffractionLossDb = calculateObstacleDiffractionLoss(
            params.elevationDeg, params.obstacleElevationMaskDeg, params.frequencyGhz, slantRange);
    } else {
        result.diffractionLossDb = 0.0;
        result.isObstacleBlocked = false;
    }

    // 3GPP TR 38.811 Section 6.6 total path loss equation:
    // PL = FSPL + SF + CL + A_g + A_r + A_c + A_s + L_pol + L_diff
    result.totalLossDb = result.freeSpaceLossDb + result.clutterLossDb + result.shadowingDb +
                         result.atmosphericLossDb + result.rainLossDb + result.cloudLossDb +
                         result.scintillationLossDb + result.polarizationLossDb + result.diffractionLossDb;

    return result;
}

double NTNChannelModel::calculateKnifeEdgeDiffractionLoss(double v)
{
    // ITU-R P.526-15 Section 4.1
    if (v <= -0.78) {
        return 0.0;
    }
    double term = std::sqrt((v - 0.1) * (v - 0.1) + 1.0) + v - 0.1;
    if (term <= 0.0) return 0.0;
    double j_v = 6.9 + 20.0 * std::log10(term);
    return std::max(0.0, j_v);
}

double NTNChannelModel::calculateObstacleDiffractionLoss(double elevationDeg, double obstacleMaskDeg, double frequencyGhz, double slantRangeKm)
{
    if (elevationDeg >= obstacleMaskDeg) {
        return 0.0;
    }

    constexpr double c0 = 299792458.0;
    double lambda = c0 / (frequencyGhz * 1e9);
    double angularDeficitRad = (obstacleMaskDeg - elevationDeg) * M_PI / 180.0;

    // Effective obstacle distance: assuming typical terrain ridge at d1 = 2000m, satellite at d2 = slantRangeKm * 1000m
    double d1 = 2000.0;
    double d2 = std::max(10000.0, slantRangeKm * 1000.0);
    double dEff = (d1 * d2) / (d1 + d2);

    // Knife edge parameter v = theta * sqrt(2 * dEff / lambda)
    double v = angularDeficitRad * std::sqrt(2.0 * dEff / lambda);

    return calculateKnifeEdgeDiffractionLoss(v);
}

double NTNChannelModel::calculateLOSProbability(double elevationDeg, Environment env) {
    // 3GPP TR 38.811 Section 6.6.1 Table 6.6.1-1
    double theta = std::max(1.0, std::min(89.5, elevationDeg));
    double thetaRad = theta * M_PI / 180.0;
    double pLos = 1.0;

    switch (env) {
        case Environment::RURAL:
            pLos = exp(-1.0 / (tan(thetaRad) * 18.98));
            break;
        case Environment::SUBURBAN:
            pLos = std::min(1.0, (theta / 90.0) + exp(-1.0 / (tan(thetaRad) * 7.5)));
            break;
        case Environment::URBAN:
            pLos = std::min(1.0, (theta / 90.0) + exp(-1.0 / (tan(thetaRad) * 3.5)));
            break;
        case Environment::DESERT:
            pLos = std::min(1.0, (theta / 90.0) + exp(-1.0 / (tan(thetaRad) * 12.0)));
            break;
        case Environment::TROPICAL:
            pLos = std::min(1.0, (theta / 90.0) + exp(-1.0 / (tan(thetaRad) * 4.0)));
            break;
        case Environment::AERONAUTICAL:
            pLos = (theta >= 5.0) ? 1.0 : (theta / 5.0);
            break;
        case Environment::MARITIME:
            pLos = (theta >= 3.0) ? 1.0 : (theta / 3.0);
            break;
        default:
            pLos = std::min(1.0, (theta / 90.0) + exp(-1.0 / (tan(thetaRad) * 6.0)));
            break;
    }
    return std::clamp(pLos, 0.0, 1.0);
}

double NTNChannelModel::calculateFSPL(double distanceKm, double frequencyGhz) {
    // Free Space Path Loss: 20*log10(4*pi*d*f/c)
    double c = 299792.458;  // km/s
    double wavelength = c / (frequencyGhz * 1e6);  // km
    return 20 * log10(4 * M_PI * distanceKm / wavelength);
}

double NTNChannelModel::calculateSlantRange(double altitudeKm, double elevationDeg) {
    const double earthRadiusKm = 6371.0;
    double elevationRad = elevationDeg * M_PI / 180.0;
    
    // Slant range calculation
    double term = earthRadiusKm * cos(elevationRad);
    double slantRange = -term + sqrt(term * term + altitudeKm * (2 * earthRadiusKm + altitudeKm));
    
    return slantRange;
}

double NTNChannelModel::calculateGaseousAbsorption(double elevationDeg, double frequencyGhz) {
    // ITU-R P.676-12 Specific Gaseous Attenuation
    double freq = frequencyGhz;
    double elevationRad = std::max(1.0, elevationDeg) * M_PI / 180.0;
    double elevationFactor = 1.0 / std::max(0.08, sin(elevationRad));

    // Dry air / Oxygen absorption
    double gamma_o = 0.0;
    if (freq < 50.0) {
        gamma_o = (7.2e-3 / (freq * freq + 0.36) + 3.22e-4 / (pow(freq - 60.0, 2) + 2.25)) * freq * freq;
    } else if (freq <= 70.0) {
        gamma_o = 15.0 / (1.0 + pow((freq - 60.0) / 4.0, 2));
    } else {
        gamma_o = 0.001 * freq;
    }
    double h_o = 6.0; // km

    // Water vapor absorption (22.235 GHz and 183.31 GHz lines)
    double rho = 7.5; // g/m^3 standard surface water vapor density
    double line22 = 0.0173 * rho * (freq * freq) / (pow(freq - 22.235, 2) + 9.0);
    double line183 = 0.002 * rho * (freq * freq) / (pow(freq - 183.31, 2) + 25.0);
    double continuum = 1.5e-6 * rho * pow(freq, 2.4);
    double gamma_w = line22 + line183 + continuum;
    double h_w = 2.2; // km

    return (gamma_o * h_o + gamma_w * h_w) * elevationFactor;
}

double NTNChannelModel::calculateRainAttenuation(double elevationDeg, double frequencyGhz, double rainRate) {
    // ITU-R P.618-13 / P.838-3 rain attenuation
    if (rainRate <= 0.0) return 0.0;

    auto [k, alpha] = getRainCoefficients(frequencyGhz);
    double gamma = k * pow(rainRate, alpha); // dB/km

    double elevationRad = std::max(1.0, elevationDeg) * M_PI / 180.0;
    double rainHeightKm = 3.5;
    double slantPathKm = rainHeightKm / std::max(0.08, sin(elevationRad));
    double d_h = slantPathKm * cos(elevationRad); // horizontal projection km

    // ITU-R P.618-13 horizontal reduction factor r_001
    double r_001 = 1.0 / (1.0 + 0.78 * sqrt(std::max(0.001, d_h * gamma / frequencyGhz)) - 0.38 * (1.0 - exp(-2.0 * d_h)));
    r_001 = std::clamp(r_001, 0.25, 1.0);

    return gamma * slantPathKm * r_001;
}

double NTNChannelModel::calculateCloudAttenuation(double elevationDeg, double frequencyGhz, 
                                                  double liquidWater, double temperature) {
    // ITU-R P.840 cloud/fog attenuation
    
    if (liquidWater <= 0) return 0.0;
    
    // Specific attenuation coefficient (dB/km per g/m^3)
    double K = getCloudAttenuationCoefficient(frequencyGhz, temperature);
    
    // Cloud height (typical)
    double cloudHeight = 2.0;  // km
    
    // Slant path through cloud
    double elevationRad = elevationDeg * M_PI / 180.0;
    double cloudPathLength = cloudHeight / std::max(0.1, sin(elevationRad));
    
    // Total liquid water along path (kg/m^2)
    double totalLiquidWater = liquidWater * cloudPathLength / cloudHeight;
    
    // Attenuation
    double attenuation = K * totalLiquidWater;
    
    return attenuation;
}

double NTNChannelModel::calculateScintillation(double elevationDeg, double frequencyGhz, double sigma) {
    // ITU-R P.1814 scintillation
    // Simplified: elevation-dependent scintillation
    
    if (sigma <= 0) return 0.0;
    
    // Scintillation increases at low elevations
    double elevationFactor = 1.0 / std::max(0.1, pow(sin(elevationDeg * M_PI / 180.0), 2));
    
    // Frequency scaling (scintillation index proportional to f^1.5)
    double freqFactor = pow(frequencyGhz / 10.0, 1.5);
    
    return sigma * elevationFactor * freqFactor;
}

double NTNChannelModel::calculateDopplerShift(double satelliteVelocityKmps, double groundVelocityKmps,
                                              double frequencyGhz, double elevationDeg, double azimuthDeg) {
    // Doppler shift for LEO satellite
    // f_d = (v_rel / c) * f_c
    
    const double c = 299792.458;  // km/s
    double fc = frequencyGhz * 1e9;  // Hz
    
    // Relative velocity along line of sight
    // Simplified: assume satellite moving perpendicular to ground track
    // and ground station stationary
    double vRel = satelliteVelocityKmps * cos(elevationDeg * M_PI / 180.0);
    
    // Add ground velocity component
    vRel += groundVelocityKmps;
    
    return (vRel / c) * fc;
}

double NTNChannelModel::calculateShadowing(double distanceKm, Environment env, omnetpp::cRNG* rng) {
    double sigma = 6.0;

    switch (env) {
        case Environment::URBAN: sigma = 8.0; break;
        case Environment::SUBURBAN: sigma = 6.0; break;
        case Environment::RURAL: sigma = 4.0; break;
        case Environment::MARITIME: sigma = 2.5; break;
        case Environment::AERONAUTICAL: sigma = 1.5; break;
        case Environment::DESERT: sigma = 3.5; break;
        case Environment::TROPICAL: sigma = 7.0; break;
        default: sigma = 5.0; break;
    }

    if (rng) {
        return omnetpp::normal(rng, 0.0, sigma);
    }

    // Deterministic pseudo-random Gaussian without static std::random_device
    uint32_t seed = static_cast<uint32_t>(distanceKm * 1000.0) ^ 0x9e3779b9;
    double u1 = std::max(1e-7, (seed % 100000) / 100000.0);
    double u2 = ((seed >> 5) % 100000) / 100000.0;
    double z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
    return z0 * sigma;
}

NTNChannelModel::MarkovState NTNChannelModel::updateMarkovState(
    MarkovState current, double elevationDeg, double distanceTraveledMeters, omnetpp::cRNG* rng) {
    double pLos = calculateLOSProbability(elevationDeg, Environment::SUBURBAN);
    double u = rng ? omnetpp::uniform(rng, 0.0, 1.0) : 0.5;
    if (u < pLos) {
        return MarkovState::STATE_GOOD_LOS;
    } else if (u < pLos + (1.0 - pLos) * 0.75) {
        return MarkovState::STATE_BAD_SHADOWED;
    } else {
        return MarkovState::STATE_DEEP_FADE;
    }
}

NTNChannelModel::FrequencyBand NTNChannelModel::getFrequencyBand(double frequencyGhz) {
    if (frequencyGhz < 2) return FrequencyBand::L_BAND;
    if (frequencyGhz < 4) return FrequencyBand::S_BAND;
    if (frequencyGhz < 8) return FrequencyBand::C_BAND;
    if (frequencyGhz < 18) return FrequencyBand::KU_BAND;
    if (frequencyGhz < 40) return FrequencyBand::KA_BAND;
    if (frequencyGhz < 75) return FrequencyBand::Q_V_BAND;
    return FrequencyBand::W_BAND;
}

double NTNChannelModel::calculateRainPathLength(double elevationDeg, double rainHeightKm) {
    double elevationRad = elevationDeg * M_PI / 180.0;
    return rainHeightKm / std::max(0.1, sin(elevationRad));
}

std::pair<double, double> NTNChannelModel::getRainCoefficients(double frequencyGhz) {
    // ITU-R P.838-3 specific rain attenuation coefficients
    double f = frequencyGhz;

    if (f < 4.0) {
        return {0.0001, 1.0};
    } else if (f >= 4.0 && f < 12.0) {
        return {0.002 * (f - 3.0), 1.15};
    } else if (f >= 12.0 && f < 20.0) {
        return {0.035, 1.12};
    } else if (f >= 20.0 && f <= 32.0) {
        // Ka-band (28 GHz nominal): k_H=0.1872, k_V=0.1678 -> circular average k=0.1775, alpha=1.0142
        return {0.1775, 1.0142};
    } else if (f > 32.0 && f <= 50.0) {
        // Q-band (40 GHz): k ~ 0.385, alpha ~ 0.945
        return {0.385, 0.945};
    } else {
        // V/W-band
        return {0.650, 0.880};
    }
}

double NTNChannelModel::getCloudAttenuationCoefficient(double frequencyGhz, double temperature) {
    // ITU-R P.840-8
    // Simplified: K = a * f^2 / (1 + (f/b)^2) * exp(-c/T)
    double f = frequencyGhz;
    double T = temperature + 273.15;  // Kelvin
    
    double a = 0.001;
    double b = 20.0;
    double c = 100.0;
    
    return a * f * f / (1.0 + f * f / (b * b)) * exp(-c / T);
}

double NTNChannelModel::calculateWaterVaporDensity(double temperature, double humidity) {
    // Water vapor density in g/m^3
    // Using Magnus formula approximation
    double T = temperature;
    double es = 6.112 * exp(17.67 * T / (T + 243.5));  // Saturation vapor pressure (hPa)
    double e = humidity / 100.0 * es;
    double rho = 216.7 * e / (T + 273.15);  // g/m^3
    return rho;
}

} // namespace ntn
} // namespace artery