#include "artery/inet/InetRadioDriver.h"
#include "artery/inet/VanetRxControl.h"
#include "artery/inet/VanetTxControl.h"
#include "artery/networking/GeoNetIndication.h"
#include "artery/networking/GeoNetPacket.h"
#include "artery/networking/GeoNetRequest.h"
#include "artery/nic/RadioDriverProperties.h"
#include <inet/common/InitStages.h>
#include <inet/common/ModuleAccess.h>
#include <inet/common/ProtocolGroup.h>
#include <inet/common/ProtocolTag_m.h>
#include <inet/common/packet/chunk/cPacketChunk.h>
#include <inet/linklayer/common/MacAddressTag_m.h>
#include <inet/linklayer/common/UserPriorityTag_m.h>
#include <inet/linklayer/ieee80211/mac/Ieee80211Mac.h>
#include <inet/physicallayer/ieee80211/packetlevel/Ieee80211Radio.h>

using namespace omnetpp;

namespace artery
{

Register_Class(InetRadioDriver)

namespace {

vanetza::MacAddress convert(const inet::MacAddress& mac)
{
	vanetza::MacAddress result;
	mac.getAddressBytes(result.octets.data());
	return result;
}

inet::MacAddress convert(const vanetza::MacAddress& mac)
{
	inet::MacAddress result;
	result.setAddressBytes(const_cast<uint8_t*>(mac.octets.data()));
	return result;
}

static const simsignal_t radioChannelChangedSignal = cComponent::registerSignal("radioChannelChanged");
static const simsignal_t channelLoadSignal = cComponent::registerSignal("ChannelLoad");

} // namespace

int InetRadioDriver::numInitStages() const
{
	return inet::InitStages::NUM_INIT_STAGES;
}

void InetRadioDriver::initialize(int stage)
{
	if (stage == inet::INITSTAGE_LOCAL) {
		RadioDriverBase::initialize();
		cModule* host = inet::getContainingNode(this);
		mLinkLayer = inet::findModuleFromPar<cModule>(par("macModule"), host);
		if (mLinkLayer) {
			mLinkLayer->subscribe(channelLoadSignal, this);
		}
		mRadio = inet::findModuleFromPar<cModule>(par("radioModule"), host);
		if (mRadio) {
			mRadio->subscribe(radioChannelChangedSignal, this);
		}
	} else if (stage == inet::INITSTAGE_LINK_LAYER) {
		ASSERT(mChannelNumber > 0);
		auto properties = new RadioDriverProperties();
		auto mac = dynamic_cast<inet::ieee80211::Ieee80211Mac*>(mLinkLayer);
		if (mac) {
			properties->LinkLayerAddress = convert(mac->getAddress());
		}
		properties->ServingChannel = mChannelNumber;
		indicateProperties(properties);
	}
}

void InetRadioDriver::receiveSignal(cComponent* source, simsignal_t signal, double value, cObject*)
{
	if (signal == channelLoadSignal) {
		emit(RadioDriverBase::ChannelLoadSignal, value);
	}
}

void InetRadioDriver::receiveSignal(cComponent* source, simsignal_t signal, long value, cObject*)
{
	if (signal == radioChannelChangedSignal) {
		mChannelNumber = value;
	}
}

void InetRadioDriver::handleMessage(cMessage* msg)
{
	if (msg->getArrivalGate() == gate("lowerLayerIn")) {
		handleDataIndication(msg);
	} else {
		RadioDriverBase::handleMessage(msg);
	}
}

void InetRadioDriver::handleDataRequest(cMessage* packet)
{
	auto request = check_and_cast<GeoNetRequest*>(packet->removeControlInfo());

	auto inetPacket = new inet::Packet(packet->getName());
	inetPacket->insertAtBack(inet::makeShared<inet::cPacketChunk>(check_and_cast<cPacket*>(packet)));

	auto macReq = inetPacket->addTag<inet::MacAddressReq>();
	macReq->setDestAddress(convert(request->destination_addr));
	macReq->setSrcAddress(convert(request->source_addr));

	auto upReq = inetPacket->addTag<inet::UserPriorityReq>();
	switch (request->access_category) {
		case vanetza::access::AccessCategory::VO:
			upReq->setUserPriority(7);
			break;
		case vanetza::access::AccessCategory::VI:
			upReq->setUserPriority(5);
			break;
		case vanetza::access::AccessCategory::BE:
			upReq->setUserPriority(3);
			break;
		case vanetza::access::AccessCategory::BK:
			upReq->setUserPriority(1);
			break;
		default:
			upReq->setUserPriority(3);
			break;
	}

	static const inet::Protocol geoNetProto("geonet", "GeoNetworking");
	if (inet::ProtocolGroup::ethertype.findProtocolNumber(&geoNetProto) == -1) {
		inet::ProtocolGroup::ethertype.addProtocol(request->ether_type.host(), &geoNetProto);
	}
	inetPacket->addTagIfAbsent<inet::PacketProtocolTag>()->setProtocol(&geoNetProto);
	inetPacket->addTagIfAbsent<inet::DispatchProtocolReq>()->setProtocol(&geoNetProto);

	delete request;
	send(inetPacket, "lowerLayerOut");
}

void InetRadioDriver::handleDataIndication(cMessage* packet)
{
	auto* inetPacket = dynamic_cast<inet::Packet*>(packet);
	cPacket* innerPacket = nullptr;
	inet::MacAddress srcAddr, destAddr;

	if (inetPacket) {
		if (auto macInd = inetPacket->findTag<inet::MacAddressInd>()) {
			srcAddr = macInd->getSrcAddress();
			destAddr = macInd->getDestAddress();
		}
		try {
			const auto& chunk = inetPacket->peekData<inet::cPacketChunk>();
			if (chunk && chunk->getPacket()) {
				innerPacket = chunk->getPacket()->dup();
			}
		} catch (const std::exception& e) {
			innerPacket = nullptr;
		}
		delete inetPacket;
	} else {
		innerPacket = check_and_cast<cPacket*>(packet);
	}

	if (innerPacket) {
		auto* indication = new GeoNetIndication();
		indication->source = convert(srcAddr);
		indication->destination = convert(destAddr);
		innerPacket->setControlInfo(indication);
		indicateData(innerPacket);
	}
}

} // namespace artery
