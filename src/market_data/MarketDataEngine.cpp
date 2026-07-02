#include <spdlog/spdlog.h>

#include "MarketDataEngine.h"

MarketDataEngine::MarketDataEngine()
  : instrumentStates_{ {
        InstrumentMarketState(InstrumentId::SPY),
        InstrumentMarketState(InstrumentId::QQQ),
        InstrumentMarketState(InstrumentId::TSLA),
        InstrumentMarketState(InstrumentId::AAPL),
        InstrumentMarketState(InstrumentId::MSFT),
        InstrumentMarketState(InstrumentId::NVDA),
        InstrumentMarketState(InstrumentId::GOOGL),
        InstrumentMarketState(InstrumentId::AMZN),
    } }
{
}

void MarketDataEngine::onTradeTick(const TradeTick &tick)
{
    size_t idx = static_cast<size_t>(tick.instrumentId);
    if (idx >= kNumInstruments) [[unlikely]]
    {
        spdlog::warn("Unknown instrumentId: {}", static_cast<int>(tick.instrumentId));
        return;
    }
    instrumentStates_[idx].onTick(tick);
}

void MarketDataEngine::onQuoteSample(const QuoteSnapshot &quote)
{
    size_t idx = static_cast<size_t>(quote.instrumentId);
    if (idx >= kNumInstruments) [[unlikely]]
    {
        spdlog::warn("Unknown instrumentId: {}", static_cast<int>(quote.instrumentId));
        return;
    }
    instrumentStates_[static_cast<size_t>(quote.instrumentId)].onQuote(quote);
}

void MarketDataEngine::flush(int64_t id)
{
    for (auto &state : instrumentStates_)
    {
        state.build(id);
    }
}

void MarketDataEngine::preFlush()
{
    for (auto &state : instrumentStates_)
    {
        state.swapBuckets();
    }
}