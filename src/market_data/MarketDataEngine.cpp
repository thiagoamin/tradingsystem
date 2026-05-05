#include "MarketDataEngine.h"

// MarketDataEngine::MarketDataEngine() : {}

MarketDataEngine::~MarketDataEngine() {}

void MarketDataEngine::onTick(const TradeTick &tick)
{
    barBuilder_.onTick(tick);
};