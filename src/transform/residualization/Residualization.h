#pragma once

#include "transform/Transformer.h"
#include "transform/residualization/RollingEstimator.h"

template<size_t Window, size_t NumFactors>
class ResidualizationTransformer
{
   public:
    ResidualizationTransformer(size_t minObs, bool fitIntercept) : estimator_(minObs, fitIntercept)
    {
    }

    double transform(const FeatureBar &stockBar, const FeatureBar &factorBar);

   private:
    double computeReturn(double price, double &lastPrice);
    double lastStockClose_;
    double lastFactorClose_;

    RollingEstimator<Window, NumFactors> estimator_;
};

// static_assert(transform::Transformer<ResidualizationTransformer>); not true rn