#ifndef ARTERY_NTN_UNIFIED_MOBILITY_MANAGER_H
#define ARTERY_NTN_UNIFIED_MOBILITY_MANAGER_H

#include <inet/common/geometry/common/Coord.h>
#include <omnetpp.h>
#include <vector>
#include <map>
#include <string>

namespace artery {
namespace nr { class NRManager; }
namespace ntn {

class ConstellationManager;

/**
 * @brief Unified Mobility Manager for Terrestrial-NTN Handovers
 * 
 * Manages seamless handovers between:
 * - Terrestrial 5G NR (gNBs)
 * - NTN LEO Satellites
 * - Ground Stations
 * 
 * Implements 3GPP TS 38.300 / TR 37.340 dual connectivity
 */
class UnifiedMobilityManager : public omnetpp::cSimpleModule {
public:
    enum class NetworkType {
        TERRESTRIAL_NR,
        NTN_LEO,
        NTN_GEO,
        GROUND_STATION
    };
    
    enum class HandoverTrigger {
        SIGNAL_STRENGTH,
        ELEVATION_ANGLE,
        LOAD_BALANCING,
        QOS_REQUIREMENT,
        USER_PREFERENCE,
        NETWORK_INITIATED
    };
    
    enum class HandoverType {
        INTRA_NR,           // gNB to gNB
        INTER_NR_NTN,       // NR to NTN (or NTN to NR)
        INTRA_NTN,          // Satellite to satellite
        NTN_TO_GS,          // Satellite to ground station
        MAKE_BEFORE_BREAK,  // Dual connectivity handover
        HARD_HANDOVER       // Break before make
    };
    
    struct NetworkNode {
        std::string id;
        NetworkType type;
        inet::Coord position;
        double altitude = 0;
        // Capabilities
        double maxThroughputMbps = 0;
        double latencyMs = 0;
        bool supportsQoS = false;
        std::vector<std::string> supportedSlices;
        // Current load
        double currentLoad = 0;  // 0-1
        int connectedUEs = 0;
    };
    
    struct UEContext {
        int ueId = 0;
        std::string currentNodeId;
        NetworkType currentNetwork = NetworkType::TERRESTRIAL_NR;
        std::string targetNodeId;
        NetworkType targetNetwork = NetworkType::NTN_LEO;
        
        // Signal measurements
        double currentRsrpDbm = -140;
        double currentRsrqDb = -20;
        double currentSinrDb = -20;
        double targetRsrpDbm = -140;
        double targetRsrqDb = -20;
        double targetSinrDb = -20;
        
        // NTN specific
        double currentElevationDeg = 0;
        double targetElevationDeg = 0;
        double elevationRateDegPerSec = 0;
        
        // Handover state
        bool handoverInProgress = false;
        HandoverType handoverType = HandoverType::HARD_HANDOVER;
        HandoverTrigger trigger = HandoverTrigger::SIGNAL_STRENGTH;
        omnetpp::simtime_t handoverStartTime = -1;
        int preparationPhase = 0;  // 0=not started, 1=measurement, 2=decision, 3=execution
        
        // Dual connectivity
        bool dualConnectivityActive = false;
        double nrRatio = 1.0;  // 0=all NTN, 1=all NR
        std::string nrNodeId;
        std::string ntnNodeId;
        
        // QoS requirements
        double requiredLatencyMs = 100;
        double requiredThroughputMbps = 10;
        double requiredReliability = 0.99;
        std::string sliceName = "embb";
    };
    
    struct HandoverPolicy {
        // Thresholds
        double rsrpThresholdDbm = -110;
        double rsrqThresholdDb = -15;
        double sinrThresholdDb = -5;
        double elevationThresholdDeg = 25;
        double elevationMinDeg = 15;
        
        // Hysteresis and timing
        double hysteresisDb = 3.0;
        double timeToTriggerMs = 160;
        double maxHandoverDurationMs = 50;
        
        // Make-before-break
        bool makeBeforeBreak = true;
        double mbBOverlapMs = 20;
        
        // Load balancing
        double loadThreshold = 0.8;
        bool loadBalancingEnabled = true;
        
        // QoS-based
        bool qosBasedSteering = true;
    };

protected:
    // Configuration
    HandoverPolicy policy;
    bool dualConnectivityEnabled = true;
    
    // Network topology
    std::map<std::string, NetworkNode> networkNodes;
    std::map<int, UEContext> ueContexts;
    
    // References to other managers
    ConstellationManager* constellationManager = nullptr;
    nr::NRManager* nrManager = nullptr;
    
    // Timers
    omnetpp::cMessage* evaluationTimer = nullptr;
    double evaluationIntervalMs = 100;
    
    // Signals
    omnetpp::simsignal_t handoverTriggeredSignal;
    omnetpp::simsignal_t handoverCompletedSignal;
    omnetpp::simsignal_t handoverFailedSignal;
    omnetpp::simsignal_t dualConnectivityChangedSignal;
    omnetpp::simsignal_t trafficSteeringSignal;
    omnetpp::simsignal_t ueMeasurementSignal;
    
    // Statistics
    long totalHandovers = 0;
    long successfulHandovers = 0;
    long failedHandovers = 0;
    long dualConnectivityActivations = 0;
    long trafficSteeringEvents = 0;

    virtual void initialize(int stage) override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
    virtual void finish() override;
    
    // Network topology management
    void registerNetworkNode(const NetworkNode& node);
    void unregisterNetworkNode(const std::string& nodeId);
    void updateNetworkNode(const std::string& nodeId, const NetworkNode& node);
    
    // UE management
    void registerUE(int ueId, const UEContext& context);
    void unregisterUE(int ueId);
    void updateUEMeasurements(int ueId, const UEContext& measurements);
    
    // Handover evaluation
    void evaluateAllUEs();
    void evaluateUE(int ueId);
    bool shouldTriggerHandover(const UEContext& ue);
    HandoverType determineHandoverType(const UEContext& ue, const std::string& targetNodeId);
    HandoverTrigger determineHandoverTrigger(const UEContext& ue);
    
    // Handover execution
    void initiateHandover(int ueId, const std::string& targetNodeId, HandoverType type, HandoverTrigger trigger);
    void executeHandover(int ueId);
    void completeHandover(int ueId, bool success);
    void abortHandover(int ueId, const std::string& reason);
    
    // Dual connectivity
    void evaluateDualConnectivity(int ueId);
    void activateDualConnectivity(int ueId, const std::string& nrNodeId, const std::string& ntnNodeId);
    void deactivateDualConnectivity(int ueId);
    void updateBearerSplit(int ueId, double nrRatio);
    
    // Traffic steering
    void evaluateTrafficSteering(int ueId);
    double calculateUtility(const UEContext& ue, const NetworkNode& node);
    void steerTraffic(int ueId, double nrRatio, const std::string& reason);
    
    // NTN-specific
    void evaluateSatelliteVisibility(int ueId);
    void predictSatellitePasses(int ueId);
    
    // Utilities
    NetworkNode* findBestTargetNode(const UEContext& ue, NetworkType preferredType = NetworkType::TERRESTRIAL_NR);
    double calculateHandoverCost(const UEContext& ue, const NetworkNode& target);
    void notifyNetworkNodes(const UEContext& ue, const std::string& event);
    
    // Configuration
    void configureFromYAML(const std::string& yamlContent);
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_UNIFIED_MOBILITY_MANAGER_H