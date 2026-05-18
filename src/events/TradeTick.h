#pragma once

#include <cstdint>
#include <core/InstrumentId.h>

using TickerId = long;

// Trade tick even = external (market-driven) event
struct TradeTick
{
    InstrumentId instrumentId;
    int64_t timeStamp_ns; // absolute time in nanoseconds
    double price;
    int64_t size;

    // TODO: do I need other features
};