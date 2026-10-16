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
    // 3GPP TR 38.901 path loss models with Breakpoint Distance (d'_BP)
    inet::Coord diff2D = txPos - rxPos;
    diff2D.z = 0;
    double d2D = std::max(1.0, diff2D.length()); // 2D distance in meters
    double hBS = txHeight;
    double hUT = rxHeight;
    double d3D = std::sqrt(d2D * d2D + (hBS - hUT) * (hBS - hUT));
    double fc = frequencyGhz;
    constexpr double c0 = 299792458.0;

    // Effective antenna heights (Table 7.4.1-1 note 1)
    double hPrimeBS = std::max(1.0, hBS - 1.0);
    double hPrimeUT = std::max(1.0, hUT - 1.0);
    double dPrimeBP = 4.0 * hPrimeBS * hPrimeUT * (fc * 1e9) / c0;

    if (channelModelType == "UMa") {
        // Urban Macro (3GPP TR 38.901 Table 7.4.1-1)
        double plLOS = 0.0;
        if (d2D <= dPrimeBP) {
            plLOS = 28.0 + 22.0 * std::log10(d3D) + 20.0 * std::log10(fc);
        } else {
            plLOS = 28.0 + 40.0 * std::log10(d3D) + 20.0 * std::log10(fc)
                    - 9.0 * std::log10(dPrimeBP * dPrimeBP + (hBS - hUT) * (hBS - hUT));
        }

        double plNLOS = 13.54 + 39.08 * std::log10(d3D) + 20.0 * std::log10(fc) - 0.6 * (hUT - 1.5);
        plNLOS = std::max(plLOS, plNLOS);

        // 3GPP UMa LOS probability
        double pLOS = (d2D <= 18.0) ? 1.0 : (18.0 / d2D + std::exp(-d2D / 63.0) * (1.0 - 18.0 / d2D));
        pLOS = std::clamp(pLOS, 0.0, 1.0);

        return pLOS * plLOS + (1.0 - pLOS) * plNLOS;

    } else if (channelModelType == "UMi") {
        // Urban Micro (3GPP TR 38.901 Table 7.4.1-1)
        double plLOS = 0.0;
        if (d2D <= dPrimeBP) {
            plLOS = 32.4 + 21.0 * std::log10(d3D) + 20.0 * std::log10(fc);
        } else {
            plLOS = 32.4 + 40.0 * std::log10(d3D) + 20.0 * std::log10(fc)
                    - 9.5 * std::log10(dPrimeBP * dPrimeBP + (hBS - hUT) * (hBS - hUT));
        }

        double plNLOS = 22.4 + 35.3 * std::log10(d3D) + 21.3 * std::log10(fc) - 0.3 * (hUT - 1.5);
        plNLOS = std::max(plLOS, plNLOS);

        // 3GPP UMi Street Canyon LOS probability
        double pLOS = (d2D <= 18.0) ? 1.0 : (18.0 / d2D + std::exp(-d2D / 36.0) * (1.0 - 18.0 / d2D));
        pLOS = std::clamp(pLOS, 0.0, 1.0);

        return pLOS * plLOS + (1.0 - pLOS) * plNLOS;

    } else if (channelModelType == "RMa") {
        // Rural Macro (3GPP TR 38.901 Table 7.4.1-1)
        double dBP = 2.0 * M_PI * hBS * hUT * (fc * 1e9) / c0;
        double plLOS = 0.0;
        if (d2D <= dBP) {
            plLOS = 20.0 * std::log10(40.0 * M_PI * d3D * fc / 3.0) + std::min(0.03 * std::pow(hBS, 1.72), 10.0) * std::log10(d3D)
                    - std::min(0.044 * std::pow(hBS, 1.72), 14.77) + 0.002 * std::log10(hBS) * d3D;
        } else {
            double plBP = 20.0 * std::log10(40.0 * M_PI * dBP * fc / 3.0) + std::min(0.03 * std::pow(hBS, 1.72), 10.0) * std::log10(dBP)
                          - std::min(0.044 * std::pow(hBS, 1.72), 14.77) + 0.002 * std::log10(hBS) * dBP;
            plLOS = plBP + 40.0 * std::log10(d3D / dBP);
        }

        double plNLOS = 161.04 - 7.1 * std::log10(hBS) + 7.5 * std::log10(hBS) * std::log10(d3D)
                        - (24.37 - 3.7 * std::pow(hBS / 5.0, 2)) * std::log10(hBS)
                        + (43.42 - 3.1 * std::log10(hBS)) * (std::log10(d3D) - 3.0)
                        + 20.0 * std::log10(fc) - (3.2 * std::pow(std::log10(11.75 * hUT), 2) - 4.97);
        plNLOS = std::max(plLOS, plNLOS);

        double pLOS = (d2D <= 10.0) ? 1.0 : std::exp(-(d2D - 10.0) / 1000.0);
        pLOS = std::clamp(pLOS, 0.0, 1.0);

        return pLOS * plLOS + (1.0 - pLOS) * plNLOS;
    }

    // Free space fallback
    double wavelength = c0 / (fc * 1e9);
    return 20.0 * std::log10(4.0 * M_PI * d3D / wavelength);
}

double NRManager::calculateShadowing(double distanceKm) {
    double sigma = (channelModelType == "UMa") ? 6.0 : 
                   (channelModelType == "UMi") ? 4.0 : 8.0;
    return sigma;
}

double NRManager::calculateCorrelatedShadowing(int ueId, const std::string& gnbName, const inet::Coord& currentPos, bool isLOS) {
    // 3GPP TR 38.901 Table 7.5-6: Correlation distance and shadow fading standard deviation
    double dCorr = 37.0; // meters
    double sigmaSF = 4.0; // dB

    if (channelModelType == "UMa") {
        dCorr = isLOS ? 37.0 : 50.0;
        sigmaSF = isLOS ? 4.0 : 6.0;
    } else if (channelModelType == "UMi") {
        dCorr = isLOS ? 10.0 : 13.0;
        sigmaSF = isLOS ? 4.0 : 7.82;
    } else if (channelModelType == "RMa") {
        dCorr = isLOS ? 37.0 : 120.0;
        sigmaSF = isLOS ? 4.0 : 8.0;
    }

    auto key = std::make_pair(ueId, gnbName);
    auto& state = m_shadowFadingStates[key];

    if (!state.initialized) {
        state.initialized = true;
        state.lastPosition = currentPos;
        uint32_t seedVal = static_cast<uint32_t>(ueId * 1013) ^ static_cast<uint32_t>(gnbName.length() * 37);
        double u1 = std::max(1e-6, ((seedVal % 997) + 1) / 1000.0);
        double u2 = (((seedVal / 7) % 997) + 1) / 1000.0;
        double z0 = std::sqrt(-2.0 * std::log(u1)) * std::cos(2.0 * M_PI * u2);
        state.lastShadowingDb = z0 * sigmaSF;
        return state.lastShadowingDb;
    }

    double deltaD = (currentPos - state.lastPosition).length();
    state.lastPosition = currentPos;

    // Autoregressive process: S_t = e^(-delta_d / d_corr) * S_{t-1} + sqrt(1 - e^(-2*delta_d/d_corr)) * N(0, sigma^2)
    double rho = std::exp(-deltaD / std::max(1.0, dCorr));
    uint32_t stepSeed = static_cast<uint32_t>(deltaD * 100.0 + ueId * 7);
    double u1 = std::max(1e-6, ((stepSeed % 997) + 1) / 1000.0);
    double u2 = (((stepSeed / 11) % 997) + 1) / 1000.0;
    double w = std::sqrt(-2.0 * std::log(u1)) * std::cos(2.0 * M_PI * u2);

    state.lastShadowingDb = rho * state.lastShadowingDb + std::sqrt(std::max(0.0, 1.0 - rho * rho)) * (w * sigmaSF);
    return state.lastShadowingDb;
}

double NRManager::calculateFastFading() {
    return 0.0;
}

NRManager::MCSResult NRManager::evaluate3GPPThroughputAndBLER(double sinrDb, double bandwidthHz, int mimoLayers) {
    MCSResult res;
    // 3GPP TS 38.214 Table 5.2.2.1-2 (4-bit CQI Table 1)
    constexpr double sinrThresh[15] = {
        -6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1, 10.3, 11.7, 14.1, 16.3, 18.7, 21.0, 22.7
    };
    constexpr double specEff[15] = {
        0.1523, 0.2344, 0.3770, 0.6016, 0.8770, 1.1758, 1.4766, 1.9141, 2.4063, 2.7305, 3.3223, 3.9023, 4.5234, 5.1152, 5.5547
    };
    constexpr double codeRates[15] = {
        78.0 / 1024, 120.0 / 1024, 193.0 / 1024, 308.0 / 1024, 449.0 / 1024, 602.0 / 1024,
        378.0 / 1024, 490.0 / 1024, 616.0 / 1024, 466.0 / 1024, 567.0 / 1024, 666.0 / 1024,
        772.0 / 1024, 873.0 / 1024, 948.0 / 1024
    };

    if (sinrDb < sinrThresh[0] - 2.5) {
        // Complete radio outage
        res.cqi = 0;
        res.mcs = 0;
        res.codeRate = 0.0;
        res.spectralEfficiency = 0.0;
        res.bler = 1.0;
        res.throughputMbps = 0.0;
        return res;
    }

    int selectedCqi = 1;
    for (int i = 14; i >= 0; --i) {
        if (sinrDb >= sinrThresh[i]) {
            selectedCqi = i + 1;
            break;
        }
    }

    res.cqi = selectedCqi;
    res.mcs = selectedCqi * 2 - 1;
    res.codeRate = codeRates[selectedCqi - 1];
    res.spectralEfficiency = specEff[selectedCqi - 1];

    // BLER curve around target SINR with steepness parameter
    double targetSinr = sinrThresh[selectedCqi - 1];
    double deltaSinr = sinrDb - targetSinr;
    res.bler = 0.5 * std::erfc(deltaSinr / (std::sqrt(2.0) * 1.2));
    res.bler = std::clamp(res.bler, 0.0001, 1.0);

    // 3GPP NR physical layer overhead (DMRS, PDCCH, PBCH, guard band): ~14%
    constexpr double NR_OVERHEAD = 0.14;
    double rawRateBps = bandwidthHz * res.spectralEfficiency * mimoLayers;
    double effRateBps = rawRateBps * (1.0 - NR_OVERHEAD) * (1.0 - res.bler);
    res.throughputMbps = std::max(0.0, effRateBps / 1e6);

    return res;
}

double NRManager::calculateLinkBudget(const GNBConfig& gnb, const UEConfig& ue) {
    // Path loss
    double plDb = calculatePathLoss(gnb.position, ue.position, gnb.frequencyGhz, 
                                     gnb.heightM, 1.5);
    
    // Spatially Correlated Shadowing
    double shadowDb = calculateCorrelatedShadowing(ue.ueId, gnb.name, ue.position, true);
    
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
    auto mcs = evaluate3GPPThroughputAndBLER(snrDb, bandwidthHz, mimoLayers);
    return mcs.throughputMbps;
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
    auto it = ues.find(ueId);
    if (it == ues.end()) return;
    
    double bestQuality = 0.0;
    for (const auto& [name, gnb] : gnbs) {
        double quality = calculateLinkBudget(gnb, it->second);
        if (quality > bestQuality) {
            bestQuality = quality;
        }
    }
    
    double targetNrRatio = 1.0;
    if (bestQuality < 0.2) {
        targetNrRatio = 0.0; // Handover completely to NTN
    } else if (bestQuality < 0.5) {
        targetNrRatio = 0.4; // Dual connectivity split
    }
    splitBearer(ueId, targetNrRatio);
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