#ifndef ARTERY_NTN_ISL_NIC_H
#define ARTERY_NTN_ISL_NIC_H

#include <inet/common/geometry/common/Coord.h>
#include <omnetpp.h>
#include <string>

namespace artery {
namespace ntn {

/**
 * @brief Inter-Satellite Link Network Interface Card
 * 
 * Models optical (laser) or RF (Ka/V-band) ISL between LEO satellites.
 * Supports pointing/acquisition/tracking (PAT) simulation.
 */
class ISLNic : public omnetpp::cSimpleModule {
public:
    enum class LinkType {
        LASER,
        KA_BAND,
        V_BAND
    };
    
    enum class LinkState {
        IDLE,
        ACQUIRING,
        TRACKING,
        ESTABLISHED,
        DEGRADED,
        LOST
    };
    
    struct LinkParameters {
        LinkType type = LinkType::LASER;
        double wavelengthNm = 1550;       // For laser
        double frequencyGhz = 23;         // For RF
        double txPowerDbm = 20;
        double rxSensitivityDbm = -40;
        double txApertureCm = 10;         // Telescope diameter
        double rxApertureCm = 10;
        double pointingAccuracyDeg = 0.01;
        double acquisitionTimeMs = 100;
        double maxRangeKm = 5000;
        double dataRateGbps = 10;         // Laser: 10-100 Gbps, RF: 1-5 Gbps
        double beamDivergenceUrad = 10;   // For laser
    };
    
    struct LinkStateInfo {
        int remoteSatId = -1;
        LinkState state = LinkState::IDLE;
        double rangeKm = 0;
        double elevationDeg = 0;
        double azimuthDeg = 0;
        double linkQuality = 0;  // 0-1
        double ber = 1e-12;      // Bit error rate
        omnetpp::simtime_t establishedAt = -1;
        omnetpp::simtime_t lastUpdate = -1;
        omnetpp::cMessage* acquisitionTimer = nullptr;
        omnetpp::cMessage* trackingTimer = nullptr;
    };

protected:
    // Configuration
    LinkParameters params;
    int portIndex = 0;
    int maxPorts = 4;
    
    // State
    std::map<int, LinkStateInfo> links;  // remoteSatId -> state
    omnetpp::cModule* mobilityModule = nullptr;
    omnetpp::cModule* constellationManager = nullptr;
    
    // Signals
    omnetpp::simsignal_t linkEstablishedSignal;
    omnetpp::simsignal_t linkLostSignal;
    omnetpp::simsignal_t linkQualitySignal;
    omnetpp::simsignal_t acquisitionTimeSignal;
    omnetpp::simsignal_t pointingErrorSignal;
    omnetpp::simsignal_t dataRateSignal;
    
    // Statistics
    long totalLinksEstablished = 0;
    long totalLinksLost = 0;
    double totalDataTransmittedGb = 0;

    virtual void initialize(int stage) override;
    virtual void handleMessage(omnetpp::cMessage* msg) override;
    virtual void finish() override;
    
    // Link management
    void initiateAcquisition(int remoteSatId, const inet::Coord& remotePos);
    void updateTracking(int remoteSatId);
    void establishLink(int remoteSatId);
    void loseLink(int remoteSatId, const std::string& reason);
    void handlePointingError(int remoteSatId, double errorDeg);
    
    // Physics
    double calculateFreeSpaceLoss(double rangeKm, double frequencyHz);
    double calculatePointingLoss(double pointingErrorDeg);
    double calculateAtmosphericLoss(double elevationDeg, double frequencyHz);
    double calculateLinkBudget(int remoteSatId, double rangeKm, double elevationDeg);
    double calculateBER(double linkQuality);
    double calculateDataRate(double snrDb);
    double calculateRange(const inet::Coord& posA, const inet::Coord& posB);
    
    // PAT (Pointing, Acquisition, Tracking)
    void startAcquisition(int remoteSatId);
    void startTracking(int remoteSatId);
    double calculatePointingAngles(int remoteSatId, double& elevation, double& azimuth);
    
    // Message handling
    void handleAcquisitionTimer(int remoteSatId);
    void handleTrackingTimer(int remoteSatId);
    void handleRemoteMessage(omnetpp::cMessage* msg, int remoteSatId);
    
    // Utilities
    inet::Coord getOwnPosition();
    inet::Coord getRemotePosition(int remoteSatId);
    void notifyConstellationManager(int remoteSatId, LinkState newState);
    
    // Configuration from ConstellationManager
    void configureLink(const LinkParameters& p);
};

} // namespace ntn
} // namespace artery

#endif // ARTERY_NTN_ISL_NIC_H