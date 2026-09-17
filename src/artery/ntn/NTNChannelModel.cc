#include "artery/ntn/NTNChannelModel.h"
#include <omnetpp.h>
#include <cmath>
#include <random>
#include <algorithm>

namespace artery {
namespace ntn {

NTNChannelModel::PathLossResult NTNChannelModel::calculatePathLoss(
    const ChannelParams& params,
    double satelliteVelocityKmps,
    double groundVelocityKmps) {
    
    PathLossResult result;
    
    // Slant range
    double slantRange = calculateSlantRange(params.altitudeKm, params.elevationDeg);
    
    // Free space loss
    result.freeSpaceLossDb = calculateFSPL(slantRange, params.frequencyGhz);
    
    // LOS probability
    result.losProbability = calculateLOSProbability(params.elevationDeg, params.env);
    
    // Atmospheric losses
    result.atmosphericLossDb = calculateGaseousAbsorption(params.elevationDeg, params.frequencyGhz);
    
    // Rain attenuation
    result.rainLossDb = calculateRainAttenuation(params.elevationDeg, params.frequencyGhz, params.rainRateMmPerH);
    
    // Cloud attenuation
    result.cloudLossDb = calculateCloudAttenuation(params.elevationDeg, params.frequencyGhz, 
                                                    params.cloudLiquidWater, params.cloudTempC);
    
    // Scintillation
    result.scintillationLossDb = calculateScintillation(params.elevationDeg, params.frequencyGhz, params.scintillationSigma);
    
    // Polarization loss
    result.polarizationLossDb = params.polarizationLossDb;
    
    // Shadowing
    result.shadowingDb = calculateShadowing(slantRange, params.env);
    
    // Doppler shift
    result.dopplerShiftHz = calculateDopplerShift(satelliteVelocityKmps, groundVelocityKmps,
                                                   params.frequencyGhz, params.elevationDeg, 0.0);
    
    // Total loss (statistical combination)
    // For LOS: FSPL + atmospheric + rain + cloud + scintillation + polarization + shadowing
    // For NLOS: additional diffraction loss
    double losLoss = result.freeSpaceLossDb + result.atmosphericLossDb + result.rainLossDb +
                     result.cloudLossDb + result.scintillationLossDb + result.polarizationLossDb +
                     result.shadowingDb;
    
    double nlosLoss = losLoss + 20.0;  // Additional NLOS loss (simplified)
    
    result.totalLossDb = result.losProbability * losLoss + (1.0 - result.losProbability) * nlosLoss;
    
    return result;
}

double NTNChannelModel::calculateLOSProbability(double elevationDeg, Environment env) {
    // 3GPP TR 38.811 Table 7.2-1: LOS probability models
    // P_LOS = min(1, (a * theta + b) / (c * theta + d))  or similar
    
    double theta = elevationDeg;
    double a, b, c, d;
    
    switch (env) {
        case Environment::URBAN:
            // Dense urban: lower LOS probability
            a = 0.3; b = 0.1; c = 0.1; d = 1.0;
            break;
        case Environment::SUBURBAN:
            a = 0.4; b = 0.15; c = 0.08; d = 1.0;
            break;
        case Environment::RURAL:
            a = 0.5; b = 0.2; c = 0.05; d = 1.0;
            break;
        case Environment::MARITIME:
            a = 0.6; b = 0.25; c = 0.04; d = 1.0;
            break;
        case Environment::AERONAUTICAL:
            a = 0.9; b = 0.05; c = 0.02; d = 1.0;
            break;
        case Environment::DESERT:
            a = 0.7; b = 0.2; c = 0.03; d = 1.0;
            break;
        case Environment::TROPICAL:
            a = 0.35; b = 0.1; c = 0.07; d = 1.0;
            break;
        default:
            a = 0.4; b = 0.15; c = 0.08; d = 1.0;
    }
    
    double pLos = (a * theta + b) / (c * theta + d);
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
    // ITU-R P.676 simplified
    // Oxygen and water vapor absorption
    
    // Zenith attenuation (dB)
    double freq = frequencyGhz;
    
    // Oxygen absorption (simplified from P.676)
    double oxygenZenith = 0.0;
    if (freq < 50) {
        oxygenZenith = 0.001 * freq * freq;  // Approximate
    } else {
        // 60 GHz oxygen band
        oxygenZenith = 15.0 / (1.0 + pow((freq - 60) / 5, 2));
    }
    
    // Water vapor absorption (simplified)
    double vaporZenith = 0.0;
    if (freq < 100) {
        vaporZenith = 0.002 * freq * freq / (1.0 + freq * freq / 40000.0);
    } else {
        // 22 GHz and 183 GHz water vapor lines
        vaporZenith = 0.5 * exp(-pow(freq - 22, 2) / 100) + 0.3 * exp(-pow(freq - 183, 2) / 1000);
    }
    
    // Slant path factor
    double elevationFactor = 1.0 / std::max(0.1, sin(elevationDeg * M_PI / 180.0));
    
    return (oxygenZenith + vaporZenith) * elevationFactor;
}

double NTNChannelModel::calculateRainAttenuation(double elevationDeg, double frequencyGhz, double rainRate) {
    // ITU-R P.618 / P.838 rain attenuation
    
    if (rainRate <= 0) return 0.0;
    
    // Specific attenuation coefficients (ITU-R P.838)
    auto [k, alpha] = getRainCoefficients(frequencyGhz);
    
    // Specific attenuation (dB/km)
    double gamma = k * pow(rainRate, alpha);
    
    // Effective path length through rain
    double rainHeight = 4.0;  // km (typical)
    double rainPathLength = calculateRainPathLength(elevationDeg, rainHeight);
    
    // Horizontal reduction factor
    double r = 1.0 / (1.0 + rainPathLength / (25.0 * pow(gamma, 0.5)));  // Simplified
    
    // Vertical adjustment factor
    double v = 1.0;  // Simplified
    
    // Total rain attenuation
    double attenuation = gamma * rainPathLength * r * v;
    
    return attenuation;
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

double NTNChannelModel::calculateShadowing(double distanceKm, Environment env) {
    // Log-normal shadowing
    // Standard deviation depends on environment
    double sigma;
    
    switch (env) {
        case Environment::URBAN: sigma = 8.0; break;
        case Environment::SUBURBAN: sigma = 6.0; break;
        case Environment::RURAL: sigma = 5.0; break;
        case Environment::MARITIME: sigma = 4.0; break;
        case Environment::AERONAUTICAL: sigma = 3.0; break;
        case Environment::DESERT: sigma = 4.5; break;
        case Environment::TROPICAL: sigma = 7.0; break;
        default: sigma = 6.0;
    }
    
    // Correlation distance
    double dCorr = 100.0;  // meters (typical)
    
    // Generate correlated shadowing (simplified: just return random value)
    static std::random_device rd;
    static std::mt19937 gen(rd());
    std::normal_distribution<> dist(0.0, sigma);
    
    return dist(gen);
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
    // ITU-R P.838-3 coefficients k and alpha
    // k = a * f^b, alpha = c * f^d + e
    // Simplified approximation for common bands
    
    double f = frequencyGhz;
    
    if (f < 10) {
        // L/S/C band - minimal rain
        return {0.0001, 1.0};
    } else if (f < 20) {
        // Ku band
        return {0.0003 * f, 1.1};
    } else if (f < 40) {
        // Ka band
        return {0.0002 * f, 1.15};
    } else {
        // Q/V band and above
        return {0.00015 * f, 1.2};
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