#include <chrono>
#include <cstdint>

namespace TimeUtils
{
    constexpr int64_t kNanosecondsPerSecond = 1'000'000'000LL; // k = constants

    /* steady_time_ns

    Used to match Unix Epoch to check for network delay, can jump if OS time adjusts
    */
    inline int64_t steady_time_ns()
    {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
                   std::chrono::steady_clock::now().time_since_epoch())
            .count();
    }

    /* wall_time_ns

    Used for internal latency measurement as clock is monotonic
    */
    inline int64_t wall_time_ns()
    {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
                   std::chrono::system_clock::now().time_since_epoch())
            .count();
    }
}