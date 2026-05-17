#pragma once

#include <cstdint>
#include "events/TradeTick.h"

class BarBuilder
{
public:
    BarBuilder(int64_t interval_ns);
    ~BarBuilder();

    void onTick(TradeTick tick);

private:
    int64_t interval_ns_;
};