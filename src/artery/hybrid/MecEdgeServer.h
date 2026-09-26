#ifndef HYBRID_MEC_SERVER_H
#define HYBRID_MEC_SERVER_H

#include <omnetpp.h>
#include <inet/applications/base/ApplicationBase.h>
#include <inet/transportlayer/contract/udp/UdpSocket.h>
#include "artery/hybrid/MecTaskPacket_m.h"

namespace artery {
namespace hybrid {

class MecEdgeServer : public inet::ApplicationBase, public inet::UdpSocket::ICallback
{
protected:
    int m_localPort = -1;
    double m_processingSpeedMips = 10000.0; // Million Instructions Per Second
    
    inet::UdpSocket m_socket;

protected:
    virtual int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void initialize(int stage) override;
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
    virtual void finish() override;
    
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

#endif // HYBRID_MEC_SERVER_H
