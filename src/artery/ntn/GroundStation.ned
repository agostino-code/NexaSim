package artery.ntn;

simple GroundStationManager
{
    parameters:
        @display("i=block/cogwheel");
        double elevationMaskDeg = default(10.0);
        double feederFrequencyGhz = default(28.0);
        double feederBandwidthMhz = default(1000.0);
        
        @signal[feederLinkActive](type=long);
        @signal[feederLinkSinr](type=double);
        @statistic[feederLinkActive](title="Feeder Link Active"; record=vector,last);
        @statistic[feederLinkSinr](title="Feeder Link SINR"; unit=dB; record=vector,mean);
}
