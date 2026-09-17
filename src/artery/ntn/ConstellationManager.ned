package artery.ntn;

import space_veins.modules.mobility.SGP4Mobility.SGP4Mobility;
import space_veins.modules.nic.SatelliteInterface;
import inet.physicallayer.common.packetlevel.RadioMedium;

simple ConstellationManager
{
    parameters:
        @display("i=block/network2");
        
        // Configuration file (YAML)
        string constellationConfigFile = default("");
        
        // Constellation type: walker_delta, walker_star, starlink_shell, custom
        string constellationType = default("starlink_shell");
        
        // Walker Delta parameters (T/P/F)
        int walkerT = default(72);
        int walkerP = default(12);
        int walkerF = default(0);
        double walkerAltitudeKm = default(550);
        double walkerInclinationDeg = default(53.0);
        
        // ISL configuration
        bool islEnabled = default(true);
        string islType = default("laser");  // laser | ka_band | v_band
        double islMaxRangeKm = default(5000);
        int islPortsPerSat = default(4);
        double islWavelengthNm = default(1550);
        double islTxPowerDbm = default(20);
        double islRxSensitivityDbm = default(-40);
        double islPointingAccuracyDeg = default(0.01);
        double islAcquisitionTimeMs = default(100);
        
        // Satellite defaults
        string satNicType = default("space_veins.modules.nic.SatelliteNic");
        string satIslNicType = default("artery.ntn.ISLNic");
        string satMobilityType = default("space_veins.modules.mobility.SGP4Mobility");
        string satManagerType = default("artery.ntn.LEO_SatelliteManager");
        double satTxPowerDbm = default(30);
        double satNoiseFigureDb = default(3);
        double satFrequencyGhz = default(28);
        double satBandwidthMhz = default(500);
        
        // Visibility update interval (seconds)
        double visibilityUpdateInterval = default(1.0);
        
        // Ground stations (configured via YAML or individually)
        // See createGroundStationModules() for parameter mapping
        
    gates:
        input radioIn;
        output radioOut;
}

module LEO_Satellite
{
    parameters:
        @networkNode;
        @display("i=device/satellite");
        int planeId = default(0);
        int satId = default(0);
        string islType = default("laser");
        int numISLPorts = default(4);
    gates:
        input radioIn;
        input islIn[];
        output islOut[];
    submodules:
        manager: LEO_SatelliteManager {
            @display("p=100,50");
        }
        mobility: inet.mobility.static.StationaryMobility {
            @display("p=100,120");
        }
        nic: SatelliteInterface {
            @display("p=100,200");
        }
        islNic[numISLPorts]: ISLNic {
            @display("p=100,270");
        }
    connections allowunconnected:
        radioIn --> nic.radioIn;
        // ISL connections would be established dynamically by ConstellationManager
}

module GroundStation
{
    parameters:
        @networkNode;
        @display("i=device/antennatower");
        double latitude = default(52.52);
        double longitude = default(13.41);
        double altitude = default(50);
        double elevationMaskDeg = default(10.0);
    gates:
        input radioIn;
        input feederIn;
    submodules:
        manager: GroundStationManager {
            @display("p=100,50");
        }
        userNic: SatelliteInterface {
            @display("p=100,120");
        }
        feederNic: SatelliteInterface {
            @display("p=100,200");
        }
        mobility: inet.mobility.static.StationaryMobility {
            @display("p=100,270");
        }
    connections allowunconnected:
        radioIn --> userNic.radioIn;
        feederIn --> feederNic.radioIn;
}

network NTNNetwork
{
    parameters:
        @display("bgb=1000,600");
        string constellationConfigFile = default("");
        string constellationType = default("starlink_shell");
        int walkerT = default(72);
        int walkerP = default(12);
        int walkerF = default(0);
        double walkerAltitudeKm = default(550);
        double walkerInclinationDeg = default(53.0);
        bool islEnabled = default(true);
        int numGroundStations = default(1);
    submodules:
        constellationManager: ConstellationManager {
            parameters:
                constellationConfigFile = ancestor.constellationConfigFile;
                constellationType = ancestor.constellationType;
                walkerT = ancestor.walkerT;
                walkerP = ancestor.walkerP;
                walkerF = ancestor.walkerF;
                walkerAltitudeKm = ancestor.walkerAltitudeKm;
                walkerInclinationDeg = ancestor.walkerInclinationDeg;
                islEnabled = ancestor.islEnabled;
            @display("p=50,50");
        }
        radioMedium: RadioMedium {
            @display("p=200,50");
        }
        satellite[ancestor.walkerT]: LEO_Satellite {
            @display("p=400,100");
        }
        groundStation[ancestor.numGroundStations]: GroundStation {
            @display("p=400,400");
        }
    connections allowunconnected:
        // Connections established dynamically by ConstellationManager
}