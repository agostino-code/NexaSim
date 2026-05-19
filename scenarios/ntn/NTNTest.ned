package scenarios.ntn;

import artery.ntn.LEO_Satellite;
import artery.ntn.GroundStation;

network NTNTest
{
    submodules:
        satellite: LEO_Satellite;
        groundStation: GroundStation;
}
