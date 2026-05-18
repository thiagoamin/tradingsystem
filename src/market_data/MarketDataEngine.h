#pragma once

#include "events/TradeTick.h"
#include "market_data/BarBuilder.h"
#include "InstrumentMarketState.h"
#include "core/InstrumentId.h"

#include <unordered_map>

class MarketDataEngine
{
public:
    MarketDataEngine() = default;
    ~MarketDataEngine() = default;
    void onTradeTick(const TradeTick &tick);

private:
    std::unordered_map<InstrumentId, InstrumentMarketState> instrumentStates_;
};