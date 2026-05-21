#pragma once

#include <cstdint>
#include "core/InstrumentId.h"

// Quote snapshot event = internal (time-driven) event, final state before every 500ms
struct QuoteSnapshot
{
    InstrumentId instrumentId;
    int64_t timeStamp_ns; // absolute time in nanoseconds

    double bid;
    double ask;
    int64_t bidSize_us; // 1 share = 1,000,000 micro shares
    int64_t askSize_us; // 1 share = 1,000,000 micro shares

    // TODO: features needed later?
    // bidConditions
    // askConditions
    // bidExchanges
    // askExchanges
};