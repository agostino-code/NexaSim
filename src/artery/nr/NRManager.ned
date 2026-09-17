package artery.nr;

simple NRManager
{
    parameters:
        @display("i=block/network2");
        
        // Simu5G configuration file
        string simu5gConfigFile = default("");
        
        // Channel model: UMa | UMi | RMa | InH
        string channelModel = default("UMa");
        
        // Feature flags
        bool carrierAggregationEnabled = default(true);
        bool beamformingEnabled = default(true);
        bool mimoEnabled = default(true);
        bool networkSlicingEnabled = default(true);
        bool dualConnectivityEnabled = default(false);
        
        // Default link budget parameters
        double frequencyGhz = default(3.5);
        double bandwidthMhz = default(100);
        double txPowerDbm = default(46);
        double rxNoiseFigureDb = default(5);
        double implementationLossDb = default(3);
        double bodyLossDb = default(3);
        double shadowMarginDb = default(8);
        
    gates:
        input radioIn;
        output radioOut;
}

module GNB
{
    parameters:
        @networkNode;
        @display("i=device/accesspoint");
        int gnbType = default(0);  // 0=macro, 1=micro, 2=mmwave, 3=pico
        double txPowerDbm = default(46);
        double frequencyGhz = default(3.5);
        double bandwidthMhz = default(100);
        int mimoLayers = default(4);
        bool beamformingEnabled = default(true);
        int numBeams = default(8);
    gates:
        input radioIn;
    submodules:
        nrManager: NRManager {
            @display("p=100,50");
        }
        mobility: inet.mobility.static.StationaryMobility {
            @display("p=100,120");
        }
        nic: space_veins.modules.nic.SatelliteInterface {
            @display("p=100,200");
        }
    connections allowunconnected:
        radioIn --> nic.radioIn;
}

module UE
{
    parameters:
        @networkNode;
        @display("i=device/cellphone");
        int ueId = default(0);
        double maxTxPowerDbm = default(23);
        int maxMimoLayers = default(2);
        bool caEnabled = default(true);
        bool dualConnectivityEnabled = default(false);
    gates:
        input radioIn;
    submodules:
        mobility: inet.mobility.static.StationaryMobility {
            @display("p=100,50");
        }
        nrNic: space_veins.modules.nic.SatelliteInterface {
            @display("p=100,120");
        }
    connections allowunconnected:
        radioIn --> nrNic.radioIn;
}

network NRNetwork
{
    parameters:
        @display("bgb=800,600");
        int numGNBs = default(2);
        int numUEs = default(10);
        string channelModel = default("UMa");
        bool carrierAggregationEnabled = default(true);
        bool beamformingEnabled = default(true);
        bool networkSlicingEnabled = default(true);
    submodules:
        nrManager: NRManager {
            parameters:
                channelModel = ancestor.channelModel;
                carrierAggregationEnabled = ancestor.carrierAggregationEnabled;
                beamformingEnabled = ancestor.beamformingEnabled;
                networkSlicingEnabled = ancestor.networkSlicingEnabled;
            @display("p=50,50");
        }
        radioMedium: inet.physicallayer.Ieee80211RadioMedium {
            @display("p=200,50");
        }
        gnb[numGNBs]: GNB {
            @display("p=400,100");
        }
        ue[numUEs]: UE {
            @display("p=400,300");
        }
    connections allowunconnected:
        // Connections managed by NRManager
}