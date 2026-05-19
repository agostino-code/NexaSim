package artery.ntn;

import space_veins.modules.nic.SatelliteNic;

simple GroundStationManager
{
    parameters:
        @display("i=block/cogwheel");
}

module GroundStation
{
    parameters:
        @networkNode;
        @display("i=device/antennatower");
        string nicType = default("space_veins.modules.nic.SatelliteNic");
    gates:
        input radioIn;
    submodules:
        manager: GroundStationManager {
            @display("p=100,50");
        }
        nic: <nicType> {
            @display("p=100,120");
        }
        mobility: inet.mobility.static.StaticMobility {
            @display("p=100,200");
        }
    connections:
        radioIn --> nic.radioIn;
}
