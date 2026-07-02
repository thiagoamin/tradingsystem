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
    flushSignal_{ false },
    buildSignal_{ false }
{
}

Tasks::~Tasks()
{
    if (engineThread_.joinable())
        engineThread_.join();
    if (flushThread_.joinable())
        flushThread_.join();
    if (timerThread_.joinable())
        timerThread_.join();
}

void Tasks::start()
{
    running_.store(true);

    // Engine thread (#1)
    engineThread_ = std::thread(&Tasks::engineTask, this);

    // Engine thread (#2)
    flushThread_ = std::thread(&Tasks::flushTask, this);

    // Timer thread (#3)
    timerThread_ = std::thread(&Tasks::timerTask, this, TimeUtils::kFifteenSec_ns);
}

void Tasks::stop()
{
    running_.store(false);

    engineThread_.join();
    flushThread_.join();
    timerThread_.join();
}

void Tasks::engineTask()
{
    runEngineLoop(running_, flushSignal_, buildSignal_, tickBuffer_, quoteBuffer_, engine_);
}

void Tasks::flushTask()
{
    runBuildLoop(running_, buildSignal_, engine_);
}

void Tasks::timerTask(int64_t interval)
{
    runTimerLoop(running_, flushSignal_, interval);
}