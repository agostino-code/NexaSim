package artery.hybrid;

//
// HybridInterfaceManager - Orchestrates vertical handover (VHO) between
// Terrestrial 5G-NR Cellular and Non-Terrestrial LEO Satellite.
// Inspired by squidslab/simu-scs-hybrid.
//
simple HybridInterfaceManager
{
    parameters:
        @class(hybrid::HybridInterfaceManager);
        @display("i=block/switch;is=s");
        string switchingMode = default("coverage-based"); // "coverage-based", "qos-based", "energy-aware"
        string satInterfaceName = default("wlan0");
        string cellInterfaceName = default("cellular");
        bool initialSatelliteActive = default(false);
        double checkInterval @unit(s) = default(1.0s);
        double elevationMaskDeg = default(25.0);

        @signal[activeInterface](type=long);
        @signal[switchCount](type=long);
        @signal[qosScore](type=double);
        @signal[batterySoC](type=double);

        @statistic[activeInterface](title="Active Interface (0=5G, 1=Sat)"; record=vector,last);
        @statistic[switchCount](title="Vertical Handover Count"; record=vector,last);
        @statistic[qosScore](title="QoS Score"; record=vector,mean);
        @statistic[batterySoC](title="Battery State of Charge"; record=vector,last);
}
