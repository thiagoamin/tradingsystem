#pragma once

/**
 * @file MarketDataEngine.h
 * @author  Phi Lam (lamyenphi14@gmail.com)
 * @brief   Central routing engine for streaming real-time market data.
 *
 * This module acts as the orchestrator for incoming network events. It consumes
 * raw trade prints and throttled book snapshots, lazily initializing and dispatching
 * them to their respective asset state machines for streaming feature extraction.
 *
 * @version 0.1
 * @date 2026-05-27
 *
 * @copyright Copyright (c) 2026
 *
 */

#include <array>

#include "InstrumentMarketState.h"
#include "core/InstrumentId.h"
#include "events/QuoteSnapshot.h"
#include "events/TradeTick.h"

/**
 * @brief Central pipeline engine processing inbound streaming market data feeds.
 *
 * @details Routes live transaction trades and quote book snapshots down to
 * their respective instrument state machines for real-time feature generation.
 */
class MarketDataEngine
{
   public:
    MarketDataEngine();

    /**
     * @brief Ingests an external, market-driven trade execution event.
     *
     * @param tick Inbound execution tick data.
     */
    void onTradeTick(const TradeTick &tick);

    /**
     * @brief Ingests an internal, time-driven top-of-book state observation.
     *
     * @param quote Inbound top-of-book snapshot data.
     */
    void onQuoteSample(const QuoteSnapshot &quote);

    /**
     * @brief runs InstrumentMarketState build() for all of the instruments/stocks
     *
     * @param id bar ID for 15s bars
     */
    void flush(int64_t id);

    /**
     * @brief swap active bucket (where engine thread pops off ring buffer and write to) and flush
     * bucket (bucket that will be read from to build bars) to prevent race conditions
     *
     */
    void preFlush();

   private:
    ///< State registry mapping instrument IDs to their data caches.
    std::array<InstrumentMarketState, kNumInstruments> instrumentStates_;

#ifdef TEST
   public:
    /* ---------------------- Helper Functions for Testing ---------------------- */
    const InstrumentMarketState *getState(InstrumentId id) const
    {
        size_t idx = static_cast<size_t>(id);
        if (idx >= kNumInstruments)
            return nullptr;
        return &instrumentStates_[idx];
    }
#endif
};