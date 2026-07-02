#pragma once

#include "rigtorp/SPSCQueue.h"

#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "market_data/MarketDataEngine.h"

void runEngineLoop(
    std::atomic<bool>                 &running,
    std::atomic<bool>                 &flushSignal,
    std::atomic<bool>                 &buildSignal_,
    rigtorp::SPSCQueue<TradeTick>     &tickBuffer,
    rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer,
    MarketDataEngine                  &engine);

void runBuildLoop(
    std::atomic<bool> &running,
    std::atomic<bool> &buildSignal,
    MarketDataEngine  &engine);

void runTimerLoop(std::atomic<bool> &running, std::atomic<bool> &flushSignal, int64_t interval);