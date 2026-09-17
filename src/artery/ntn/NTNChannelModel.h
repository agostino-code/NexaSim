#ifndef ARTERY_NTN_NTN_CHANNEL_MODEL_H
#define ARTERY_NTN_NTN_CHANNEL_MODEL_H

#include <omnetpp.h>
#include <cmath>

namespace artery {
namespace ntn {

/**
 * @brief NTN Channel Model based on 3GPP TR 38.811
 * 
 * Implements:
 * - LOS/NLOS probability based on elevation angle
 * - Path loss: Free space + atmospheric (gas, rain, cloud) + scintillation
 * - Shadowing: Correlated log-normal
 * - Doppler shift for LEO satellites
 * - Polarization effects
 * - Rain fade (ITU-R P.618)
 * - Cloud/fog attenuation (ITU-R P.840)
 * - Gaseous absorption (ITU-R P.676)
 * - Scintillation (ITU-R P.1814)
 */
class NTNChannelModel {
public:
    enum class FrequencyBand {
        L_BAND,    // 1-2 GHz
        S_BAND,    // 2-4 GHz
        C_BAND,    // 4-8 GHz
        KU_BAND,   // 12-18 GHz
        KA_BAND,   // 26.5-40 GHz
        Q_V_BAND,  // 33-75 GHz
        W_BAND     // 75-110 GHz
    };
    
    enum class Environment {
        URBAN,
        SUBURBAN,
        RURAL,
        MARITIME,
        AERONAUTICAL,
        DESERT,
        TROPICAL
    };
    
    struct ChannelParams {
        double frequencyGhz = 28.0;
        double elevationDeg = 30.0;
        double altitudeKm = 550.0;
        FrequencyBand band = FrequencyBand::KA_BAND;
        Environment env = Environment::SUBURBAN;
        
        // Rain parameters
        double rainRateMmPerH = 25.0;  // mm/h (0.01% exceedance)
        double rainHeightKm = 4.0;
        
        // Cloud parameters
        double cloudLiquidWater = 0.5;  // kg/m^2
        double cloudTempC = 0.0;
        
        // Scintillation
        double scintillationSigma = 1.0;  // dB
        
        // Polarization
        double polarizationLossDb = 0.5;
    };
    
    struct PathLossResult {
        double totalLossDb = 0;
        double freeSpaceLossDb = 0;
        double atmosphericLossDb = 0;
        double rainLossDb = 0;
        double cloudLossDb = 0;
        double scintillationLossDb = 0;
        double polarizationLossDb = 0;
        double losProbability = 0;
        double shadowingDb = 0;
        double dopplerShiftHz = 0;
    };

    /**
     * Calculate complete path loss for NTN link
     * @param params Channel parameters
     * @param satelliteVelocityKmps Satellite velocity in km/s
     * @param groundVelocityKmps Ground terminal velocity in km/s
     * @return PathLossResult with all components
     */
    static PathLossResult calculatePathLoss(const ChannelParams& params,
                                             double satelliteVelocityKmps = 7.5,
                                             double groundVelocityKmps = 0.0);
    
    /**
     * Calculate LOS probability based on 3GPP TR 38.811
     * @param elevationDeg Elevation angle in degrees
     * @param environment Environment type
     * @return LOS probability (0-1)
     */
    static double calculateLOSProbability(double elevationDeg, Environment env);
    
    /**
     * Calculate free space path loss
     * @param distanceKm Distance in km
     * @param frequencyGhz Frequency in GHz
     * @return FSPL in dB
     */
    static double calculateFSPL(double distanceKm, double frequencyGhz);
    
    /**
     * Calculate slant range from altitude and elevation
     * @param altitudeKm Satellite altitude in km
     * @param elevationDeg Elevation angle in degrees
     * @return Slant range in km
     */
    static double calculateSlantRange(double altitudeKm, double elevationDeg);
    
    /**
     * Calculate atmospheric gaseous absorption (ITU-R P.676)
     * @param elevationDeg Elevation angle
     * @param frequencyGhz Frequency in GHz
     * @return Attenuation in dB
     */
    static double calculateGaseousAbsorption(double elevationDeg, double frequencyGhz);
    
    /**
     * Calculate rain attenuation (ITU-R P.618)
     * @param elevationDeg Elevation angle
     * @param frequencyGhz Frequency in GHz
     * @param rainRate Rain rate in mm/h
     * @return Rain attenuation in dB
     */
    static double calculateRainAttenuation(double elevationDeg, double frequencyGhz, double rainRate);
    
    /**
     * Calculate cloud/fog attenuation (ITU-R P.840)
     * @param elevationDeg Elevation angle
     * @param frequencyGhz Frequency in GHz
     * @param liquidWater Cloud liquid water content in kg/m^2
     * @param temperature Temperature in Celsius
     * @return Cloud attenuation in dB
     */
    static double calculateCloudAttenuation(double elevationDeg, double frequencyGhz, 
                                            double liquidWater, double temperature);
    
    /**
     * Calculate scintillation loss (ITU-R P.1814)
     * @param elevationDeg Elevation angle
     * @param frequencyGhz Frequency in GHz
     * @param sigma Scintillation standard deviation in dB
     * @return Scintillation loss in dB
     */
    static double calculateScintillation(double elevationDeg, double frequencyGhz, double sigma);
    
    /**
     * Calculate Doppler shift for LEO satellite
     * @param satelliteVelocityKmps Satellite velocity in km/s
     * @param groundVelocityKmps Ground terminal velocity in km/s
     * @param frequencyGhz Carrier frequency in GHz
     * @param elevationDeg Elevation angle
     * @param azimuthDeg Azimuth angle
     * @return Doppler shift in Hz
     */
    static double calculateDopplerShift(double satelliteVelocityKmps, double groundVelocityKmps,
                                        double frequencyGhz, double elevationDeg, double azimuthDeg);
    
    /**
     * Calculate shadowing (log-normal)
     * @param distanceKm Distance in km
     * @param environment Environment type
     * @return Shadowing in dB (random variable)
     */
    static double calculateShadowing(double distanceKm, Environment env);
    
    /**
     * Get frequency band from GHz
     */
    static FrequencyBand getFrequencyBand(double frequencyGhz);
    
    /**
     * Calculate distance to rain height
     */
    static double calculateRainPathLength(double elevationDeg, double rainHeightKm);
    
    /**
     * Specific attenuation coefficient for rain (ITU-R P.838)
     */
    static std::pair<double, double> getRainCoefficients(double frequencyGhz);
    
    /**
     * Specific attenuation for cloud (ITU-R P.840)
     */
    static double getCloudAttenuationCoefficient(double frequencyGhz, double temperature);
    
    /**
     * Water vapor density calculation
     */
    static double calculateWaterVaporDensity(double temperature, double humidity);
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_NTN_CHANNEL_MODEL_H