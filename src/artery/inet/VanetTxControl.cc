/*
* Artery V2X Simulation Framework
* Copyright 2020 Raphael Riebl
* Licensed under GPLv2, see COPYING file for detailed license and warranty terms.
*/

#include "artery/inet/VanetTxControl.h"

namespace artery
{

VanetTxControl::VanetTxControl(const VanetTxControl& other) :
    mDest(other.mDest),
    mSrc(other.mSrc),
    mEtherType(other.mEtherType),
    mUserPriority(other.mUserPriority),
    mTxRequest(other.getTransmissionRequest() ? other.getTransmissionRequest()->dup() : nullptr)
{
}

VanetTxControl& VanetTxControl::operator=(const VanetTxControl& other)
{
    if (&other != this) {
        mDest = other.mDest;
        mSrc = other.mSrc;
        mEtherType = other.mEtherType;
        mUserPriority = other.mUserPriority;
        const omnetpp::cObject* request = other.getTransmissionRequest();
        mTxRequest.reset(request ? request->dup() : nullptr);
    }
    return *this;
}

} // namespace artery
