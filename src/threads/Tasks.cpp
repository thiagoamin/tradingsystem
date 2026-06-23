#include <thread>
#include <atomic>

#include "Tasks.h"
#include "utils/TimeUtils.h"

Tasks::Tasks(
    MarketDataEngine                  &engine,
    rigtorp::SPSCQueue<TradeTick>     &tick,
    rigtorp::SPSCQueue<QuoteSnapshot> &quote)
  : engine_(engine),
    tickBuffer_(tick),
    quoteBuffer_(quote),
    running_{ false },
    flushSignal_{ false }
{
}

Tasks::~Tasks()
{
    if (engineThread_.joinable())
        engineThread_.join();
    if (timerThread_.joinable())
        timerThread_.join();
}

void Tasks::start()
{
    running_.store(true);

    // Engine thread (#1)
    engineThread_ = std::thread(&Tasks::engineTask, this);

    // Timer thread (#2)
    timerThread_ = std::thread(&Tasks::timerTask, this);
}

void Tasks::stop()
{
    running_.store(false);

    engineThread_.join();
    timerThread_.join();
}

void Tasks::engineTask()
{
    while (running_.load(std::memory_order_relaxed))
    {
        if (flushSignal_.load(std::memory_order_acquire))
        {
            int64_t boundaryId = TimeUtils::wallTime_ns() / TimeUtils::kFifteenSec_ns - 1;
            engine_.flush(boundaryId);
            flushSignal_.store(false, std::memory_order_release);
        }

        TradeTick *tick = tickBuffer_.front();
        if (tick)
        {
            engine_.onTradeTick(*tick);
            tickBuffer_.pop();
        }

        QuoteSnapshot *quote = quoteBuffer_.front();
        if (quote)
        {
            engine_.onQuoteSample(*quote);
            quoteBuffer_.pop();
        }
    }
}

void Tasks::timerTask()
{
    while (running_.load(std::memory_order_relaxed))
    {
        // calculate next 15s boundary
        auto now_ns = TimeUtils::wallTime_ns();

        int64_t next_boundary = (now_ns / TimeUtils::kFifteenSec_ns + 1) *
                                TimeUtils::kFifteenSec_ns; // start at boundary 15s instead of 0
        int64_t sleep_ns      = next_boundary - now_ns;

        std::this_thread::sleep_for(std::chrono::nanoseconds(sleep_ns));
        flushSignal_.store(true, std::memory_order_release);
    }
}