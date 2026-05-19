package scenarios.ntn;

import artery.ntn.LEO_Satellite;
import artery.ntn.GroundStation;
import space_veins.modules.world.RadioMedium;

network NTNTest
{
    submodules:
        radioMedium: RadioMedium {
            @display("p=50,50");
        }
        satellite: LEO_Satellite {
            @display("p=200,100");
        }
        groundStation: GroundStation {
            @display("p=200,300");
        }
}
