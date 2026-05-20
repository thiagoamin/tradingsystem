#pragma once
#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "events/FeatureBar.h"
#include "market_data/MarketBucket.h"
#include "core/InstrumentId.h"

#include <vector>

class InstrumentMarketState
{
public:
    static constexpr int64_t FifteenSec_ns = 15'000'000LL;

    explicit InstrumentMarketState(InstrumentId id);

    void onTick(const TradeTick &tick);
    void onQuote(const QuoteSnapshot &quote);

private:
    InstrumentId instrumentId_;

    QuoteSnapshot latestQuote_;

    MarketBucket activeBucket_;
    int64_t bucketId_15s_;
    FeatureBar currBar_15s_;
    std::vector<FeatureBar> bars_15s_;
};