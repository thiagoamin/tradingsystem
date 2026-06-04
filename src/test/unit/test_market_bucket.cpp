#include <gtest/gtest.h>
#include "market_data/MarketBucket.h"
#include <cmath>

static TradeTick makeTick(double price, int64_t size_us, int64_t ts_ns = 0)
{
    TradeTick t{};
    t.instrumentId = InstrumentId::SPY;
    t.price = price;
    t.size_us = size_us;
    t.exchangeTimestamp_ns = ts_ns;
    return t;
}

static QuoteSnapshot makeQuote(double bid, double ask, int64_t bidSize_us, int64_t askSize_us)
{
    QuoteSnapshot q{};
    q.instrumentId = InstrumentId::SPY;
    q.bid = bid;
    q.ask = ask;
    q.bidSize_us = bidSize_us;
    q.askSize_us = askSize_us;
    return q;
}

// ── isEmpty / isQuoteEmpty ────────────────────────────────────────────────────

TEST(MarketBucketTest, IsEmptyOnConstruction)
{
    MarketBucket b;
    EXPECT_TRUE(b.isEmpty());
    EXPECT_TRUE(b.isQuoteEmpty());
}

TEST(MarketBucketTest, NotEmptyAfterTick)
{
    MarketBucket b;
    b.addTick(makeTick(100.0, 1'000'000));
    EXPECT_FALSE(b.isEmpty());
}

TEST(MarketBucketTest, ClearResetsToEmpty)
{
    MarketBucket b;
    b.addTick(makeTick(100.0, 1'000'000));
    b.addQuote(makeQuote(99.0, 101.0, 1'000'000, 1'000'000));
    b.clear();
    EXPECT_TRUE(b.isEmpty());
    EXPECT_TRUE(b.isQuoteEmpty());
}

// ── OHLC ─────────────────────────────────────────────────────────────────────

TEST(MarketBucketTest, OhlcSingleTick)
{
    MarketBucket b;
    b.addTick(makeTick(150.0, 1'000'000, 1000));
    FeatureBar bar = b.build(InstrumentId::SPY, 0);
    EXPECT_DOUBLE_EQ(bar.open,  150.0);
    EXPECT_DOUBLE_EQ(bar.high,  150.0);
    EXPECT_DOUBLE_EQ(bar.low,   150.0);
    EXPECT_DOUBLE_EQ(bar.close, 150.0);
}

TEST(MarketBucketTest, OhlcMultipleTicks)
{
    MarketBucket b;
    b.addTick(makeTick(100.0, 1'000'000, 1000)); // open
    b.addTick(makeTick(200.0, 1'000'000, 2000)); // high
    b.addTick(makeTick( 50.0, 1'000'000, 3000)); // low
    b.addTick(makeTick(120.0, 1'000'000, 4000)); // close
    FeatureBar bar = b.build(InstrumentId::SPY, 0);
    EXPECT_DOUBLE_EQ(bar.open,   100.0);
    EXPECT_DOUBLE_EQ(bar.high,   200.0);
    EXPECT_DOUBLE_EQ(bar.low,     50.0);
    EXPECT_DOUBLE_EQ(bar.close,  120.0);
}

// ── Trade aggregates ──────────────────────────────────────────────────────────

TEST(MarketBucketTest, TradeCount)
{
    MarketBucket b;
    for (int i = 0; i < 5; ++i)
        b.addTick(makeTick(100.0, 1'000'000));
    EXPECT_EQ(b.build(InstrumentId::SPY, 0).tradeCount, 5);
}

TEST(MarketBucketTest, Vwap)
{
    // Trade 1: price=100, size=1 share → dollar=100
    // Trade 2: price=200, size=2 shares → dollar=400
    // VWAP = 500 / 3 ≈ 166.667 (in μshare units the ratio is the same)
    MarketBucket b;
    b.addTick(makeTick(100.0, 1'000'000));
    b.addTick(makeTick(200.0, 2'000'000));
    EXPECT_NEAR(b.build(InstrumentId::SPY, 0).vwap, 500.0 / 3.0, 1e-9);
}

TEST(MarketBucketTest, SviWithKnownMidpoint)
{
    // bid=150, ask=160 → midpoint=155
    // Tick at 160 (≥ mid): sign=+1, size=1M → signed=+1M
    // Tick at 140 (< mid): sign=-1, size=2M → signed=-2M
    // SVI = -1M / 3M = -1/3
    MarketBucket b;
    b.addQuote(makeQuote(150.0, 160.0, 100'000'000, 100'000'000));
    b.addTick(makeTick(160.0, 1'000'000));
    b.addTick(makeTick(140.0, 2'000'000));
    EXPECT_NEAR(b.build(InstrumentId::SPY, 0).svi, -1.0 / 3.0, 1e-9);
}

// ── Quote-derived microstructure ──────────────────────────────────────────────

TEST(MarketBucketTest, SpreadAndMidpoint)
{
    // bid=100, ask=110 → spread=10, mid=105
    MarketBucket b;
    b.addQuote(makeQuote(100.0, 110.0, 1'000'000, 1'000'000));
    b.addTick(makeTick(105.0, 1'000'000));
    FeatureBar bar = b.build(InstrumentId::SPY, 0);
    EXPECT_DOUBLE_EQ(bar.spreadClose,   10.0);
    EXPECT_DOUBLE_EQ(bar.midpointClose, 105.0);
    EXPECT_NEAR(bar.spreadBptsClose, 10000.0 * 10.0 / 105.0, 1e-9);
}

TEST(MarketBucketTest, QuoteImbalance)
{
    // bidSize=200, askSize=100 → (200-100)/(200+100) = 1/3
    MarketBucket b;
    b.addQuote(makeQuote(100.0, 110.0, 200'000'000, 100'000'000));
    b.addTick(makeTick(105.0, 1'000'000));
    EXPECT_NEAR(b.build(InstrumentId::SPY, 0).quoteImbalanceClose, 1.0 / 3.0, 1e-9);
}

TEST(MarketBucketTest, MicroPrice)
{
    // bid=100, ask=110, bidSize=200, askSize=100
    // μ = (110*200 + 100*100) / 300 = 32000/300 ≈ 106.667
    MarketBucket b;
    b.addQuote(makeQuote(100.0, 110.0, 200'000'000, 100'000'000));
    b.addTick(makeTick(105.0, 1'000'000));
    double expected = (110.0 * 200.0 + 100.0 * 100.0) / 300.0;
    EXPECT_NEAR(b.build(InstrumentId::SPY, 0).microPriceClose, expected, 1e-9);
}

// ── Statistics ────────────────────────────────────────────────────────────────

TEST(MarketBucketTest, PriceMeanAndStdev)
{
    // Prices: [100, 200] → mean=150, population stdev=50
    MarketBucket b;
    b.addTick(makeTick(100.0, 1'000'000));
    b.addTick(makeTick(200.0, 1'000'000));
    FeatureBar bar = b.build(InstrumentId::SPY, 0);
    EXPECT_NEAR(bar.priceMean,  150.0, 1e-9);
    EXPECT_NEAR(bar.priceStdev,  50.0, 1e-9);
}

TEST(MarketBucketTest, PriceQuartiles)
{
    // Prices added out of order: 40, 10, 30, 20 → sorted: [10, 20, 30, 40]
    // n=3: Q1=index 0 → 10, Q2=index 1 → 20, Q3=index 2 → 30
    MarketBucket b;
    b.addTick(makeTick(40.0, 1'000'000));
    b.addTick(makeTick(10.0, 1'000'000));
    b.addTick(makeTick(30.0, 1'000'000));
    b.addTick(makeTick(20.0, 1'000'000));
    FeatureBar bar = b.build(InstrumentId::SPY, 0);
    EXPECT_DOUBLE_EQ(bar.priceQ1, 10.0);
    EXPECT_DOUBLE_EQ(bar.priceQ2, 20.0);
    EXPECT_DOUBLE_EQ(bar.priceQ3, 30.0);
}

TEST(MarketBucketTest, BuildOnEmptyBucketIsZeroSafe)
{
    // build() on empty bucket must not crash or divide by zero
    MarketBucket b;
    FeatureBar bar = b.build(InstrumentId::SPY, 0);
    EXPECT_EQ(bar.tradeCount, 0);
    EXPECT_DOUBLE_EQ(bar.priceMean, 0.0);
    EXPECT_DOUBLE_EQ(bar.vwap,      0.0);
}
