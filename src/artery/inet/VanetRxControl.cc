/*
* Artery V2X Simulation Framework
* Copyright 2020 Raphael Riebl
* Licensed under GPLv2, see COPYING file for detailed license and warranty terms.
*/

#include "artery/inet/VanetRxControl.h"

namespace artery
{

VanetRxControl::VanetRxControl(const VanetRxControl& other) :
    mDest(other.mDest),
    mSrc(other.mSrc),
    mEtherType(other.mEtherType),
    mUserPriority(other.mUserPriority),
    mRxIndication(other.getReceptionIndication() ? other.getReceptionIndication()->dup() : nullptr)
{
}

VanetRxControl& VanetRxControl::operator=(const VanetRxControl& other)
{
    if (&other != this) {
        mDest = other.mDest;
        mSrc = other.mSrc;
        mEtherType = other.mEtherType;
        mUserPriority = other.mUserPriority;
        const omnetpp::cObject* indication = other.getReceptionIndication();
        mRxIndication.reset(indication ? indication->dup() : nullptr);
    }
    return *this;
}

} // namespace artery
