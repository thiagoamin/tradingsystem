#pragma once

#include "events/tradeTickEvent.h"
#include "BarBuilder.h"

class MarketDataEngine
{
public:
    MarketDataEngine();
    ~MarketDataEngine();

private:
    void onTick(const TradeTick &tick);
    BarBuilder barBuilder_;
};