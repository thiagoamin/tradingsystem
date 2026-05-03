#pragma once

#include <cstdint>
#include "events/tick_event.h"

class BarBuilder
{
public:
    BarBuilder(int64_t interval_ns);
    ~BarBuilder();

    void onTick(TickEvent tick);

private:
    int64_t interval_ns_;
};