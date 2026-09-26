namespace artery::hybrid;

packet MecTaskPacket {
    int taskId;
    long computationInstructions; // Number of instructions
    double generationTime;
    int routingDecision;
}
