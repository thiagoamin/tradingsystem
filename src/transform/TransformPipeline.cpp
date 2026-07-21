#include "TransformPipeline.h"

TransformPipeline::TransformPipeline() : oneMin(4, true), fiveMin(20, true), fifteenMin(60, true) {}

void TransformPipeline::onBar(const FeatureBar &stockBar, const FeatureBar &factorBar)
{
    // compute return on stock bar
    // compute return on factor bar
    // double stockReturn  = (stockBar.close - lastStockClose_) / lastStockClose_;
    // double factorReturn = (factorBar.close - lastFactorClose_) / lastFactorClose_;
    // lastStockClose_     = stockBar.close;
    // lastFactorClose_    = factorBar.close;

    // residualizer transform with my stock + factor return

    // residual factor
}
