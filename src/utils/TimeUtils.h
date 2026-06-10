#pragma once

/**
 * @file TimeUtils.h
 * @brief   High-resolution clock utilities for latency tracking and epoch synchronization.
 * @brief
 * @version 0.1
 * @date 2026-05-27
 *
 * @copyright Copyright (c) 2026
 *
 */
#include <chrono>
#include <cstdint>
#include <string>

namespace TimeUtils
{
constexpr int64_t kNanosecondsPerSecond = 1'000'000'000LL; // k = constants

/**
 * @brief Initialize timezone to Eastern Time
 *
 */
inline void init()
{
    setenv("TZ", "America/New_York", 1);
    tzset();
}

/**
 * @brief Monotonic clock tracking duration since an unspecified epoch (system boot).
 *
 * @note Guarantees strict linearity. Ideal for internal system profiling and delta latency
 * measurements.
 */
inline int64_t steady_time_ns()
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

/**
 * @brief Wall-clock time tied directly to the system's real-time calendar clock.
 *
 * @note Represents Unix Epoch time. Ideal for measuring external network flight delays against
 * exchange prints, but can jump if OS time adjusts.
 */
inline int64_t wall_time_ns()
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

inline std::string getCurrentDate()
{
    // 1. time right now
    auto now = std::chrono::system_clock::now();
    // 2. convert time to system day precision
    auto current_day = std::chrono::floor<std::chrono::days>(now);
    // 3. convert to year-month-day
    std::chrono::year_month_day today{ current_day };

    return std::format(
        "{:04}_{:02}_{:02}", (int)today.year(), (unsigned)today.month(), (unsigned)today.day());
}
} // namespace TimeUtils