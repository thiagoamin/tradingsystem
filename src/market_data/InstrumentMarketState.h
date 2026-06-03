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

#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "events/FeatureBar.h"
#include "market_data/MarketBucket.h"
#include "core/InstrumentId.h"

#include <vector>

/**
 * @brief State container and aggregator for a single instrument's market data.
 *
 * @details Tracks top-of-book state and aggregates transactional metrics into
 * rolling historical 15-second feature bars.
 */
class InstrumentMarketState
{
public:
    static constexpr int64_t kFifteenSec_ns = 15'000'000'000LL;

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
     * @param quote The raw quote snapshot.
     */
    void onQuote(const QuoteSnapshot &quote);

private:
    InstrumentId instrumentId_;

    QuoteSnapshot latestQuote_; ///< Cached recent quote snapshot.
    bool hasNewQuote_;

    int64_t bucketId_15s_;      ///< Current bucket Id
    MarketBucket activeBucket_; ///< Current raw sub-window accumulation container for data filtering.

    std::vector<FeatureBar> bars_15s_; ///< Historical storage array of finalized 15-second intervals used for Strategy.

public:
    // getters for testing
    const std::vector<FeatureBar> &getBars() const { return bars_15s_; }
    size_t barCount() const { return bars_15s_.size(); }
};