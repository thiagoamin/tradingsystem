#pragma once

#include <cstdint>

struct BarEvent
{
    int32_t barId;
    double price;
    int64_t timeStamp_ms;
};