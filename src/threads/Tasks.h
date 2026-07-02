#pragma once

/**
 * @file Tasks.h
 * @author Phi Lam (lamyenphi14@gmail.com)
 * @brief Owns and manages engine and timer threads for the trading system.
 *
 * Acts as the transport layer between IBKR's SPSCQueues and MarketDataEngine,
 * draining tick and quote buffers on the engine thread and firing flush signals
 * on 15s bar boundaries via the timer thread.
 *
 * @version 0.1
 * @version 0.1
 * @date 2026-06-23
 *
 * @copyright Copyright (c) 2026
 *
 */

#include <thread>
#include <atomic>

#include "utils/TimeUtils.h"
#include "rigtorp/SPSCQueue.h"

#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "market_data/MarketDataEngine.h"

/**
 * @class Tasks
 * @brief  Owns engine and timer threads, draining SPSCQueues into MarketDataEngine on the engine
 * thread and firing 15s flush signals on the timer thread.
 *
 */
class Tasks
{
   public:
    /**
     * @brief Constructs Tasks with references to the engine and data buffers.
     *
     * @param engine  MarketDataEngine to process ticks and quotes
     * @param tick    SPSCQueue of incoming trade ticks from IBKR
     * @param quote   SPSCQueue of incoming quote snapshots from IBKR
     */
    Tasks(
        MarketDataEngine                  &engine,
        rigtorp::SPSCQueue<TradeTick>     &tick,
        rigtorp::SPSCQueue<QuoteSnapshot> &quote);

    /**
     * @brief Joins any running threads if not already stopped.
     *
     */
    ~Tasks();
    void start();
    void stop();

   private:
    std::thread                        engineThread_;
    std::thread                        timerThread_;
    std::thread                        flushThread_;
    std::atomic<bool>                  running_;
    std::atomic<bool>                  flushSignal_;
    std::atomic<bool>                  buildSignal_;
    MarketDataEngine                  &engine_;
    rigtorp::SPSCQueue<TradeTick>     &tickBuffer_;
    rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer_;

    /**
     * @brief Fires flush signal on 15s bar boundaries
     *
     */
    void timerTask(int64_t interval = TimeUtils::kFifteenSec_ns);

    /**
     * @brief Drains tick and quote buffers into MarketDataEngine, acts as transport layer taking
     * data from ring buffer and giving it to the MarketDataEngine
     *
     */
    void engineTask();

    /**
     * @brief Flushes the InstrumentMarketState cache and builds FeatureBars for strategies
     *
     */
    void flushTask();
};
