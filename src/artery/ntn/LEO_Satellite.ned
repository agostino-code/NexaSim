package artery.ntn;

import space_veins.modules.mobility.SGP4Mobility;
import space_veins.modules.nic.SatelliteNic;

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
        mobility: <mobilityType> like inet.mobility.contract.IMobility {
            @display("p=100,100");
        }
        nic: <nicType> {
            @display("p=100,200");
        }
    connections:
        radioIn --> nic.radioIn;
}
