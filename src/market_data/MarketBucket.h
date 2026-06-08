#pragma once

/**
 * @file    MarketBucket.h
 * @author  Phi Lam (lamyenphi14@gmail.com)
 * @brief   Raw statistics accumulator for trade prints and quote frames.
 *
 * This module buffers discrete transactional ticks and cross-sectional quotes
 * over an active epoch window. It maintains running aggregates and raw vectors
 * to calculate robust microstructural statistics (e.g., VWAP, standard deviations,
 * and percentiles) when constructing a finalized FeatureBar.
 *
 * @version 0.1
 * @date    2026-05-27
 *
 * @copyright Copyright (c) 2026
 *
 */

#include <vector>

#include "core/InstrumentId.h"
#include "events/FeatureBar.h"
#include "events/QuoteSnapshot.h"
#include "events/TradeTick.h"

/**
 * @brief Statistical bucket tracking raw data slices.
 *
 * @details Accumulates streaming tick and quote parameters dynamically, exporting
 * a structured feature state profile on 15s interval boundary roll-overs.
 */
class MarketBucket
{
   public:
    /**
     * @brief Constructs an empty market data bucket and reserves sample storage.
     */
    MarketBucket();

    /**
     * @brief Aggregates an execution trade tick.
     *
     * @param tick   Inbound trade execution print.
     */
    void addTick(const TradeTick& tick);

    /**
     * @brief Aggregates the most recent top-of-book context.
     *
     * @param quote Most recent quote snapshot.
     */
    void addQuote(const QuoteSnapshot& quote);

    /**
     * @brief Processes accumulated data in market bucket to compile a finalized FeatureBar.
     *
     * @param id        Current instrument's ID.
     * @param bucketId  Bucket ID for the 15s window.
     * @return          Fully populated statistical 15s feature bar profile.
     */
    FeatureBar build(InstrumentId id, int64_t bucketId) const;

    /**
     * @brief Flushes accumulated metrics and resets scalars while preserving vector allocations.
     */
    void clear();

    /**
     * @brief Checks if the bucket contains 0 trade samples.
     *
     * @return true  If bucket contains any trade samples.
     * @return false If bucket has 0 trades.
     */
    bool isEmpty() const;

    /**
     * @brief After clear(), need to ensure tick data that uses latest Quote
     * adds to the total Quote.
     *
     * @return true  If quoteCount_ equal to 0.
     * @return false If quoteCount_ > 0.
     */
    bool isQuoteEmpty() const;

   private:
    /* -------------------------- Bucket Time Interval -------------------------- */
    int64_t startTimeStamp_ns_ = 0;
    int64_t endTimeStamp_ns_ = 0;

    /* ---------------------------- Trade Aggregates ---------------------------- */
    int64_t tradeCount_ = 0;
    double priceTotal_ = 0.0;
    int64_t unsignedVolume_us_ = 0;
    int64_t signedVolume_us_ = 0;
    double dollarVolume_us_ = 0.0;

    /* ---------------------------------- Quote --------------------------------- */
    int64_t quoteCount_ = 0;

    double latestBid_ = 0.0;
    double latestAsk_ = 0.0;
    int64_t latestBidSize_us_ = 0;  // 1 share = 1,000,000 micro shares
    int64_t latestAskSize_us_ = 0;

    double bidTotal_ = 0.0;
    double askTotal_ = 0.0;
    int64_t bidSizeTotal_us_ = 0;  // 1 share = 1,000,000 micro shares
    int64_t askSizeTotal_us_ = 0;

    /* ---------------------------------- OHLC ---------------------------------- */
    double open_ = 0.0;
    double high_ = 0.0;
    double low_ = 0.0;
    double close_ = 0.0;

    /* ----------------------- Running variance (Welford) ----------------------- */
    double priceMeanRunning_ = 0.0;
    double priceM2_ = 0.0;

    double sizeMeanRunning_us_ = 0.0;
    double sizeM2_us_ = 0.0;

    /* ------------------------------- Raw samples ------------------------------ */
    std::vector<double> prices_;
    std::vector<int64_t> sizes_us_;

    bool hasValidQuote() const;
};