#pragma once
#include "events/TradeTick.h"
#include "events/FeatureBar.h"
#include "market_data/TradeBucket.h"
#include "core/InstrumentId.h"

#include <vector>

class InstrumentMarketState
{
public:
    explicit InstrumentMarketState(InstrumentId id);

    void onTick(const TradeTick &tick);

private:
    InstrumentId instrumentId_;
    TradeBucket activeBucket_;
    std::vector<FeatureBar> bars_15s_;
};