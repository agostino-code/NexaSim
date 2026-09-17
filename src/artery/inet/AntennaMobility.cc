#include <artery/inet/AntennaMobility.h>
#include <omnetpp.h>

using namespace omnetpp;

namespace artery
{

Define_Module(AntennaMobility)

void AntennaMobility::initialize(int stage)
{
    omnetpp::cModule* module = getModuleByPath(par("mobilityModule"));
    mParentMobility = omnetpp::check_and_cast<inet::IMobility*>(module);

    mOffsetCoord.x = par("offsetX");
    mOffsetCoord.y = par("offsetY");
    mOffsetCoord.z = par("offsetZ");
    mOffsetAngles.alpha = inet::deg(par("offsetAlpha"));
    mOffsetAngles.beta = inet::deg(par("offsetBeta"));
    mOffsetAngles.gamma = inet::deg(par("offsetGamma"));
    mOffsetRotation = inet::Quaternion(mOffsetAngles);
}

int AntennaMobility::numInitStages() const
{
    return 1;
}

double AntennaMobility::getMaxSpeed() const
{
    return mParentMobility->getMaxSpeed();
}

inet::Coord AntennaMobility::getCurrentPosition()
{
    inet::Quaternion rot = mParentMobility->getCurrentAngularPosition();
    inet::Coord rotated_offset = rot.rotate(mOffsetCoord);
    return mParentMobility->getCurrentPosition() + rotated_offset;
}

inet::Coord AntennaMobility::getCurrentVelocity()
{
    return mOffsetRotation.rotate(mParentMobility->getCurrentVelocity());
}

inet::Coord AntennaMobility::getCurrentAcceleration()
{
    return inet::Coord::ZERO;
}

inet::Quaternion AntennaMobility::getCurrentAngularPosition()
{
    return mParentMobility->getCurrentAngularPosition() * mOffsetRotation;
}

inet::Quaternion AntennaMobility::getCurrentAngularVelocity()
{
    return inet::Quaternion::IDENTITY;
}

inet::Quaternion AntennaMobility::getCurrentAngularAcceleration()
{
    return inet::Quaternion::IDENTITY;
}

inet::Coord AntennaMobility::getConstraintAreaMax() const
{
    inet::Coord offset = mParentMobility->getConstraintAreaMax() + mOffsetCoord;
    return offset.max(mParentMobility->getConstraintAreaMax());
}

inet::Coord AntennaMobility::getConstraintAreaMin() const
{
    inet::Coord offset = mParentMobility->getConstraintAreaMin() + mOffsetCoord;
    return offset.min(mParentMobility->getConstraintAreaMin());
}

} // namespace artery
