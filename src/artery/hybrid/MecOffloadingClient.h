#ifndef HYBRID_MEC_CLIENT_H
#define HYBRID_MEC_CLIENT_H

#include <omnetpp.h>
#include <inet/applications/base/ApplicationBase.h>
#include <inet/transportlayer/contract/udp/UdpSocket.h>
#include "artery/hybrid/HybridInterfaceManager.h"
#include "artery/hybrid/MecTaskPacket_m.h"

namespace artery {
namespace hybrid {

class MecOffloadingClient : public inet::ApplicationBase, public inet::UdpSocket::ICallback
{
protected:
    int m_localPort = -1;
    int m_destPort = -1;
    inet::L3Address m_terrestrialEdgeAddr;
    inet::L3Address m_satelliteEdgeAddr;
    
    double m_taskGenerationInterval = 1.0;
    int m_taskSizeByte = 1000;
    long m_taskInstructions = 1000000;
    int m_taskIdCounter = 0;
    
    inet::UdpSocket m_socket;
    omnetpp::cMessage *m_timer = nullptr;
    HybridInterfaceManager *m_hybridManager = nullptr;
    
    omnetpp::simsignal_t m_sigTaskLatency;
    std::vector<omnetpp::cMessage*> m_pendingTimers;

protected:
    virtual int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void initialize(int stage) override;
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
    virtual void finish() override;

    virtual void generateTask();
    virtual void handleLocalTaskCompleted(omnetpp::cMessage *msg);
    
    virtual void handleStartOperation(inet::LifecycleOperation *operation) override {}
    virtual void handleStopOperation(inet::LifecycleOperation *operation) override {}
    virtual void handleCrashOperation(inet::LifecycleOperation *operation) override {}
    
    // UdpSocket::ICallback methods
    virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override;
    virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override;
    virtual void socketClosed(inet::UdpSocket *socket) override;
};

} // namespace hybrid
} // namespace artery

#endif // HYBRID_MEC_CLIENT_H
