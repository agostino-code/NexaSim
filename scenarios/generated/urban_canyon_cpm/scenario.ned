package generated.urban_canyon_cpm;

import artery.ntn.ConstellationManager;
import artery.ntn.LEO_Satellite;
import artery.ntn.GroundStation;
import artery.ntn.UserTerminalNode;
import artery.nr.GNB;
import artery.nr.UE;
import inet.physicallayer.unitdisk.UnitDiskRadioMedium;

network GeneratedScenario
{
    parameters:
        @display("bgb=1200,800");
    submodules:
        constellationManager: ConstellationManager {
            parameters:
                constellationType = "starlink_shell";
                walkerT = 72;
                walkerP = 12;
                walkerF = 0;
                walkerAltitudeKm = 550;
                walkerInclinationDeg = 53.0;
                islEnabled = true;
            @display("p=50,50");
        }
        radioMedium: UnitDiskRadioMedium {
            @display("p=200,50");
        }
        nrRadioMedium: UnitDiskRadioMedium {
            @display("p=200,150");
        }
        satellite[72]: LEO_Satellite {
            @display("p=400,100");
        }
        groundStation[1]: GroundStation {
            @display("p=400,300");
        }
        gnb[3]: GNB {
            @display("p=600,100");
        }
        ue[18]: UE {
            @display("p=600,300");
        }
        userTerminal[18]: UserTerminalNode {
            @display("p=800,300");
        }
    connections allowunconnected:
        // Connections established dynamically by managers
}
