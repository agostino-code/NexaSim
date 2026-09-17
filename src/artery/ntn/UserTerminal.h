#ifndef ARTERY_NTN_USER_TERMINAL_H
#define ARTERY_NTN_USER_TERMINAL_H

#include <inet/common/geometry/common/Coord.h>
#include <omnetpp.h>
#include <vector>
#include <string>
#include <map>
#include <memory>
#include <complex>

namespace artery {
namespace ntn {

class ConstellationManager;

/**
 * @brief User Terminal (Starlink Dish) with Phased Array Antenna
 * 
 * Features:
 * - Electronic beam steering (phased array)
 * - Satellite tracking using TLE/ephemeris
 * - Make-before-break handover between satellites
 * - Link budget with rain fade, atmospheric loss
 * - Dual connectivity with terrestrial 5G
 */
class UserTerminal : public omnetpp::cSimpleModule {
public:
    enum class TerminalState {
        IDLE,
        SEARCHING,
        ACQUIRING,
        TRACKING,
        HANDOVER_PREPARE,
        HANDOVER_EXECUTE,
        CONNECTED
    };
    
    enum class BeamformingMode {
        ANALOG,
        DIGITAL,
        HYBRID
    };

protected:
    struct PhasedArrayConfig {
        int numElements = 64;           // 8x8 array
        double elementSpacingWavelengths = 0.5;
        double maxScanAngleDeg = 60;    // Max boresight angle
        double beamwidthDeg = 10;       // 3dB beamwidth
        double maxGainDbi = 30;
        double sidelobeLevelDb = -13;   // Typical for uniform array
        BeamformingMode mode = BeamformingMode::HYBRID;
        int numRFChains = 8;            // For hybrid beamforming
    };
    
    struct SatelliteTrackInfo {
        int satId = -1;
        std::string satName;
        inet::Coord position;
        inet::Coord velocity;
        double elevationDeg = 0;
        double azimuthDeg = 0;
        double rangeKm = 0;
        double elevationRateDegPerSec = 0;
        double linkQuality = 0;
        double snrDb = 0;
        double dataRateMbps = 0;
        omnetpp::simtime_t lastUpdate = -1;
        bool isVisible = false;
        bool isCurrent = false;

        bool isValid() const { return satId >= 0; }
    };
    
    struct HandoverInfo {
        int fromSatId = -1;
        int toSatId = -1;
        TerminalState previousState = TerminalState::IDLE;
        omnetpp::simtime_t startedAt = -1;
        omnetpp::simtime_t prepareDeadline = -1;
        omnetpp::simtime_t executeDeadline = -1;
        bool makeBeforeBreak = true;
        std::string triggerReason;
    };
    
    struct LinkBudgetParams {
        double frequencyGhz = 28;       // Ka-band
        double bandwidthMhz = 500;
        double txPowerDbm = 30;
        double rxNoiseFigureDb = 3;
        double implementationLossDb = 3;
        double rainMarginDb = 10;       // For 99.9% availability
        double polarizationLossDb = 0.5;
        double pointingLossDb = 1.0;
    };
    
    // Configuration
    PhasedArrayConfig arrayConfig;
    LinkBudgetParams linkParams;
    int terminalId = 0;
    std::string terminalType = "residential";  // residential | business | mobility | maritime | aviation
    
    // Handover parameters
    double handoverElevationThresholdDeg = 25;  // Start handover prep at this elevation
    double handoverElevationMinDeg = 15;        // Execute handover at this elevation
    double handoverHysteresisDb = 3;
    double handoverTimeToTriggerMs = 160;
    bool makeBeforeBreak = true;
    double maxHandoverDurationMs = 50;
    
    // Dual connectivity
    bool dualConnectivityEnabled = false;
    std::string terrestrialRat = "nr";  // nr | lte
    double terrestrialRsrpThresholdDbm = -110;
    
    // Runtime state
    TerminalState state = TerminalState::IDLE;
    SatelliteTrackInfo currentSat;
    std::vector<SatelliteTrackInfo> candidateSats;  // Visible satellites
    HandoverInfo handover;
    omnetpp::cMessage* trackingTimer = nullptr;
    omnetpp::cMessage* handoverTimer = nullptr;
    omnetpp::cMessage* measurementTimer = nullptr;
    omnetpp::cMessage* trafficTimer = nullptr;
    
    // Mobility
    omnetpp::cModule* mobilityModule = nullptr;
    inet::Coord currentPosition;
    inet::Coord currentVelocity;
    
    // Constellation manager reference
    ConstellationManager* constellationManager = nullptr;
    
    // Terrestrial NR connection (for dual connectivity)
    omnetpp::cModule* terrestrialConnection = nullptr;
    double terrestrialRsrpDbm = -140;
    double terrestrialSnrDb = -20;
    
    // Signals
    omnetpp::simsignal_t stateChangedSignal;
    omnetpp::simsignal_t satAcquiredSignal;
    omnetpp::simsignal_t satLostSignal;
    omnetpp::simsignal_t handoverStartedSignal;
    omnetpp::simsignal_t handoverCompletedSignal;
    omnetpp::simsignal_t handoverFailedSignal;
    omnetpp::simsignal_t linkQualitySignal;
    omnetpp::simsignal_t dataRateSignal;
    omnetpp::simsignal_t beamDirectionSignal;
    omnetpp::simsignal_t elevationSignal;
    
    // Statistics
    long totalHandovers = 0;
    long successfulHandovers = 0;
    long failedHandovers = 0;
    double totalDataGb = 0;
    long packetsSentTotal = 0;
    long packetsReceivedTotal = 0;
    long packetsDroppedTotal = 0;
    double latencySumMs = 0;
    double lastLatencyMs = 0;
    double jitterSumMs = 0;
    omnetpp::simtime_t connectedTime = 0;
    omnetpp::simtime_t lastStateChange = 0;

    virtual void initialize(int stage) override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
    virtual void finish() override;
    void scheduleTrafficTick();
    void handleTrafficTick();
    
    // State machine
    void changeState(TerminalState newState);
    void handleIdleState();
    void handleSearchingState();
    void handleAcquiringState();
    void handleTrackingState();
    void handleHandoverPrepareState();
    void handleHandoverExecuteState();
    void handleConnectedState();
    
    // Satellite tracking
    void startSatelliteSearch();
    void updateVisibleSatellites();
    void selectBestSatellite();
    void trackSatellite(int satId);
    void predictSatellitePass(int satId, omnetpp::simtime_t horizon);
    void calculateOrbitalParameters(int satId);
    
    // Phased array beamforming
    void steerBeam(double elevationDeg, double azimuthDeg);
    std::vector<std::complex<double>> computeBeamWeights(double elevationDeg, double azimuthDeg);
    double calculateArrayGain(double elevationDeg, double azimuthDeg, double targetElev, double targetAz);
    double calculatePointingLoss(double pointingErrorDeg);
    void updateBeamforming();
    
    // Link budget
    double calculateLinkBudget(const SatelliteTrackInfo& sat);
    double calculateRainAttenuation(double elevationDeg, double frequencyGhz);
    double calculateAtmosphericLoss(double elevationDeg, double frequencyGhz);
    double calculateFreeSpaceLoss(double rangeKm, double frequencyGhz);
    double calculateSnr(double receivedPowerDbm);
    double calculateDataRate(double snrDb, double bandwidthHz);
    
    // Handover management
    void evaluateHandover();
    void prepareHandover(int fromSat, int toSat, const std::string& reason);
    void executeHandover();
    void abortHandover(const std::string& reason);
    bool checkHandoverConditions(int fromSat, int toSat);
    
    // Dual connectivity
    void evaluateDualConnectivity();
    void configureTerrestrialConnection();
    void splitBearer(double nrRatio);  // 0=all sat, 1=all terrestrial
    
    // Timers
    void scheduleTrackingUpdate();
    void scheduleMeasurementUpdate();
    void scheduleHandoverTimeout();
    
    // Utilities
    inet::Coord getCurrentPosition();
    inet::Coord getCurrentVelocity();
    void notifyConstellationManager(const std::string& event, int satId);
    void notifyTerrestrialNetwork(const std::string& event);
    
    // Signal emission
    void emitStateChange(TerminalState oldState, TerminalState newState);
    void emitHandoverEvent(int fromSat, int toSat, bool success);
    
    // Configuration from YAML
    void configureFromYAML(const std::string& yamlContent);
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_USER_TERMINAL_H