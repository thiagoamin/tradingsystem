#pragma once
#include "events/TradeTick.h"
#include "events/FeatureBar.h"
#include "market_data/TradeBucket.h"

#include <vector>

class InstrumentMarketState
{
public:
    void onTick(const TradeTick &tick);

private:
    TradeBucket activeBucket_;
    // bar builder?
    std::vector<FeatureBar> bars_15s_;
};