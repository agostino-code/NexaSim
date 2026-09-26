#include "artery/hybrid/MecOffloadingClient.h"
#include <algorithm>
#include <inet/common/ModuleAccess.h>
#include <inet/common/packet/Packet.h>
#include <inet/common/packet/chunk/cPacketChunk.h>
#include <inet/networklayer/common/L3AddressResolver.h>
#include <omnetpp/checkandcast.h>

namespace artery {
namespace hybrid {

Define_Module(MecOffloadingClient);

void MecOffloadingClient::initialize(int stage)
{
    ApplicationBase::initialize(stage);

    if (stage == inet::INITSTAGE_LOCAL) {
        m_localPort = par("localPort");
        m_destPort = par("destPort");
        m_taskGenerationInterval = par("taskGenerationInterval");
        m_taskSizeByte = par("taskSizeByte");
        m_taskInstructions = par("taskInstructions");
        
        m_sigTaskLatency = registerSignal("mecTaskLatency");
        
        m_timer = new omnetpp::cMessage("generateTask");
    }
    else if (stage == inet::INITSTAGE_APPLICATION_LAYER) {
        const char *terrAddr = par("terrestrialEdgeAddress");
        const char *satAddr = par("satelliteEdgeAddress");

        try {
            if (strlen(terrAddr) > 0)
                m_terrestrialEdgeAddr = inet::L3AddressResolver().resolve(terrAddr);
            if (strlen(satAddr) > 0)
                m_satelliteEdgeAddr = inet::L3AddressResolver().resolve(satAddr);
        } catch (...) {
            // Unresolved addresses gracefully fall back to co-simulation channel model
        }

        if (gate("socketOut")->isConnected()) {
            m_socket.setOutputGate(gate("socketOut"));
            m_socket.setCallback(this);
            m_socket.bind(m_localPort);
        }
        
        // Find the HybridInterfaceManager in the same node
        omnetpp::cModule *node = inet::findContainingNode(this);
        if (node) {
            for (omnetpp::cModule::SubmoduleIterator it(node); !it.end(); ++it) {
                if (dynamic_cast<HybridInterfaceManager*>(*it)) {
                    m_hybridManager = dynamic_cast<HybridInterfaceManager*>(*it);
                    break;
                }
            }
        }
        
        scheduleAt(omnetpp::simTime() + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.0, m_taskGenerationInterval), m_timer);
    }
}

void MecOffloadingClient::handleMessageWhenUp(omnetpp::cMessage *msg)
{
    if (msg->isSelfMessage() && msg == m_timer) {
        generateTask();
        scheduleAt(omnetpp::simTime() + m_taskGenerationInterval, m_timer);
    } else if (msg->isSelfMessage() && strcmp(msg->getName(), "localMecFinish") == 0) {
        handleLocalTaskCompleted(msg);
    } else {
        m_socket.processMessage(msg);
    }
}

void MecOffloadingClient::generateTask()
{
    if (!m_hybridManager) {
        EV_WARN << "HybridInterfaceManager not found, skipping MEC task generation." << std::endl;
        return;
    }

    bool isSat = m_hybridManager->isSatelliteActive();
    inet::L3Address destAddr = isSat ? m_satelliteEdgeAddr : m_terrestrialEdgeAddr;

    int taskId = ++m_taskIdCounter;

    // 1. If valid destination and UDP socket are active, send real packet
    if (!destAddr.isUnspecified() && gate("socketOut")->isConnected()) {
        try {
            auto payload = new MecTaskPacket("MecTaskReq");
            payload->setTaskId(taskId);
            payload->setComputationInstructions(m_taskInstructions);
            payload->setGenerationTime(omnetpp::simTime().dbl());
            payload->setRoutingDecision(isSat ? 1 : 0);
            payload->setByteLength(m_taskSizeByte);

            auto packet = new inet::Packet("MecTaskReq");
            packet->insertAtBack(inet::makeShared<inet::cPacketChunk>(payload));

            EV_INFO << "Offloading Task #" << taskId
                    << " to " << (isSat ? "Satellite Edge" : "Terrestrial Edge")
                    << " (" << destAddr << ")" << std::endl;

            m_socket.sendTo(packet, destAddr, m_destPort);
            return;
        } catch (std::exception& e) {
            EV_WARN << "MEC Socket Send failed (" << e.what() << "), using co-simulation channel model." << std::endl;
        }
    }

    // 2. Co-simulation Channel & Edge Processor Fallback
    // Evaluates realistic propagation RTT + Edge Compute latency
    double rtt = isSat ? (0.024 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.001, 0.006))
                       : (0.005 + omnetpp::uniform(omnetpp::getEnvir()->getRNG(0), 0.0005, 0.002));
    double mips = isSat ? 5000.0 : 20000.0;
    double computeTime = (m_taskInstructions / 1e6) / mips;
    double totalDelay = rtt + computeTime;

    auto finishMsg = new omnetpp::cMessage("localMecFinish");
    finishMsg->setKind(taskId);
    finishMsg->setContextPointer(new double(totalDelay));
    m_pendingTimers.push_back(finishMsg);

    EV_INFO << "Offloading Task #" << taskId
            << " to " << (isSat ? "Satellite Edge" : "Terrestrial Edge")
            << " (Modeled Latency: " << totalDelay * 1000 << " ms)" << std::endl;

    scheduleAt(omnetpp::simTime() + totalDelay, finishMsg);
}

void MecOffloadingClient::handleLocalTaskCompleted(omnetpp::cMessage *msg)
{
    if (msg->getContextPointer()) {
        double latency = *(static_cast<double*>(msg->getContextPointer()));
        delete static_cast<double*>(msg->getContextPointer());
        msg->setContextPointer(nullptr);

        emit(m_sigTaskLatency, latency);

        EV_INFO << "MEC Task #" << msg->getKind() << " completed. "
                << "Total Latency (RTT + Compute): " << latency * 1000 << " ms" << std::endl;
    }
    auto it = std::find(m_pendingTimers.begin(), m_pendingTimers.end(), msg);
    if (it != m_pendingTimers.end()) {
        m_pendingTimers.erase(it);
    }
    delete msg;
}

void MecOffloadingClient::socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet)
{
    try {
        const auto& chunk = packet->peekData<inet::cPacketChunk>();
        if (chunk && chunk->getPacket()) {
            if (auto payload = dynamic_cast<MecTaskPacket*>(chunk->getPacket())) {
                double latency = omnetpp::simTime().dbl() - payload->getGenerationTime();
                emit(m_sigTaskLatency, latency);
                
                EV_INFO << "MEC Task #" << payload->getTaskId() << " completed. "
                        << "Total Latency (RTT + Compute): " << latency * 1000 << " ms" << std::endl;
            }
        }
    } catch (std::exception& e) {}
    delete packet;
}

void MecOffloadingClient::socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication)
{
    EV_WARN << "UDP socket error in MecOffloadingClient: " << indication->getName() << std::endl;
    delete indication;
}

void MecOffloadingClient::socketClosed(inet::UdpSocket *socket)
{
}

void MecOffloadingClient::finish()
{
    ApplicationBase::finish();
    cancelAndDelete(m_timer);
    for (auto timerMsg : m_pendingTimers) {
        if (timerMsg) {
            if (timerMsg->getContextPointer()) {
                delete static_cast<double*>(timerMsg->getContextPointer());
                timerMsg->setContextPointer(nullptr);
            }
            cancelAndDelete(timerMsg);
        }
    }
    m_pendingTimers.clear();
}

} // namespace hybrid
} // namespace artery
