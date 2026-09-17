/*
* Artery V2X Simulation Framework
* Copyright 2020 Raphael Riebl
* Licensed under GPLv2, see COPYING file for detailed license and warranty terms.
*/

#include "artery/inet/VanetHcf.h"

namespace artery
{

Define_Module(VanetHcf)

using namespace inet::ieee80211;
using inet::physicallayer::IIeee80211Mode;

void VanetHcf::setFrameMode(inet::Packet* packet, const inet::Ptr<const inet::ieee80211::Ieee80211MacHeader>& header, const IIeee80211Mode* mode) const
{
    using namespace inet;
    Hcf::setFrameMode(packet, header, mode);
}

} // namespace artery
