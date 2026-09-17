package artery.ntn;

simple UserTerminal
{
    parameters:
        @display("i=device/satelliteearth");
        
        // Terminal identification
        int terminalId = default(0);
        string terminalType = default("residential");  // residential | business | mobility | maritime | aviation
        
        // Phased array configuration
        int arrayNumElements = default(64);           // 8x8 = 64 elements
        double arrayElementSpacing = default(0.5);    // In wavelengths
        double arrayMaxScanAngle = default(60);       // Max boresight angle (deg)
        double arrayBeamwidth = default(10);          // 3dB beamwidth (deg)
        double arrayMaxGain = default(30);            // Max gain (dBi)
        double arraySidelobeLevel = default(-13);     // Sidelobe level (dB)
        int arrayBeamformingMode = default(2);        // 0=analog, 1=digital, 2=hybrid
        int arrayNumRFChains = default(8);            // For hybrid beamforming
        
        // Link budget parameters
        double frequencyGhz = default(28);            // Ka-band
        double bandwidthMhz = default(500);
        double txPowerDbm = default(30);
        double rxNoiseFigureDb = default(3);
        double implementationLossDb = default(3);
        double rainMarginDb = default(10);
        double polarizationLossDb = default(0.5);
        double pointingLossDb = default(1.0);
        
        // Handover parameters
        double handoverElevationThreshold = default(25);  // Start prep at this elevation
        double handoverElevationMin = default(15);        // Execute at this elevation
        double handoverHysteresisDb = default(3);
        double handoverTimeToTriggerMs = default(160);
        bool makeBeforeBreak = default(true);
        double maxHandoverDurationMs = default(50);
        
        // Dual connectivity
        bool dualConnectivityEnabled = default(false);
        string terrestrialRat = default("nr");  // nr | lte
        double terrestrialRsrpThreshold = default(-110);
        
    gates:
        input radioIn;
        output radioOut;
        input terrestrialIn;
        output terrestrialOut;
}

import space_veins.modules.nic.SatelliteInterface;

module UserTerminalNode
{
    parameters:
        @networkNode;
        @display("i=device/laptop");
    gates:
        input radioIn;
        input terrestrialIn;
        output terrestrialOut;
    submodules:
        terminal: UserTerminal {
            @display("p=100,50");
        }
        mobility: inet.mobility.static.StationaryMobility {
            @display("p=100,120");
        }
        satNic: SatelliteInterface {
            @display("p=100,200");
        }
    connections allowunconnected:
        radioIn --> satNic.radioIn;
}