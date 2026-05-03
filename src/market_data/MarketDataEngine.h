#pragma once

#include "events/tick_event.h"
#include "BarBuilder.h"

class MarketDataEngine
{
public:
    MarketDataEngine();
    ~MarketDataEngine();

private:
    void onTick(const TickEvent &tick);
    BarBuilder barBuilder_;
};