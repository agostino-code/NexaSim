package scenarios.nr_test;

import artery.nr.NRManager;
import simu5g.common.binder.Binder;
import simu5g.common.carrierAggregation.CarrierAggregation;

network NRTest
{
    submodules:
        binder: Binder {
            @display("p=50,50");
        }
        carrierAggregation: CarrierAggregation {
            @display("p=50,150");
        }
        nrManager: NRManager {
            @display("p=150,100");
        }
}
