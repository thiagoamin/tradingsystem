#include "MarketDataEngine.h"

// MarketDataEngine::MarketDataEngine() : {}

MarketDataEngine::~MarketDataEngine() {}

void MarketDataEngine::onTick(const TickEvent &tick)
{
    barBuilder_.onTick(tick);
};