#pragma once

/**
 * @file    MarketConstants.h
 * @author  Phi Lam (lamyenphi14@gmail.com)
 * @brief   Global fixed parameters and scaling constants for trading system logic.
 * @version 0.1
 * @date    2026-05-27
 * * @copyright Copyright (c) 2026
 * */

#include <cstdint>

namespace MarketConstants
{
// Conversion factor used to scale raw physical equity shares into integer micro-shares to eliminate
// floating-point rounding errors
constexpr int64_t kMicrosharesPerShare = 1'000'000;

} // namespace MarketConstants