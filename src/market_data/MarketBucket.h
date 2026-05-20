#pragma once
#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "events/FeatureBar.h"
#include "core/InstrumentId.h"
#include <vector>

class MarketBucket
{
public:
    MarketBucket();
    void add(const TradeTick &tick, const QuoteSnapshot &quote);
    FeatureBar build(InstrumentId id, int64_t bucketId) const;
    void clear();
    bool isEmpty();

private:
    int64_t startTimeStamp_ns;
    int64_t endTimeStamp_ns;

    int64_t tradeCount;
    double priceTotal;
    int64_t unsignedVolume_us;
    int64_t signedVolume_us;
    double dollarVolume_us;

    // Quote
    double latestBid;
    double latestAsk;
    int64_t latestBidSize_us; // 1 share = 1,000,000 micro shares
    int64_t latestAskSize_us;

    // OHLC
    double open;
    double high;
    double low;
    double close;

    // for stdev
    double priceMeanRunning = 0.0;
    double priceM2 = 0.0;

    double sizeMeanRunning_us = 0.0;
    double sizeM2_us = 0.0;

    // array
    std::vector<double> prices;
    std::vector<int64_t> sizes_us;

    bool hasValidQuote() const;
};