/*
* Artery V2X Simulation Framework
* Copyright 2020 Raphael Riebl
* Licensed under GPLv2, see COPYING file for detailed license and warranty terms.
*/

#ifndef ARTERY_VANETRXCONTROL_H_YHJMCGWD
#define ARTERY_VANETRXCONTROL_H_YHJMCGWD

#include <inet/linklayer/common/MacAddress.h>
#include <omnetpp/cobject.h>
#include <memory>

namespace artery
{

class VanetRxControl : public omnetpp::cObject
{
public:
    using ReceptionIndication = omnetpp::cObject;

    VanetRxControl() = default;
    VanetRxControl(const VanetRxControl& other);
    VanetRxControl& operator=(const VanetRxControl& other);
    VanetRxControl* dup() const override { return new VanetRxControl(*this); }

    void setDest(const inet::MacAddress& addr) { mDest = addr; }
    const inet::MacAddress& getDest() const { return mDest; }

    void setSrc(const inet::MacAddress& addr) { mSrc = addr; }
    const inet::MacAddress& getSrc() const { return mSrc; }

    void setEtherType(int eth) { mEtherType = eth; }
    int getEtherType() const { return mEtherType; }

    void setUserPriority(int up) { mUserPriority = up; }
    int getUserPriority() const { return mUserPriority; }

    void setReceptionIndication(omnetpp::cObject* rx) { mRxIndication.reset(rx); }
    omnetpp::cObject* getReceptionIndication() { return mRxIndication.get(); }
    const omnetpp::cObject* getReceptionIndication() const { return mRxIndication.get(); }
    omnetpp::cObject* removeReceptionIndication() { return mRxIndication.release(); }

private:
    inet::MacAddress mDest;
    inet::MacAddress mSrc;
    int mEtherType = 0;
    int mUserPriority = 0;
    std::unique_ptr<omnetpp::cObject> mRxIndication;
};

} // namespace artery

#endif /* ARTERY_VANETRXCONTROL_H_YHJMCGWD */

