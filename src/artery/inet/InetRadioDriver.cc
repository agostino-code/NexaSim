#include "artery/inet/InetRadioDriver.h"
#include "artery/inet/VanetRxControl.h"
#include "artery/inet/VanetTxControl.h"
#include "artery/networking/GeoNetIndication.h"
#include "artery/networking/GeoNetRequest.h"
#include "artery/nic/RadioDriverProperties.h"
#include <inet/common/InitStages.h>
#include <inet/common/ModuleAccess.h>
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
	auto ctrl = new VanetTxControl();
	ctrl->setDest(convert(request->destination_addr));
	ctrl->setSrc(convert(request->source_addr));
	ctrl->setEtherType(request->ether_type.host());
	switch (request->access_category) {
		case vanetza::access::AccessCategory::VO:
			ctrl->setUserPriority(7);
			break;
		case vanetza::access::AccessCategory::VI:
			ctrl->setUserPriority(5);
			break;
		case vanetza::access::AccessCategory::BE:
			ctrl->setUserPriority(3);
			break;
		case vanetza::access::AccessCategory::BK:
			ctrl->setUserPriority(1);
			break;
		default:
			throw cRuntimeError("mapping to user priority (UP) unknown");
	}
	packet->setControlInfo(ctrl);
	delete request;

	send(packet, "lowerLayerOut");
}

void InetRadioDriver::handleDataIndication(cMessage* packet)
{
	auto* info = check_and_cast<VanetRxControl*>(packet->removeControlInfo());
	auto* indication = new GeoNetIndication();
	indication->source = convert(info->getSrc());
	indication->destination = convert(info->getDest());
	packet->setControlInfo(indication);
	delete info;

	indicateData(packet);
}

} // namespace artery
