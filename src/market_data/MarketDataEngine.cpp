#include "MarketDataEngine.h"

void MarketDataEngine::onTradeTick(const TradeTick &tick)
{
    instrumentStates_[tick.instrumentId].onTick(tick);
};