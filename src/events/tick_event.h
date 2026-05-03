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
    TickerId tickerId;
    MarketTickType tickType;
    double price;
    int64_t timeStamp_ns; // absolute time in nanoseconds
};