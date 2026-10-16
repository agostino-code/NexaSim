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
        double satelliteCarrierGhz = default(20.0); // Ka-band carrier of the NTN link [GHz]
        double cellularCarrierGhz = default(3.5);   // 5G-NR carrier of the terrestrial link [GHz]
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
        bool makeBeforeBreak = default(true); // 3GPP Rel-16/17 DAPS Make-Before-Break vs Hard Handover
        double handoverInterruptionTimeMs @unit(ms) = default(45ms); // Hard handover radio interruption blackout

        @signal[activeInterface](type=long);
        @signal[switchCount](type=long);
        @signal[qosScore](type=double);
        @signal[batterySoC](type=double);
        @signal[timeToLoss](type=double);
        @signal[handoverInterruption](type=double);
        @signal[v2xRelayActive](type=bool);
        @signal[aoiMs](type=double);
        @signal[safetySpeedReductionKmh](type=double);

        @statistic[activeInterface](title="Active Interface (0=5G, 1=Sat, 2=V2X)"; record=vector,last);
        @statistic[switchCount](title="Vertical Handover Count"; record=vector,last);
        @statistic[qosScore](title="QoS Score"; record=vector,mean);
        @statistic[batterySoC](title="Battery State of Charge"; record=vector,last);
        @statistic[timeToLoss](title="Predictive Time-To-Loss"; unit=s; record=vector,min);
        @statistic[handoverInterruption](title="Handover Interruption Time"; unit=ms; record=vector,last);
        @statistic[v2xUsageRatio](title="V2X Sidelink Usage Ratio"; record=last);
        @statistic[aoiMs](title="Age of Information (AoI)"; unit=ms; record=vector?,mean?);
        @statistic[safetySpeedReductionKmh](title="Safety Speed Reduction"; unit=kmph; record=vector?,mean?);
}
