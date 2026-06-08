#include "InstrumentMarketState.h"

#include "BarBuilder.h"

InstrumentMarketState::InstrumentMarketState(InstrumentId id)
    : instrumentId_(id), bucketId_15s_(-1), latestQuote_{}, hasNewQuote_(false), activeBucket_{}
{
}

void InstrumentMarketState::onTick(const TradeTick& tick)
{
    // !TODO: Update this later because feature bar will not push if new tick right after 15s comes
    int64_t currId = tick.exchangeTimestamp_ns / kFifteenSec_ns;

    if (bucketId_15s_ == -1)
    {
        bucketId_15s_ = currId;
    }

    if (currId != bucketId_15s_)
    {
        // 1. Only build bars if we accumulated trades
        if (!activeBucket_.isEmpty())
        {
            FeatureBar currBar_15s = activeBucket_.build(instrumentId_, bucketId_15s_);
            bars_15s_.push_back(currBar_15s);
        }

        // 2. Clean up state every 15s to clear cached quote data
        activeBucket_.clear();
        bucketId_15s_ = currId;
    }

    // 3. Add quote to bucket quote variables if we get new quote or if new tick, but empty bucket
    // quote
    if (hasNewQuote_ || activeBucket_.isQuoteEmpty())
    {
        activeBucket_.addQuote(latestQuote_);
        hasNewQuote_ = false;
    }

    activeBucket_.addTick(tick);
    // TODO: log tick
}

void InstrumentMarketState::onQuote(const QuoteSnapshot& quote)
{
    latestQuote_ = quote;
    hasNewQuote_ = true;
    // TODO: log quote
}