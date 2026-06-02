#include <gtest/gtest.h>
#include "market_data/MarketDataEngine.h"

static constexpr int64_t kB0 = 0LL;
static constexpr int64_t kB1 = 15'000'000'000LL;
static constexpr int64_t kB2 = 30'000'000'000LL;

static TradeTick makeTick(InstrumentId id, int64_t ts_ns,
                          double price = 100.0, int64_t size_us = 1'000'000)
{
    TradeTick t{};
    t.instrumentId = id;
    t.exchangeTimestamp_ns = ts_ns;
    t.price = price;
    t.size_us = size_us;
    return t;
}

static QuoteSnapshot makeQuote(InstrumentId id, double bid, double ask)
{
    QuoteSnapshot q{};
    q.instrumentId = id;
    q.bid = bid;
    q.ask = ask;
    q.bidSize_us = 100'000'000;
    q.askSize_us = 100'000'000;
    return q;
}

// ── Routing & bar emission ────────────────────────────────────────────────────

TEST(PipelineTest, UnseenInstrumentReturnsNullptr)
{
    MarketDataEngine engine;
    EXPECT_EQ(engine.getState(InstrumentId::NVDA), nullptr);
}

TEST(PipelineTest, SingleInstrumentBarEmittedAfterBoundary)
{
    MarketDataEngine engine;
    engine.onTradeTick(makeTick(InstrumentId::SPY, kB0));
    engine.onTradeTick(makeTick(InstrumentId::SPY, kB1));
    const auto* state = engine.getState(InstrumentId::SPY);
    ASSERT_NE(state, nullptr);
    EXPECT_EQ(state->barCount(), 1u);
}

TEST(PipelineTest, TwoInstrumentsRoutedIndependently)
{
    // SPY crosses 2 boundaries → 2 bars; QQQ crosses 1 → 1 bar
    MarketDataEngine engine;
    engine.onTradeTick(makeTick(InstrumentId::SPY, kB0));
    engine.onTradeTick(makeTick(InstrumentId::QQQ, kB0));
    engine.onTradeTick(makeTick(InstrumentId::SPY, kB1)); // SPY bar 0 emitted
    engine.onTradeTick(makeTick(InstrumentId::QQQ, kB1)); // QQQ bar 0 emitted
    engine.onTradeTick(makeTick(InstrumentId::SPY, kB2)); // SPY bar 1 emitted

    const auto* spy = engine.getState(InstrumentId::SPY);
    const auto* qqq = engine.getState(InstrumentId::QQQ);
    ASSERT_NE(spy, nullptr);
    ASSERT_NE(qqq, nullptr);
    EXPECT_EQ(spy->barCount(), 2u);
    EXPECT_EQ(qqq->barCount(), 1u);
}

TEST(PipelineTest, QuoteRoutedToCorrectInstrument)
{
    MarketDataEngine engine;
    engine.onQuoteSample(makeQuote(InstrumentId::TSLA, 200.0, 202.0));
    engine.onTradeTick(makeTick(InstrumentId::TSLA, kB0, 201.0, 1'000'000));
    engine.onTradeTick(makeTick(InstrumentId::TSLA, kB1));
    const auto* state = engine.getState(InstrumentId::TSLA);
    ASSERT_NE(state, nullptr);
    ASSERT_EQ(state->barCount(), 1u);
    EXPECT_DOUBLE_EQ(state->getBars()[0].spreadClose, 2.0); // 202 - 200
}

TEST(PipelineTest, QuoteForOneInstrumentDoesNotPollutAnother)
{
    MarketDataEngine engine;
    engine.onQuoteSample(makeQuote(InstrumentId::SPY, 99.0, 101.0));
    engine.onTradeTick(makeTick(InstrumentId::QQQ, kB0));
    engine.onTradeTick(makeTick(InstrumentId::QQQ, kB1));
    const auto* qqq = engine.getState(InstrumentId::QQQ);
    ASSERT_NE(qqq, nullptr);
    ASSERT_EQ(qqq->barCount(), 1u);
    // QQQ bar should have no valid quote (spread stays 0)
    EXPECT_DOUBLE_EQ(qqq->getBars()[0].spreadClose, 0.0);
}
