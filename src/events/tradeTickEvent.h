#pragma once

#include <cstdint>

using TickerId = long;

// Trade tick even = external (market-driven) event
struct TradeTick
{
    int32_t instrumentId;
    int64_t timeStamp_ns; // absolute time in nanoseconds
    double price;
    int64_t size;
};