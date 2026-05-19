package artery.ntn;

import space_veins.modules.mobility.SGP4Mobility;
import space_veins.modules.nic.SatelliteNic;

simple LEO_SatelliteManager
{
    parameters:
        @display("i=block/cogwheel");
        string satelliteName = default("");
}

module LEO_Satellite
{
    parameters:
        @networkNode;
        @display("i=device/satellite");
        string mobilityType = default("space_veins.modules.mobility.SGP4Mobility");
        string nicType = default("space_veins.modules.nic.SatelliteNic");
    gates:
        input radioIn;
    submodules:
        manager: LEO_SatelliteManager {
            parameters:
                satelliteName = default("");
            @display("p=100,50");
        }
        mobility: <mobilityType> like inet.mobility.contract.IMobility {
            @display("p=100,120");
        }
        nic: <nicType> {
            @display("p=100,200");
        }
    connections:
        radioIn --> nic.radioIn;
}
