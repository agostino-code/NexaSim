package artery.ntn;

import space_veins.modules.nic.SatelliteNic;

module GroundStation
{
    parameters:
        @networkNode;
        @display("i=device/antennatower");
        string nicType = default("space_veins.modules.nic.SatelliteNic");
    gates:
        input radioIn;
    submodules:
        nic: <nicType> {
            @display("p=100,100");
        }
        mobility: inet.mobility.static.StaticMobility {
            @display("p=100,200");
        }
    connections:
        radioIn --> nic.radioIn;
}
