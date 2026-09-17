#include "artery/nr/NRManager.h"
#include <omnetpp.h>
#include <cmath>
#include <algorithm>
#include <fstream>
#include <sstream>

namespace artery {
namespace nr {

Define_Module(NRManager);

void NRManager::initialize(int stage) {
    if (stage == 0) {
        // Read parameters
        simu5gConfigFile = par("simu5gConfigFile").stringValue();
        channelModelType = par("channelModel").stringValue();
        carrierAggregationEnabled = par("carrierAggregationEnabled");
        beamformingEnabled = par("beamformingEnabled");
        mimoEnabled = par("mimoEnabled");
        networkSlicingEnabled = par("networkSlicingEnabled");
        dualConnectivityEnabled = par("dualConnectivityEnabled");
        
        // Link budget params
        linkParams.frequencyGhz = par("frequencyGhz");
        linkParams.bandwidthMhz = par("bandwidthMhz");
        linkParams.txPowerDbm = par("txPowerDbm");
        linkParams.rxNoiseFigureDb = par("rxNoiseFigureDb");
        linkParams.implementationLossDb = par("implementationLossDb");
        linkParams.bodyLossDb = par("bodyLossDb");
        linkParams.shadowMarginDb = par("shadowMarginDb");
        
        // Find Simu5G modules
        findSimu5GModules();
        
        // Register signals
        gnbDeployedSignal = registerSignal("gnbDeployed");
        ueAttachedSignal = registerSignal("ueAttached");
        handoverSignal = registerSignal("handover");
        caConfiguredSignal = registerSignal("caConfigured");
        beamformedSignal = registerSignal("beamformed");
        sliceCreatedSignal = registerSignal("sliceCreated");
        linkQualitySignal = registerSignal("linkQuality");
        throughputSignal = registerSignal("throughput");
        latencySignal = registerSignal("latency");
        
        // Deploy gNBs
        deployGNBs();
        
        // Configure Simu5G modules
        configureBinder();
        configureCarrierAggregation();
        configureMAC();
        
        // Load YAML config if provided
        if (!simu5gConfigFile.empty()) {
            std::ifstream file(simu5gConfigFile);
            if (file.is_open()) {
                std::stringstream buffer;
                buffer << file.rdbuf();
                configureFromYAML(buffer.str());
                file.close();
            }
        }
        
        EV_INFO << "NRManager initialized with " << gnbs.size() << " gNBs\n";
    }
}

void NRManager::handleMessage(omnetpp::cMessage* msg) {
    // Handle messages from Simu5G or other modules
    // For now, just delete
    delete msg;
}

void NRManager::finish() {
    recordScalar("totalGNBs", gnbs.size());
    recordScalar("totalUEs", ues.size());
    recordScalar("totalHandovers", totalHandovers);
    recordScalar("totalCAConfigurations", totalCAConfigurations);
    recordScalar("totalThroughputGb", totalThroughputGb);
    
    EV_INFO << "NRManager finished\n";
}

void NRManager::findSimu5GModules() {
    // Find Simu5G binder module
    binderModule = getSimulation()->getModuleByPath("**.binder");
    if (!binderModule) {
        binderModule = getSimulation()->getModuleByPath("**.Binder");
    }
    if (!binderModule) {
        EV_WARN << "NRManager: Simu5G Binder module not found\n";
    } else {
        EV_INFO << "NRManager: Found Simu5G Binder at " << binderModule->getFullPath() << "\n";
    }
    
    // Find carrier aggregation module
    carrierAggregationModule = getSimulation()->getModuleByPath("**.carrierAggregation");
    if (!carrierAggregationModule) {
        carrierAggregationModule = getSimulation()->getModuleByPath("**.CarrierAggregation");
    }
    
    // Find MAC module
    macModule = getSimulation()->getModuleByPath("**.mac");
    if (!macModule) {
        macModule = getSimulation()->getModuleByPath("**.Mac");
    }
}

void NRManager::configureBinder() {
    if (!binderModule) return;
    
    // Configure Simu5G binder for NR
    // In Simu5G, the binder connects MAC, RLC, PDCP layers
    EV_INFO << "NRManager: Configuring Simu5G Binder\n";
    
    // Example: binderModule->par("someParam") = value;
}

void NRManager::configureCarrierAggregation() {
    if (!carrierAggregationEnabled || !carrierAggregationModule) return;
    
    EV_INFO << "NRManager: Configuring Carrier Aggregation\n";
    
    // Configure component carriers for each gNB
    for (auto& [name, gnb] : gnbs) {
        if (gnb.caEnabled && !gnb.componentCarriers.empty()) {
            // Send configuration to carrier aggregation module
            // carrierAggregationModule->par("numCC") = gnb.componentCarriers.size();
            totalCAConfigurations++;
        }
    }
    
    emit(caConfiguredSignal, totalCAConfigurations);
}

void NRManager::configureMAC() {
    if (!macModule) return;
    
    EV_INFO << "NRManager: Configuring MAC layer\n";
    
    // Configure MAC parameters for NR
    // macModule->par("numerology") = static_cast<int>(Numerology::N1);
}

void NRManager::deployGNBs() {
    // In a real deployment, gNBs would be created from NED network definition
    // Here we just register the configurations
    
    // Example gNB configurations (would come from YAML or scenario generator)
    if (gnbs.empty()) {
        // Create default macro gNB
        GNBConfig macro;
        macro.name = "gnb_macro_0";
        macro.type = GNBType::MACRO;
        macro.position = inet::Coord(0, 0, 0);
        macro.heightM = 25;
        macro.txPowerDbm = 46;
        macro.antennaGainDbi = 18;
        macro.beamwidthDeg = 65;
        macro.frequencyGhz = 3.5;
        macro.bandwidthMhz = 100;
        macro.numerology = Numerology::N1;
        macro.mimoLayers = 4;
        macro.caEnabled = true;
        macro.componentCarriers = {{3.5, 100}, {28, 400}};
        
        gnbs[macro.name] = macro;
        
        // Create mmWave gNB
        GNBConfig mmwave;
        mmwave.name = "gnb_mmwave_0";
        mmwave.type = GNBType::MMWAVE;
        mmwave.position = inet::Coord(500, 500, 0);
        mmwave.heightM = 10;
        mmwave.txPowerDbm = 35;
        mmwave.antennaGainDbi = 25;
        mmwave.beamwidthDeg = 30;
        mmwave.frequencyGhz = 28;
        mmwave.bandwidthMhz = 400;
        mmwave.numerology = Numerology::N2;
        mmwave.mimoLayers = 2;
        mmwave.numBeams = 64;
        mmwave.caEnabled = false;
        
        gnbs[mmwave.name] = mmwave;
    }
    
    // Create modules for each gNB (would be done via NED)
    for (auto& [name, config] : gnbs) {
        createGNBModule(config);
    }
    
    for (const auto& [name, config] : gnbs) {
        emit(gnbDeployedSignal, name.c_str());
    }
}

void NRManager::createGNBModule(const GNBConfig& config) {
    // Find or create gNB module from NED network
    std::string modName = "gnb[" + config.name + "]";
    omnetpp::cModule* parent = getParentModule();
    omnetpp::cModule* mod = parent->getSubmodule(modName.c_str());
    
    if (mod) {
        gnbModules[config.name] = mod;
        
        // Set parameters
        mod->par("gnbType") = static_cast<int>(config.type);
        mod->par("txPowerDbm") = config.txPowerDbm;
        mod->par("frequencyGhz") = config.frequencyGhz;
        mod->par("bandwidthMhz") = config.bandwidthMhz;
        
        EV_DEBUG << "NRManager: Found gNB module " << modName << "\n";
    } else {
        EV_WARN << "NRManager: gNB module not found: " << modName << "\n";
    }
}

void NRManager::configureGNB(const std::string& gnbName) {
    auto it = gnbs.find(gnbName);
    if (it == gnbs.end()) return;
    
    const GNBConfig& config = it->second;
    auto modIt = gnbModules.find(gnbName);
    if (modIt == gnbModules.end()) return;
    
    omnetpp::cModule* mod = modIt->second;
    
    // Configure beamforming
    if (beamformingEnabled && config.beamformingEnabled) {
        configureBeamforming(gnbName);
    }
    
    // Configure MIMO
    if (mimoEnabled) {
        // MIMO configuration would go here
    }
    
    EV_INFO << "NRManager: Configured gNB " << gnbName << "\n";
}

void NRManager::attachUE(int ueId, const std::string& gnbName) {
    if (gnbs.find(gnbName) == gnbs.end()) {
        EV_WARN << "NRManager: Unknown gNB " << gnbName << "\n";
        return;
    }
    
    UEConfig ue;
    ue.ueId = ueId;
    ue.position = inet::Coord(0, 0, 0);  // Would get from mobility
    ue.maxTxPowerDbm = 23;
    ue.maxMimoLayers = 2;
    ue.caEnabled = carrierAggregationEnabled;
    ue.dualConnectivityEnabled = dualConnectivityEnabled;
    
    ues[ueId] = ue;
    
    // Find UE module
    std::string modName = "ue[" + std::to_string(ueId) + "]";
    omnetpp::cModule* parent = getParentModule();
    omnetpp::cModule* mod = parent->getSubmodule(modName.c_str());
    
    if (mod) {
        ueModules[ueId] = mod;
        
        // Attach to gNB via Simu5G
        // This would trigger RRC connection establishment
        
        emit(ueAttachedSignal, ueId);
        
        // Configure carrier aggregation for UE
        if (ue.caEnabled && gnbs[gnbName].caEnabled) {
            configureCA(ueId, gnbs[gnbName].componentCarriers);
        }
        
        EV_INFO << "NRManager: UE " << ueId << " attached to " << gnbName << "\n";
    } else {
        EV_WARN << "NRManager: UE module not found: " << modName << "\n";
    }
}

void NRManager::detachUE(int ueId) {
    ues.erase(ueId);
    ueModules.erase(ueId);
}

void NRManager::handoverUE(int ueId, const std::string& fromGNB, const std::string& toGNB) {
    if (ues.find(ueId) == ues.end()) return;
    
    totalHandovers++;
    
    // Trigger handover in Simu5G
    // This would send RRC handover command
    
    emit(handoverSignal, ueId);
    
    EV_INFO << "NRManager: Handover UE " << ueId << " from " << fromGNB << " to " << toGNB << "\n";
}

void NRManager::configureCA(int ueId, const std::vector<std::pair<double, double>>& carriers) {
    if (!carrierAggregationModule) return;
    
    // Configure component carriers for UE
    // carrierAggregationModule->par("ueId") = ueId;
    // carrierAggregationModule->par("numCC") = carriers.size();
    
    EV_INFO << "NRManager: Configured CA for UE " << ueId << " with " << carriers.size() << " CCs\n";
}

void NRManager::updateCAConfiguration(int ueId) {
    // Update CA based on channel conditions
}

void NRManager::configureBeamforming(const std::string& gnbName) {
    auto it = gnbs.find(gnbName);
    if (it == gnbs.end()) return;
    
    const GNBConfig& config = it->second;
    if (!config.beamformingEnabled) return;
    
    // Configure analog/digital/hybrid beamforming
    // Would set beamforming weights, codebook, etc.
    
    emit(beamformedSignal, gnbName.c_str());
    
    EV_INFO << "NRManager: Beamforming configured for " << gnbName 
            << " (" << config.numBeams << " beams)\n";
}

void NRManager::updateBeamDirection(const std::string& gnbName, int ueId, 
                                    double azimuth, double elevation) {
    // Update beam direction for specific UE
    // In hybrid beamforming, this updates analog beamforming weights
}

void NRManager::configureMIMO(const std::string& gnbName, int ueId, int layers) {
    // Configure MIMO layers for UE
    auto ueIt = ues.find(ueId);
    if (ueIt == ues.end()) return;
    
    int maxLayers = std::min(layers, ueIt->second.maxMimoLayers);
    // Send MIMO configuration to gNB and UE modules
}

double NRManager::calculatePathLoss(const inet::Coord& txPos, const inet::Coord& rxPos,
                                    double frequencyGhz, double txHeight, double rxHeight) {
    // 3GPP 38.901 path loss models
    double distance = (txPos - rxPos).length() / 1000.0;  // km
    double fc = frequencyGhz;
    double hBS = txHeight;
    double hUT = rxHeight;
    
    if (channelModelType == "UMa") {
        // Urban Macro (3GPP 38.901 Table 7.4.1-1)
        // LOS
        double plLOS = 28.0 + 22.0 * log10(distance * 1000) + 20 * log10(fc);
        // NLOS
        double plNLOS = std::max(plLOS, 
            13.54 + 39.08 * log10(distance * 1000) + 20 * log10(fc) 
            - 0.6 * (hUT - 1.5));
        
        // LOS probability
        double pLOS = std::min(18.0 / distance, 1.0) * (1 - exp(-distance / 0.063)) + exp(-distance / 0.063);
        
        return pLOS * plLOS + (1 - pLOS) * plNLOS;
    } else if (channelModelType == "UMi") {
        // Urban Micro
        double plLOS = 32.4 + 21.0 * log10(distance * 1000) + 20 * log10(fc);
        double plNLOS = std::max(plLOS,
            35.3 * log10(distance * 1000) + 22.4 + 21.3 * log10(fc) 
            - 0.3 * (hUT - 1.5));
        
        double pLOS = std::min(18.0 / distance, 1.0) * (1 - exp(-distance / 0.036)) + exp(-distance / 0.036);
        
        return pLOS * plLOS + (1 - pLOS) * plNLOS;
    } else if (channelModelType == "RMa") {
        // Rural Macro
        double plLOS = 20 * log10(4 * M_PI * distance * 1000 * fc * 1e9 / 3e8);
        double plNLOS = 161.04 - 7.1 * log10(hBS - 1.5) + 7.5 * log10(distance * 1000) 
                        + 20 * log10(fc) - (1.1 * log10(hBS - 1.5) - 0.7) * hUT;
        
        double pLOS = std::min(1.0, std::max(0.0, (10 - distance) / 10.0));
        
        return pLOS * plLOS + (1 - pLOS) * plNLOS;
    }
    
    // Free space fallback
    double wavelength = 3e8 / (fc * 1e9);
    return 20 * log10(4 * M_PI * distance * 1000 / wavelength);
}

double NRManager::calculateShadowing(double distanceKm) {
    // Correlated log-normal shadowing
    // Standard deviation: 4-8 dB depending on scenario
    double sigma = (channelModelType == "UMa") ? 6.0 : 
                   (channelModelType == "UMi") ? 4.0 : 8.0;
    
    // Simplified: return fixed margin
    return linkParams.shadowMarginDb;
}

double NRManager::calculateFastFading() {
    // Rayleigh/Rician fading
    // Simplified: return 0 dB (average)
    return 0.0;
}

double NRManager::calculateLinkBudget(const GNBConfig& gnb, const UEConfig& ue) {
    double distance = (gnb.position - ue.position).length() / 1000.0;  // km
    
    // Path loss
    double plDb = calculatePathLoss(gnb.position, ue.position, gnb.frequencyGhz, 
                                     gnb.heightM, 1.5);
    
    // Shadowing
    double shadowDb = calculateShadowing(distance);
    
    // Fast fading
    double fadingDb = calculateFastFading();
    
    // Antenna gains
    double gTxDb = gnb.antennaGainDbi;
    double gRxDb = 0;  // UE antenna gain (omnidirectional)
    
    // Body loss, implementation loss
    double bodyLossDb = linkParams.bodyLossDb;
    double implLossDb = linkParams.implementationLossDb;
    
    // Received power
    double pRxDbm = gnb.txPowerDbm + gTxDb + gRxDb - plDb - shadowDb - fadingDb - bodyLossDb - implLossDb;
    
    // SNR
    double bandwidthHz = gnb.bandwidthMhz * 1e6;
    double noiseFloorDbm = -174 + 10 * log10(bandwidthHz) + linkParams.rxNoiseFigureDb;
    double snrDb = pRxDbm - noiseFloorDbm;
    
    // Return quality (0-1)
    double quality = std::min(1.0, std::max(0.0, (snrDb + 10) / 30.0));
    
    return quality;
}

double NRManager::calculateSNR(double receivedPowerDbm, double bandwidthHz) {
    double noiseFloorDbm = -174 + 10 * log10(bandwidthHz) + linkParams.rxNoiseFigureDb;
    return receivedPowerDbm - noiseFloorDbm;
}

double NRManager::calculateDataRate(double snrDb, double bandwidthHz, int mimoLayers) {
    // Shannon capacity with practical limits
    double spectralEfficiency;
    if (snrDb < -5) spectralEfficiency = 0.1;
    else if (snrDb < 0) spectralEfficiency = 0.5;
    else if (snrDb < 5) spectralEfficiency = 1.5;
    else if (snrDb < 10) spectralEfficiency = 3.0;
    else if (snrDb < 15) spectralEfficiency = 5.0;
    else if (snrDb < 20) spectralEfficiency = 7.0;
    else spectralEfficiency = 8.5;
    
    // MIMO multiplexing gain
    spectralEfficiency *= mimoLayers;
    
    // Practical overhead (pilots, coding, HARQ, etc.)
    spectralEfficiency *= 0.7;
    
    return bandwidthHz * spectralEfficiency / 1e6;  // Mbps
}

void NRManager::createSlice(const SliceConfig& slice) {
    slices.push_back(slice);
    emit(sliceCreatedSignal, slice.name.c_str());
    
    EV_INFO << "NRManager: Created network slice " << slice.name 
            << " (priority: " << slice.priority << ")\n";
}

void NRManager::assignUEToSlice(int ueId, const std::string& sliceName) {
    // Assign UE to network slice
    // Would configure QoS flows in Simu5G
}

void NRManager::configureDualConnectivity(int ueId, bool enable) {
    auto it = ues.find(ueId);
    if (it != ues.end()) {
        it->second.dualConnectivityEnabled = enable;
    }
}

void NRManager::splitBearer(int ueId, double nrRatio) {
    // nrRatio: 0 = all NTN, 1 = all NR
    // Configure PDCP split bearer
    EV_INFO << "NRManager: UE " << ueId << " bearer split: " 
            << (nrRatio * 100) << "% NR, " << ((1-nrRatio) * 100) << "% NTN\n";
}

void NRManager::evaluateTrafficSteering(int ueId) {
    // Evaluate whether to steer traffic to NR or NTN
    // Based on latency, throughput, reliability requirements
}

void NRManager::configureFromYAML(const std::string& yamlContent) {
    // Parse YAML configuration
    // Would use yaml-cpp library
    EV_INFO << "NRManager: Received YAML configuration (" << yamlContent.length() << " chars)\n";
    
    // Example parsing (simplified):
    // Parse gNB configurations, slice configurations, etc.
}

omnetpp::cModule* NRManager::getSimu5GModule(const std::string& path) {
    return getSimulation()->getModuleByPath(path.c_str());
}

template<typename T>
T* NRManager::getSimu5GModuleAs(const std::string& path) {
    omnetpp::cModule* mod = getSimu5GModule(path);
    if (mod) {
        return dynamic_cast<T*>(mod);
    }
    return nullptr;
}

} // namespace nr
} // namespace artery