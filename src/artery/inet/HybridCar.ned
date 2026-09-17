package artery.inet;

import artery.application.VehicleMiddleware;
import artery.networking.Vanetza;
import artery.nic.IRadioDriver;
import artery.ntn.UserTerminal;
import inet.node.inet.INetworkNode;
import inet.linklayer.contract.IWirelessNic;
import inet.mobility.contract.IMobility;
import inet.networklayer.common.InterfaceTable;
import space_veins.modules.nic.SatelliteInterface;

//
// HybridCar provides a 3D Unified Terrestrial & Non-Terrestrial Network (TN-NTN)
// vehicular node for NexaSim. Integrates V2X (ETSI ITS-G5), NTN LEO UserTerminal
// with phased-array antenna tracking, and TraCI vehicle mobility.
//
module HybridCar like INetworkNode
{
    parameters:
        @display("i=block/wrxtx;is=vs");
        @networkNode;
        @labels(node,ethernet-node,wireless-node);

        @statistic[posX](source="xCoord(mobilityPos(mobilityStateChanged))"; record=vector?);
        @statistic[posY](source="yCoord(mobilityPos(mobilityStateChanged))"; record=vector?);

        int numRadios = default(1);
        bool withAntennaMobility = default(false);
        bool enableNTN = default(true);
        *.interfaceTableModule = default(absPath(".interfaceTable"));
        mobility.visualRepresentation = "^";

    gates:
        input radioIn[numRadios] @directIn;
        input satRadioIn @directIn;
        inout pppg[] @labels(PPPFrame-conn);
        inout ethg[] @labels(EtherFrame-conn);

    submodules:
        interfaceTable: InterfaceTable {
            parameters:
                @display("p=50,300");
        }

        wlan[numRadios]: <default("VanetNic")> like IWirelessNic {
            parameters:
                @display("p=250,400,row,100;q=queue");
                radio.antenna.mobilityModule = absPath(withAntennaMobility ? "^.antennaMobility" : "^.mobility");
        }

        antennaMobility: AntennaMobility if withAntennaMobility == true {
            parameters:
                @display("p=100,200");
                mobilityModule = "^.mobility";
        }

        radioDriver[numRadios]: RadioDriver {
            parameters:
                @display("p=250,300,row,100");
                macModule = ".wlan[" + string(index) + "].mac";
                radioModule = ".wlan[" + string(index) + "].radio";
        }

        vanetza[numRadios]: Vanetza {
            parameters:
                @display("p=250,200,row,100");
                *.middlewareModule = absPath("^.middleware");
                *.mobilityModule = absPath("^.mobility");
                *.radioDriverModule = absPath("^.radioDriver[" + string(index) + "]");
                runtime.datetime = middleware.datetime;
        }

        userTerminal: UserTerminal if enableNTN == true {
            parameters:
                @display("p=400,200");
                terminalType = "mobility";
                dualConnectivityEnabled = true;
        }

        satNic: SatelliteInterface if enableNTN == true {
            parameters:
                @display("p=400,300");
        }

        mobility: <default("artery.inet.VehicleMobility")> like IMobility {
            parameters:
                @display("p=50,200");
        }

        middleware: VehicleMiddleware {
            parameters:
                @display("p=250,100");
                mobilityModule = ".mobility";
        }

    connections allowunconnected:
        for i=0..sizeof(radioIn)-1 {
            radioIn[i] --> { @display("m=s"); } --> wlan[i].radioIn;

            wlan[i].upperLayerOut --> radioDriver[i].lowerLayerIn;
            wlan[i].upperLayerIn <-- radioDriver[i].lowerLayerOut;

            radioDriver[i].upperLayer <--> vanetza[i].radioDriverData;
            radioDriver[i].properties --> vanetza[i].radioDriverProperties;
        }

        satRadioIn --> satNic.radioIn if enableNTN;
}
