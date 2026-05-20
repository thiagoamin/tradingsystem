#pragma once

#include <cstdint>
#include <core/InstrumentId.h>

using TickerId = long;

// Trade tick even = external (market-driven) event
struct TradeTick
{
    InstrumentId instrumentId;
    int64_t exchangeTimestamp_ns; // IBKR time_t * 1e9, coarse
    int64_t recvSteadyTimestamp_ns;
    int64_t recvWallTimestamp_ns;
    double price;
    int64_t size_us;

    // TODO: do I need other features
};