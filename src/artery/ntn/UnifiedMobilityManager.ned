package artery.ntn;

simple UnifiedMobilityManager
{
    parameters:
        @display("i=block/network2");
        
        // Handover policy thresholds
        double rsrpThresholdDbm = default(-110);
        double rsrqThresholdDb = default(-15);
        double sinrThresholdDb = default(-5);
        double elevationThresholdDeg = default(25);
        double elevationMinDeg = default(15);
        
        // Hysteresis and timing
        double hysteresisDb = default(3.0);
        double timeToTriggerMs = default(160);
        double maxHandoverDurationMs = default(50);
        
        // Make-before-break
        bool makeBeforeBreak = default(true);
        double mbBOverlapMs = default(20);
        
        // Load balancing
        double loadThreshold = default(0.8);
        bool loadBalancingEnabled = default(true);
        
        // QoS-based steering
        bool qosBasedSteering = default(true);
        
        // Dual connectivity
        bool dualConnectivityEnabled = default(true);
        
        // Evaluation interval
        double evaluationIntervalMs = default(100);
        
    gates:
        input radioIn;
        output radioOut;
}