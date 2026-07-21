#include "events/FeatureBar.h"
#include "transform/residualization/Residualization.h"

class TransformPipeline
{
   public:
    TransformPipeline();

    void onBar(const FeatureBar &stockBar, const FeatureBar &factorBar);

   private:
    ResidualizationTransformer<4, 1>  oneMin;
    ResidualizationTransformer<20, 1> fiveMin;
    ResidualizationTransformer<60, 1> fifteenMin;
};