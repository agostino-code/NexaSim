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
        string switchingMode = default("coverage-based"); // "coverage-based", "qos-based", "energy-aware", "predictive"
        string satInterfaceName = default("wlan0");
        string cellInterfaceName = default("cellular");
        bool initialSatelliteActive = default(false);
        double checkInterval @unit(s) = default(1.0s);
        double elevationMaskDeg = default(25.0);
        double lookaheadTimeS @unit(s) = default(3.0s);
        double timeToLossThresholdS @unit(s) = default(1.5s);
        double minDwellTimeS @unit(s) = default(4.0s);
        double blindSpotMinX = default(1500.0);
        double blindSpotMaxX = default(2800.0);
        double blindSpotMinY = default(800.0);
        double blindSpotMaxY = default(2200.0);
        double blindSpotAttenuationDb = default(45.0);
        double hysteresisMarginDb = default(3.0); // 3GPP Rel-17 NTN VHO Hysteresis in dB
        double timeToTrigger @unit(s) = default(0.5s); // 3GPP Rel-17 NTN Time-To-Trigger (TTT)

        @signal[activeInterface](type=long);
        @signal[switchCount](type=long);
        @signal[qosScore](type=double);
        @signal[batterySoC](type=double);
        @signal[timeToLoss](type=double);

        @statistic[activeInterface](title="Active Interface (0=5G, 1=Sat)"; record=vector,last);
        @statistic[switchCount](title="Vertical Handover Count"; record=vector,last);
        @statistic[qosScore](title="QoS Score"; record=vector,mean);
        @statistic[batterySoC](title="Battery State of Charge"; record=vector,last);
        @statistic[timeToLoss](title="Predictive Time-To-Loss"; unit=s; record=vector,min);
}
