package artery.ntn;

simple ISLNic
{
    parameters:
        @display("i=block/antenna");
        
        // Link type: 0=laser, 1=ka_band, 2=v_band
        int linkType = default(0);
        
        // Laser parameters
        double wavelengthNm = default(1550);
        
        // RF parameters
        double frequencyGhz = default(23);
        
        // Common parameters
        double txPowerDbm = default(20);
        double rxSensitivityDbm = default(-40);
        double txApertureCm = default(10);
        double rxApertureCm = default(10);
        double pointingAccuracyDeg = default(0.01);
        double acquisitionTimeMs = default(100);
        double maxRangeKm = default(5000);
        double dataRateGbps = default(10);
        double beamDivergenceUrad = default(10);
        
        // Port identification
        int portIndex = default(0);
        int maxPorts = default(4);
        
    gates:
        input radioIn;
        output radioOut;
}