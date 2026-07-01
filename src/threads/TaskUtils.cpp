#include <atomic>
#include <thread>

#include "TaskUtils.h"
#include "utils/TimeUtils.h"

void runEngineLoop(
    std::atomic<bool>                 &running,
    std::atomic<bool>                 &flushSignal,
    rigtorp::SPSCQueue<TradeTick>     &tickBuffer,
    rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer,
    MarketDataEngine                  &engine)
{
    while (running.load(std::memory_order_relaxed))
    {
        if (flushSignal.load(std::memory_order_acquire))
        {
            int64_t boundaryId = TimeUtils::wallTime_ns() / TimeUtils::kFifteenSec_ns - 1;
            engine.flush(boundaryId);
            flushSignal.store(false, std::memory_order_release);
        }

        TradeTick *tick = tickBuffer.front();
        if (tick)
        {
            engine.onTradeTick(*tick);
            tickBuffer.pop();
        }

        QuoteSnapshot *quote = quoteBuffer.front();
        if (quote)
        {
            engine.onQuoteSample(*quote);
            quoteBuffer.pop();
        }
    }
}

void runTimerLoop(std::atomic<bool> &running, std::atomic<bool> &flushSignal, int64_t interval)
{
    while (running.load(std::memory_order_relaxed))
    {
        // calculate next 15s boundary
        auto now_ns = TimeUtils::wallTime_ns();

        int64_t next_boundary =
            (now_ns / interval + 1) * interval; // start at boundary 15s instead of 0
        int64_t sleep_ns = next_boundary - now_ns;

        std::this_thread::sleep_for(std::chrono::nanoseconds(sleep_ns));
        flushSignal.store(true, std::memory_order_release);
    }
}