#pragma once

#include <cstdint>

struct BarEvent
{
    int32_t instrumentId;

    int64_t startTimeStamp_ns;
    int64_t endTimeStamp_ns;
    int64_t interval_ns;

    double open;
    double high;
    double low;
    double close;

    int64_t volume;
    int32_t trade_count;
};