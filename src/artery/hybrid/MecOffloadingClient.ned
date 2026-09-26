package artery.hybrid;

import inet.applications.contract.IApp;

simple MecOffloadingClient like IApp
{
    parameters:
        @class(hybrid::MecOffloadingClient);
        @display("i=block/app");
        
        int localPort = default(5000);
        int destPort = default(5000);
        
        string terrestrialEdgeAddress = default("");
        string satelliteEdgeAddress = default("");
        
        double taskGenerationInterval @unit(s) = default(1.0s);
        int taskSizeByte @unit(B) = default(1000B);
        int taskInstructions = default(10000000); // 10 Million instructions
        
        @signal[mecTaskLatency](type=double);
        @statistic[mecTaskLatency](title="MEC Task Latency (RTT + Compute)"; record=vector,mean,max; unit=s);
        
    gates:
        input socketIn;
        output socketOut;
}
