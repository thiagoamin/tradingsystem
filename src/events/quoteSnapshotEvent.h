#pragma once

#include <cstdint>

// Quote snapshot event = internal (time-driven) event, final state before every 500ms
struct QuoteSnapshot
{
    int32_t instrumentId;
    int64_t timeStamp_ns; // absolute time in nanoseconds

    double bid;
    double ask;
    int64_t bidSize;
    int64_t askSize;
};