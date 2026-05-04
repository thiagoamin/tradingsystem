#pragma once

#include <cstdint>

using TickerId = long;

enum class MarketTickType
{
    Bid,
    Ask,
    Last,
    DelayedBid,
    DelayedAsk,
    DelayedLast,
    Unknown
};

struct TickEvent
{
    int32_t instrumentId;

    int64_t timeStamp_ns; // absolute time in nanoseconds
    MarketTickType tickType;

    double price;
    long long size;
};