#include "InstrumentMarketState.h"

InstrumentMarketState::InstrumentMarketState(InstrumentId id)
  : instrumentId_(id), lastSeenSeq_(0), latestQuote_{}, activeBucket_{}, flushBucket_{}
{
}

void InstrumentMarketState::onTick(const TradeTick &tick)
{
    // 3. Add quote to bucket quote variables if we get new quote or if new tick, but empty bucket
    // quote
    if (latestQuote_.updateSeq != lastSeenSeq_ || activeBucket_.isQuoteEmpty())
    {
        activeBucket_.addQuote(latestQuote_);
        lastSeenSeq_ = latestQuote_.updateSeq;
    }

    activeBucket_.addTick(tick);
    // TODO: log tick
}

void InstrumentMarketState::onQuote(const QuoteSnapshot &quote)
{
    latestQuote_ = quote;
    // TODO: log quote
}

void InstrumentMarketState::build(int64_t boundaryId)
{
    swapBuckets(); // O(1) — helps ring buffer not overflow while waiting to build

    // 1. Only build bars if we accumulated trades
    if (!flushBucket_.isEmpty())
    {
        FeatureBar currBar_15s = flushBucket_.build(instrumentId_, boundaryId);
        bars_15s_.push_back(currBar_15s);
    }

    // 2. Clean up state every 15s to clear cached data
    flushBucket_.clear();
}