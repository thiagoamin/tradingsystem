#include "MarketDataEngine.h"

void MarketDataEngine::onTradeTick(const TradeTick &tick)
{
    // Try to emplace. If tick.instrumentId isn't found, it constructs an
    // InstrumentMarketState passing tick.instrumentId as the constructor argument to make
    // InstrumentMarketState(tick.instrumentId)
    auto [it, _] = instrumentStates_.try_emplace(tick.instrumentId, tick.instrumentId);
    it->second.onTick(tick);
};

void MarketDataEngine::onQuoteSample(const QuoteSnapshot &quote)
{
    auto [it, _] = instrumentStates_.try_emplace(quote.instrumentId, quote.instrumentId);
    it->second.onQuote(quote);
}

void MarketDataEngine::flush(int64_t id)
{
    for (auto &[_, state] : instrumentStates_)
    {
        state.build(id);
    }
}