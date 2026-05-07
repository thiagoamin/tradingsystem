#pragma once
#include <cstdint>

namespace MarketConstants
{
    /*
    kMicrosharesPerShare is done to prevent floating point errors
    and account for fractional shares down the line
    */
    constexpr int64_t kMicrosharesPerShare = 1'000'000;

}