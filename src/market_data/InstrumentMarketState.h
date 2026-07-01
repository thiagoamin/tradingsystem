#pragma once

/**
 * @file InstrumentMarketState.h
 * @author your name (you@domain.com)
 * @brief Isolated data container and feature tracking machine per instrument.
 *
 * This module encapsulates the running state of a single asset. It caches
 * top-of-book metrics to compute microstructure indicators and buffers into
 * standardized mathematical 15-second feature bars for strategy ingestion.
 *
 * @version 0.1
 * @date 2026-05-27
 *
 * @copyright Copyright (c) 2026
 *
 */

#include <vector>

#include "core/InstrumentId.h"
#include "events/FeatureBar.h"
#include "events/QuoteSnapshot.h"
#include "events/TradeTick.h"
#include "market_data/MarketBucket.h"

/**
 * @brief State container and aggregator for a single instrument's market data.
 *
 * @details Tracks top-of-book state and aggregates transactional metrics into
 * rolling historical 15-second feature bars.
 */
class InstrumentMarketState
{
   public:
    /**
     * @brief Constructs an isolated state machine for a specific asset.
     *
     * @param id Unique internal tracking token for the target asset.
     */
    explicit InstrumentMarketState(InstrumentId id);

    /**
     * @brief Updates transaction volume metrics and price statistics using an inbound trade print.
     *
     * @param tick The raw execution tick data.
     */
    void onTick(const TradeTick &tick);

    /**
     * @brief Caches the latest top-of-book snapshot and recalculates microstructural indicators.
     *
     * @param quote The raw quote snapshot.
     */
    void onQuote(const QuoteSnapshot &quote);

    /**
     * @brief Run build if there is data in activeBucket_ and clears activeBucket_
     *
     * @param boundaryId ID for the 15s bucket
     */
    void build(int64_t boundaryId);

    void swapBuckets() noexcept { std::swap(activeBucket_, flushBucket_); }

   private:
    InstrumentId  instrumentId_;
    uint32_t      lastSeenSeq_;
    QuoteSnapshot latestQuote_;  ///< Cached recent quote snapshot.
    MarketBucket  activeBucket_; // consumer writes here
    MarketBucket  flushBucket_;  // flush reads here

    std::vector<FeatureBar> bars_15s_; ///< Historical storage array of finalized 15-second
                                       ///< intervals used for Strategy.

   public:
    /* -------------------------------------------------------------------------- */
    /*                        Helper Functions for Testing                        */
    /* -------------------------------------------------------------------------- */

    const std::vector<FeatureBar> &getBars() const { return bars_15s_; }

    size_t barCount() const { return bars_15s_.size(); }
};