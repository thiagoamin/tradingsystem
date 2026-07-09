#pragma once

#include <cstddef>

template<size_t Window, size_t NumFactors>
class RollingEstimator
{
   public:
    RollingEstimator(size_t minObs, bool fitIntercept)
      : minObs_(minObs), fitIntercept_(fitIntercept)
    {
    }

   private:
    int window_;

    int  minObs_;
    bool fitIntercept_;

    // min orbs per factor or refit every
};