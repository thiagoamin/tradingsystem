#include "Tasks.h"
#include "TaskUtils.h"

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
    timerThread_ = std::thread(&Tasks::timerTask, this, TimeUtils::kFifteenSec_ns);
}

void Tasks::stop()
{
    running_.store(false);

    engineThread_.join();
    timerThread_.join();
}

void Tasks::engineTask()
{
    runEngineLoop(running_, flushSignal_, tickBuffer_, quoteBuffer_, engine_);
}

void Tasks::timerTask(int64_t interval)
{
    runTimerLoop(running_, flushSignal_, interval);
}