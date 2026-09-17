#ifndef ARTERY_NR_NRMANAGER_H
#define ARTERY_NR_NRMANAGER_H

#include <inet/common/geometry/common/Coord.h>
#include <omnetpp.h>
#include <vector>
#include <string>
#include <map>
#include <memory>

namespace artery {
namespace nr {

/**
 * @brief NR Manager for 5G/6G Terrestrial Network Integration
 * 
 * Interfaces with Simu5G framework for:
 * - gNB management (macro, micro, mmWave)
 * - Carrier aggregation
 * - Beamforming and MIMO
 * - NR channel models (3GPP 38.901)
 * - Dual connectivity with NTN
 * - Network slicing
 */
class NRManager : public omnetpp::cSimpleModule {
public:
    enum class GNBType {
        MACRO,
        MICRO,
        MMWAVE,
        PICO
    };
    
    enum class Numerology {
        N0 = 0,   // 15 kHz SCS
        N1 = 1,   // 30 kHz SCS
        N2 = 2,   // 60 kHz SCS
        N3 = 3,   // 120 kHz SCS
        N4 = 4    // 240 kHz SCS
    };
    
    struct GNBConfig {
        std::string name;
        GNBType type = GNBType::MACRO;
        inet::Coord position;
        double heightM = 25;
        double txPowerDbm = 46;
        double antennaGainDbi = 18;
        double beamwidthDeg = 65;
        double frequencyGhz = 3.5;
        double bandwidthMhz = 100;
        Numerology numerology = Numerology::N1;
        int mimoLayers = 4;
        int numBeams = 8;
        bool beamformingEnabled = true;
        
        // Carrier aggregation
        bool caEnabled = true;
        std::vector<std::pair<double, double>> componentCarriers;  // (freq GHz, bw MHz)
    };
    
    struct UEConfig {
        int ueId = 0;
        inet::Coord position;
        double maxTxPowerDbm = 23;
        int maxMimoLayers = 2;
        bool caEnabled = true;
        bool dualConnectivityEnabled = false;
        std::vector<int> supportedBands;  // NR bands
    };
    
    struct SliceConfig {
        std::string name;
        int priority = 1;
        double maxBitrateMbps = 1000;
        double guaranteedBitrateMbps = 0;
        double maxLatencyMs = 100;
        double reliability = 0.999;
        std::string qci;  // 5QI identifier
    };
    
    struct LinkBudgetParams {
        double frequencyGhz = 3.5;
        double bandwidthMhz = 100;
        double txPowerDbm = 46;
        double rxNoiseFigureDb = 5;
        double implementationLossDb = 3;
        double bodyLossDb = 3;
        double shadowMarginDb = 8;
    };

protected:
    // Configuration
    std::string simu5gConfigFile;
    std::string channelModelType = "UMa";  // UMa, UMi, RMa, InH
    bool carrierAggregationEnabled = true;
    bool beamformingEnabled = true;
    bool mimoEnabled = true;
    bool networkSlicingEnabled = true;
    bool dualConnectivityEnabled = false;
    
    // gNBs managed by this NRManager
    std::map<std::string, GNBConfig> gnbs;
    std::map<int, UEConfig> ues;
    std::vector<SliceConfig> slices;
    LinkBudgetParams linkParams;
    
    // Simu5G integration
    omnetpp::cModule* binderModule = nullptr;
    omnetpp::cModule* carrierAggregationModule = nullptr;
    omnetpp::cModule* macModule = nullptr;
    
    // Runtime state
    std::map<std::string, omnetpp::cModule*> gnbModules;
    std::map<int, omnetpp::cModule*> ueModules;
    
    // Signals
    omnetpp::simsignal_t gnbDeployedSignal;
    omnetpp::simsignal_t ueAttachedSignal;
    omnetpp::simsignal_t handoverSignal;
    omnetpp::simsignal_t caConfiguredSignal;
    omnetpp::simsignal_t beamformedSignal;
    omnetpp::simsignal_t sliceCreatedSignal;
    omnetpp::simsignal_t linkQualitySignal;
    omnetpp::simsignal_t throughputSignal;
    omnetpp::simsignal_t latencySignal;
    
    // Statistics
    long totalHandovers = 0;
    long totalCAConfigurations = 0;
    double totalThroughputGb = 0;

    virtual void initialize(int stage) override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
    virtual void finish() override;
    
    // Simu5G integration
    void findSimu5GModules();
    void configureBinder();
    void configureCarrierAggregation();
    void configureMAC();
    
    // gNB management
    void deployGNBs();
    void createGNBModule(const GNBConfig& config);
    void configureGNB(const std::string& gnbName);
    
    // UE management
    void attachUE(int ueId, const std::string& gnbName);
    void detachUE(int ueId);
    void handoverUE(int ueId, const std::string& fromGNB, const std::string& toGNB);
    
    // Carrier aggregation
    void configureCA(int ueId, const std::vector<std::pair<double, double>>& carriers);
    void updateCAConfiguration(int ueId);
    
    // Beamforming
    void configureBeamforming(const std::string& gnbName);
    void updateBeamDirection(const std::string& gnbName, int ueId, double azimuth, double elevation);
    
    // MIMO
    void configureMIMO(const std::string& gnbName, int ueId, int layers);
    
    // Channel model
    double calculatePathLoss(const inet::Coord& txPos, const inet::Coord& rxPos, 
                             double frequencyGhz, double txHeight, double rxHeight);
    double calculateShadowing(double distanceKm);
    double calculateFastFading();
    
    // Link budget
    double calculateLinkBudget(const GNBConfig& gnb, const UEConfig& ue);
    double calculateSNR(double receivedPowerDbm, double bandwidthHz);
    double calculateDataRate(double snrDb, double bandwidthHz, int mimoLayers);
    
    // Network slicing
    void createSlice(const SliceConfig& slice);
    void assignUEToSlice(int ueId, const std::string& sliceName);
    
    // Dual connectivity with NTN
    void configureDualConnectivity(int ueId, bool enable);
    void splitBearer(int ueId, double nrRatio);  // 0=all NTN, 1=all NR
    void evaluateTrafficSteering(int ueId);
    
    // Configuration from YAML
    void configureFromYAML(const std::string& yamlContent);
    
    // Simu5G module access
    omnetpp::cModule* getSimu5GModule(const std::string& path);
    template<typename T>
    T* getSimu5GModuleAs(const std::string& path);
};

} // namespace nr
} // namespace artery

#endif // ARTERY_NR_NRMANAGER_H