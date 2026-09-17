#ifndef ARTERY_NTN_CONSTELLATION_MANAGER_H
#define ARTERY_NTN_CONSTELLATION_MANAGER_H

#include <inet/common/geometry/common/Coord.h>
#include <omnetpp.h>
#include <vector>
#include <string>
#include <map>
#include <memory>

namespace artery {
namespace ntn {

/**
 * @brief Manages a LEO satellite constellation
 * 
 * Supports Walker Delta/Star constellations, Starlink-like shells,
 * and custom TLE-based deployments. Handles ISL topology,
 * visibility calculations, and handover triggers.
 */
class ConstellationManager : public omnetpp::cSimpleModule {
public:
    struct OrbitalElements {
        int globalId = 0;
        double semiMajorAxisKm;      // a
        double eccentricity;         // e
        double inclinationDeg;       // i
        double raanDeg;              // RAAN (Ω)
        double argPerigeeDeg;        // ω
        double meanAnomalyDeg;       // M0
        double epoch;                // TLE epoch (days since 1950)
        double meanMotionRevPerDay;  // n
        double bstar;                // Drag term
    };

    struct SatelliteInfo {
        std::string name;
        int planeId;
        int satIdInPlane;
        int globalId;
        OrbitalElements elements;
        omnetpp::cModule* module = nullptr;
        // Runtime state
        inet::Coord position;
        inet::Coord velocity;
        std::vector<int> visibleSats;      // ISL neighbors
        std::vector<int> visibleGroundStations;
        std::vector<int> visibleUEs;
        double lastVisibilityUpdate = 0;
    };

    struct GroundStationInfo {
        std::string name;
        double lat, lon, alt;
        omnetpp::cModule* module = nullptr;
        double elevationMaskDeg = 10.0;
        std::vector<int> visibleSats;
    };

    struct ISLLink {
        int satA, satB;
        double distanceKm;
        double elevationDeg;
        bool active = false;
        omnetpp::simtime_t establishedAt = -1;
        omnetpp::simtime_t lastQualityUpdate = -1;
        double linkQuality = 1.0;  // 0-1
    };

protected:
    // Configuration
    std::string constellationConfigFile;
    std::string constellationType;  // walker_delta, walker_star, starlink_shell, custom
    
    // Walker Delta parameters
    int walkerT = 0;  // Total satellites
    int walkerP = 0;  // Number of planes
    int walkerF = 0;  // Phasing parameter
    double walkerAltitudeKm = 550;
    double walkerInclinationDeg = 53.0;
    
    // Starlink shell parameters
    struct ShellConfig {
        std::string name;
        double altitudeKm;
        double inclinationDeg;
        int numPlanes;
        int satsPerPlane;
        int phaseOffset;
    };
    std::vector<ShellConfig> shells;
    
    // ISL configuration
    bool islEnabled = true;
    std::string islType = "laser";
    double islMaxRangeKm = 5000;
    int islPortsPerSat = 4;
    double islWavelengthNm = 1550;
    double islFrequencyGhz = 60;
    double islTxPowerDbm = 20;
    double islRxSensitivityDbm = -40;
    double islPointingAccuracyDeg = 0.01;
    double islAcquisitionTimeMs = 100;
    
    // Satellite defaults
    std::string satNicType = "space_veins.modules.nic.SatelliteNic";
    std::string satIslNicType = "artery.ntn.ISLNic";
    std::string satMobilityType = "space_veins.modules.mobility.SGP4Mobility";
    std::string satManagerType = "artery.ntn.LEO_SatelliteManager";
    double satTxPowerDbm = 30;
    double satNoiseFigureDb = 3;
    double satFrequencyGhz = 28;
    double satBandwidthMhz = 500;
    
    // Ground station defaults
    struct GSConfig {
        std::string name;
        double lat, lon, alt;
        double elevationMaskDeg = 10.0;
        double feederFreqGhz = 28;
        double feederBwMhz = 1000;
        double userFreqGhz = 28;
        double userBwMhz = 500;
    };
    std::vector<GSConfig> groundStations;
    
    // Simulation
    double visibilityUpdateInterval = 1.0;  // seconds
    omnetpp::cMessage* visibilityUpdateTimer = nullptr;
    
    // Runtime state
    std::vector<SatelliteInfo> satellites;
    std::vector<GroundStationInfo> gstations;
    std::vector<ISLLink> islLinks;
    std::map<std::string, int> satNameToIndex;
    std::map<std::string, int> gsNameToIndex;
    
    // Statistics
    long totalHandovers = 0;
    long totalISLHandoffs = 0;
    omnetpp::simsignal_t satDeployedSignal;
    omnetpp::simsignal_t islEstablishedSignal;
    omnetpp::simsignal_t islBrokenSignal;
    omnetpp::simsignal_t handoverSignal;
    omnetpp::simsignal_t visibilitySignal;

    virtual void initialize(int stage) override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
    virtual void finish() override;
    
    // Configuration loading
    void loadConfiguration();
    void parseWalkerDelta(const std::string& config);
    void parseStarlinkShells(const std::string& config);
    void parseCustomTLE(const std::string& config);
    
    // Constellation deployment
    void deployConstellation();
    void deployWalkerDelta();
    void deployStarlinkShells();
    void deployCustomTLE();
    void createSatelliteModule(const SatelliteInfo& sat);
    void createGroundStationModules();
    
    // Orbital mechanics
    OrbitalElements computeWalkerElements(int planeIdx, int satIdx, int P, int T, int F, 
                                          double altitudeKm, double inclinationDeg);
    OrbitalElements computeStarlinkElements(const ShellConfig& shell, int planeIdx, int satIdx);
    void elementsToTLE(const OrbitalElements& el, std::string& line1, std::string& line2);
    
    // Visibility & ISL
    void scheduleVisibilityUpdates();
    void updateVisibility();
    void updateSatellitePositions();
    inet::Coord computePositionFromElements(const OrbitalElements& el, double time);
    void computeISLTopology();
    void computeGroundStationVisibility();
    void computeUEVisibility();  // For user terminals
    bool checkLOS(const inet::Coord& posA, const inet::Coord& posB, double minElevationDeg = 0);
    double calculateElevation(const inet::Coord& satPos, const inet::Coord& gsPos);
    double calculateRange(const inet::Coord& posA, const inet::Coord& posB);
    double calculateLinkBudget(const ISLLink& link);
    
    // ISL management
    void establishISL(int satA, int satB);
    void breakISL(int satA, int satB);
    void updateISLQuality();
    
    // Handover support
    void triggerHandover(int ueId, int fromSat, int toSat);
    bool evaluateHandover(int ueId, int currentSat, int candidateSat);
    
public:
    // Utilities
    SatelliteInfo* getSatelliteByName(const std::string& name);
    SatelliteInfo* getSatelliteById(int globalId);
    GroundStationInfo* getGroundStationByName(const std::string& name);
    std::vector<int> findVisibleSatellites(const inet::Coord& observerPos, double minElevationDeg = 10.0);
    inet::Coord getSatellitePosition(const SatelliteInfo& sat);
    inet::Coord getGroundStationPosition(const GroundStationInfo& gs);

protected:
    // Signals
    void emitSatelliteDeployed(const SatelliteInfo& sat);
    void emitISLEstablished(int satA, int satB);
    void emitISLBroken(int satA, int satB);
    void emitHandover(int ueId, int fromSat, int toSat, const std::string& reason);
    
    // Configuration from YAML (called by scenario generator)
    void configureFromYAML(const std::string& yamlContent);
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_CONSTELLATION_MANAGER_H