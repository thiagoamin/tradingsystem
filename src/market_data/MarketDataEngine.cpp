#include "MarketDataEngine.h"

void MarketDataEngine::onTradeTick(const TradeTick &tick)
{
    // Try to emplace. If tick.instrumentId isn't found, it constructs an
    // InstrumentMarketState passing tick.instrumentId as the constructor argument to make InstrumentMarketState(tick.instrumentId)
    auto [it, inserted] = instrumentStates_.try_emplace(tick.instrumentId, tick.instrumentId);
    it->second.onTick(tick);
};