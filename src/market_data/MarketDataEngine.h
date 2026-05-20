#pragma once

#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "market_data/BarBuilder.h"
#include "InstrumentMarketState.h"
#include "core/InstrumentId.h"

#include <unordered_map>

class MarketDataEngine
{
public:
    void onTradeTick(const TradeTick &tick);
    void onQuoteSample(const QuoteSnapshot &quote);

private:
    std::unordered_map<InstrumentId, InstrumentMarketState> instrumentStates_;
};