#include "artery/hybrid/MecEdgeServer.h"
#include <inet/common/ModuleAccess.h>
#include <inet/common/packet/Packet.h>
#include <inet/common/packet/chunk/cPacketChunk.h>
#include <inet/networklayer/common/L3AddressResolver.h>
#include <inet/networklayer/common/L3AddressTag_m.h>
#include <inet/transportlayer/common/L4PortTag_m.h>
#include <omnetpp/checkandcast.h>

namespace artery {
namespace hybrid {

Define_Module(MecEdgeServer);

void MecEdgeServer::initialize(int stage)
{
    ApplicationBase::initialize(stage);

    if (stage == inet::INITSTAGE_LOCAL) {
        m_localPort = par("localPort");
        m_processingSpeedMips = par("processingSpeedMips");
    }
    else if (stage == inet::INITSTAGE_APPLICATION_LAYER) {
        m_socket.setOutputGate(gate("socketOut"));
        m_socket.setCallback(this);
        m_socket.bind(m_localPort);
    }
}

void MecEdgeServer::handleMessageWhenUp(omnetpp::cMessage *msg)
{
    if (msg->isSelfMessage()) {
        inet::Packet *replyPacket = omnetpp::check_and_cast<inet::Packet*>(msg->removeControlInfo());
        auto destAddrTag = replyPacket->getTag<inet::L3AddressReq>();
        auto destPortTag = replyPacket->getTag<inet::L4PortReq>();
        m_socket.sendTo(replyPacket, destAddrTag->getDestAddress(), destPortTag->getDestPort());
        delete msg;
    } else {
        m_socket.processMessage(msg);
    }
}

void MecEdgeServer::socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet)
{
    try {
        const auto& chunk = packet->peekData<inet::cPacketChunk>();
        if (chunk && chunk->getPacket()) {
            if (auto payload = dynamic_cast<MecTaskPacket*>(chunk->getPacket())) {
                double instructionsMillions = payload->getComputationInstructions() / 1e6;
                double processingTime = instructionsMillions / m_processingSpeedMips;
                
                EV_INFO << "Received Task #" << payload->getTaskId() 
                        << " - Processing Time: " << processingTime * 1000 << " ms" << std::endl;
                
                auto reply = new inet::Packet("MecTaskRes");
                auto newPayload = new MecTaskPacket("MecTaskRes");
                newPayload->setTaskId(payload->getTaskId());
                newPayload->setComputationInstructions(payload->getComputationInstructions());
                newPayload->setGenerationTime(payload->getGenerationTime());
                newPayload->setRoutingDecision(payload->getRoutingDecision());
                newPayload->setByteLength(packet->getByteLength());
                
                reply->insertAtBack(inet::makeShared<inet::cPacketChunk>(newPayload));
                
                auto srcAddrTag = packet->getTag<inet::L3AddressInd>();
                auto srcPortTag = packet->getTag<inet::L4PortInd>();
                
                reply->addTagIfAbsent<inet::L3AddressReq>()->setDestAddress(srcAddrTag->getSrcAddress());
                reply->addTagIfAbsent<inet::L4PortReq>()->setDestPort(srcPortTag->getSrcPort());
                
                omnetpp::cMessage *processingTimer = new omnetpp::cMessage("MecProcessing");
                processingTimer->setControlInfo(reply);
                scheduleAt(omnetpp::simTime() + processingTime, processingTimer);
            }
        }
    } catch (std::exception& e) {}
    delete packet;
}

void MecEdgeServer::socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication)
{
    delete indication;
}

void MecEdgeServer::socketClosed(inet::UdpSocket *socket)
{
}

void MecEdgeServer::finish()
{
    ApplicationBase::finish();
}

} // namespace hybrid
} // namespace artery
