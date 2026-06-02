#include <gtest/gtest.h>
#include "market_data/InstrumentMarketState.h"

static constexpr int64_t kB0 = 0LL;                  // bucket 0: [0, 15s)
static constexpr int64_t kB1 = 15'000'000'000LL;     // bucket 1: [15s, 30s)
static constexpr int64_t kB2 = 30'000'000'000LL;     // bucket 2: [30s, 45s)

static TradeTick makeTick(int64_t ts_ns, double price = 100.0, int64_t size_us = 1'000'000)
{
    TradeTick t{};
    t.instrumentId = InstrumentId::SPY;
    t.exchangeTimestamp_ns = ts_ns;
    t.price = price;
    t.size_us = size_us;
    return t;
}

static QuoteSnapshot makeQuote(double bid, double ask,
                               int64_t bidSz = 100'000'000, int64_t askSz = 100'000'000)
{
    QuoteSnapshot q{};
    q.instrumentId = InstrumentId::SPY;
    q.bid = bid;
    q.ask = ask;
    q.bidSize_us = bidSz;
    q.askSize_us = askSz;
    return q;
}

// ── Bar emission logic ────────────────────────────────────────────────────────

TEST(InstrumentMarketStateTest, NoBarWithinSameBucket)
{
    InstrumentMarketState s(InstrumentId::SPY);
    s.onTick(makeTick(kB0));
    s.onTick(makeTick(kB0 + 1'000'000'000LL));
    EXPECT_EQ(s.barCount(), 0u);
}

TEST(InstrumentMarketStateTest, OneBarOnFirstBoundary)
{
    InstrumentMarketState s(InstrumentId::SPY);
    s.onTick(makeTick(kB0)); // populates bucket 0
    s.onTick(makeTick(kB1)); // crosses boundary → emits bar for bucket 0
    EXPECT_EQ(s.barCount(), 1u);
}

TEST(InstrumentMarketStateTest, TwoBarsOnTwoBoundaries)
{
    InstrumentMarketState s(InstrumentId::SPY);
    s.onTick(makeTick(kB0));
    s.onTick(makeTick(kB1)); // emits bar 0
    s.onTick(makeTick(kB2)); // emits bar 1
    EXPECT_EQ(s.barCount(), 2u);
}

TEST(InstrumentMarketStateTest, EmptyBucketNotEmitted)
{
    // First tick lands in bucket 1 — bucket 0 was never populated, so no bar for it
    InstrumentMarketState s(InstrumentId::SPY);
    s.onTick(makeTick(kB1));
    s.onTick(makeTick(kB2)); // emits bar for bucket 1 only
    EXPECT_EQ(s.barCount(), 1u);
}

// ── Bar content ───────────────────────────────────────────────────────────────

TEST(InstrumentMarketStateTest, BarInstrumentIdIsCorrect)
{
    InstrumentMarketState s(InstrumentId::AAPL);
    TradeTick t = makeTick(kB0);
    t.instrumentId = InstrumentId::AAPL;
    s.onTick(t);
    TradeTick t2 = makeTick(kB1);
    t2.instrumentId = InstrumentId::AAPL;
    s.onTick(t2);
    ASSERT_EQ(s.barCount(), 1u);
    EXPECT_EQ(s.getBars()[0].instrumentId, InstrumentId::AAPL);
}

TEST(InstrumentMarketStateTest, QuoteBeforeTickAppearsInBar)
{
    // Quote arrives first, then a tick in bucket 0, then a tick in bucket 1 triggers emit
    InstrumentMarketState s(InstrumentId::SPY);
    s.onQuote(makeQuote(99.0, 101.0));
    s.onTick(makeTick(kB0, 100.0, 1'000'000));
    s.onTick(makeTick(kB1));
    ASSERT_EQ(s.barCount(), 1u);
    EXPECT_DOUBLE_EQ(s.getBars()[0].spreadClose,   2.0);   // 101 - 99
    EXPECT_DOUBLE_EQ(s.getBars()[0].midpointClose, 100.0); // (99+101)/2
}

TEST(InstrumentMarketStateTest, BarBucketIdMatchesWindow)
{
    InstrumentMarketState s(InstrumentId::SPY);
    s.onTick(makeTick(kB0));
    s.onTick(makeTick(kB1));
    ASSERT_EQ(s.barCount(), 1u);
    EXPECT_EQ(s.getBars()[0].barId, kB0 / 15'000'000'000LL); // bucket 0 → id 0
}
