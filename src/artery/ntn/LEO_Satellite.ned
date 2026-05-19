package artery.ntn;

simple LEO_Satellite
{
    parameters:
        @display("i=device/satellite");
        string satelliteName = default("LEO_1");
    gates:
        input radioIn;
        output radioOut;
}
