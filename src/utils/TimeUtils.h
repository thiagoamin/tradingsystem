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

namespace TimeUtils
{
    constexpr int64_t kNanosecondsPerSecond = 1'000'000'000LL; // k = constants

    /**
     * @brief Monotonic clock tracking duration since an unspecified epoch (system boot).
     *
     * @note Guarantees strict linearity. Ideal for internal system profiling and delta latency measurements.
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
     * @note Represents Unix Epoch time. Ideal for measuring external network flight delays against exchange prints,
     * but can jump if OS time adjusts.
     */
    inline int64_t wall_time_ns()
    {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
                   std::chrono::system_clock::now().time_since_epoch())
            .count();
    }
}