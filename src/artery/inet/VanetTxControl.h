/*
* Artery V2X Simulation Framework
* Copyright 2020 Raphael Riebl
* Licensed under GPLv2, see COPYING file for detailed license and warranty terms.
*/

#ifndef ARTERY_VANETTXCONTROL_H_NXB5FIPT
#define ARTERY_VANETTXCONTROL_H_NXB5FIPT

#include <inet/linklayer/common/MacAddress.h>
#include <omnetpp/cobject.h>
#include <memory>

namespace artery
{

class VanetTxControl : public omnetpp::cObject
{
public:
    using TransmissionRequest = omnetpp::cObject;

    VanetTxControl() = default;
    VanetTxControl(const VanetTxControl& other);
    VanetTxControl& operator=(const VanetTxControl& other);
    VanetTxControl* dup() const override { return new VanetTxControl(*this); }

    void setDest(const inet::MacAddress& addr) { mDest = addr; }
    const inet::MacAddress& getDest() const { return mDest; }

    void setSrc(const inet::MacAddress& addr) { mSrc = addr; }
    const inet::MacAddress& getSrc() const { return mSrc; }

    void setEtherType(int eth) { mEtherType = eth; }
    int getEtherType() const { return mEtherType; }

    void setUserPriority(int up) { mUserPriority = up; }
    int getUserPriority() const { return mUserPriority; }

    void setTransmissionRequest(omnetpp::cObject* tx) { mTxRequest.reset(tx); }
    omnetpp::cObject* getTransmissionRequest() { return mTxRequest.get(); }
    const omnetpp::cObject* getTransmissionRequest() const { return mTxRequest.get(); }
    omnetpp::cObject* removeTransmissionRequest() { return mTxRequest.release(); }

private:
    inet::MacAddress mDest;
    inet::MacAddress mSrc;
    int mEtherType = 0;
    int mUserPriority = 0;
    std::unique_ptr<omnetpp::cObject> mTxRequest;
};

} // namespace artery

#endif /* ARTERY_VANETTXCONTROL_H_NXB5FIPT */

