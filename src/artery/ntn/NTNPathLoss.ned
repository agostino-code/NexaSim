package artery.ntn;

import inet.physicallayer.pathloss.FreeSpacePathLoss;

module NTNPathLoss extends FreeSpacePathLoss
{
    parameters:
        double rainRateMmPerH = default(0.0);
        double cloudLiquidWater = default(0.0);
        double elevationMaskDeg = default(10.0);
        bool atmosphericLossEnabled = default(true);
        string environmentType = default("suburban");
        @class(NTNPathLoss);
        @display("i=block/control");
}
