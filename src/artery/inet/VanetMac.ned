package artery.inet;

import inet.linklayer.ieee80211.mac.Ieee80211Mac;

// VanetMac specializes INET's Ieee80211Mac by using VanetHcf for vehicular OCB / 802.11p EDCA
module VanetMac extends Ieee80211Mac
{
    submodules:
        hcf: VanetHcf if qosStation {
            parameters:
                @display("p=250,100");
        }
}
