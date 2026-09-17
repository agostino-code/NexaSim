#ifndef ARTERY_ANTENNAMOBILITY_H_BMWHZWNJ
#define ARTERY_ANTENNAMOBILITY_H_BMWHZWNJ

#include <inet/mobility/contract/IMobility.h>
#include <inet/common/geometry/common/EulerAngles.h>
#include <inet/common/geometry/common/Quaternion.h>

namespace artery
{

class AntennaMobility : public inet::IMobility, public omnetpp::cSimpleModule
{
public:
    // inet::IMobility interface
    double getMaxSpeed() const override;
    inet::Coord getCurrentPosition() override;
    inet::Coord getCurrentVelocity() override;
    inet::Coord getCurrentAcceleration() override;
    inet::Quaternion getCurrentAngularPosition() override;
    inet::Quaternion getCurrentAngularVelocity() override;
    inet::Quaternion getCurrentAngularAcceleration() override;
    inet::Coord getConstraintAreaMax() const override;
    inet::Coord getConstraintAreaMin() const override;

    // omnetpp::cSimpleModule
    void initialize(int stage) override;
    int numInitStages() const override;

private:
    inet::IMobility* mParentMobility = nullptr;
    inet::Coord mOffsetCoord;
    inet::EulerAngles mOffsetAngles;
    inet::Quaternion mOffsetRotation;
};

} // namespace artery

#endif /* ARTERY_ANTENNAMOBILITY_H_BMWHZWNJ */
