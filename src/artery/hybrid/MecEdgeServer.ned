package artery.hybrid;

import inet.applications.contract.IApp;

simple MecEdgeServer like IApp
{
    parameters:
        @class(hybrid::MecEdgeServer);
        @display("i=block/server");
        
        int localPort = default(5000);
        double processingSpeedMips = default(10000.0); // 10000 MIPS
        
    gates:
        input socketIn;
        output socketOut;
}
