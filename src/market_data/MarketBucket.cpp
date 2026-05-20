#include "MarketBucket.h"
#include <algorithm>
#include <cmath>

MarketBucket::MarketBucket()
{
    prices.reserve(4096);
    sizes_us.reserve(4096);
}

void MarketBucket::add(const TradeTick &tick, const QuoteSnapshot &quote)
{
    // OHLC
    if (tradeCount == 0)
    {
        startTimeStamp_ns = tick.exchangeTimestamp_ns;
        open = tick.price;
        high = tick.price;
        low = tick.price;
    }

    close = tick.price;
    endTimeStamp_ns = tick.exchangeTimestamp_ns;

    high = (high > tick.price) ? high : tick.price;
    low = (low < tick.price) ? low : tick.price;

    // accumulation
    tradeCount++;
    priceTotal += tick.price;
    unsignedVolume_us += tick.size_us;
    dollarVolume_us += tick.price * tick.size_us;

    // quote
    latestBid = quote.bid;
    latestAsk = quote.ask;
    latestBidSize_us = quote.bidSize_us;
    latestAskSize_us = quote.askSize_us;

    double midpoint = (quote.bid + quote.ask) / 2.0;
    int sign = tick.price >= midpoint ? +1 : -1;

    signedVolume_us += sign * tick.size_us;

    // array
    prices.push_back(tick.price);
    sizes_us.push_back(tick.size_us);

    // Price Welford
    double priceDelta = tick.price - priceMeanRunning;
    priceMeanRunning += priceDelta / tradeCount;

    double priceDelta2 = tick.price - priceMeanRunning;
    priceM2 += priceDelta * priceDelta2;

    // Size Welford
    double size = static_cast<double>(tick.size_us);

    double sizeDelta = size - sizeMeanRunning_us;
    sizeMeanRunning_us += sizeDelta / tradeCount;

    double sizeDelta2 = size - sizeMeanRunning_us;
    sizeM2_us += sizeDelta * sizeDelta2;
}

FeatureBar MarketBucket::build(InstrumentId id, int64_t bucketId) const
{
    FeatureBar bar = {};
    bar.instrumentId = id;
    bar.barId = bucketId;
    bar.startTimeStamp_ns = startTimeStamp_ns;
    bar.endTimeStamp_ns = endTimeStamp_ns;
    bar.interval_ns = endTimeStamp_ns - startTimeStamp_ns;

    // trade derived
    bar.tradeCount = tradeCount;
    bar.unsignedVolume_us = unsignedVolume_us;
    bar.signedVolume_us = signedVolume_us;
    bar.dollarVolume_us = dollarVolume_us;

    // zero guards, tradecount is already guarded
    if (unsignedVolume_us != 0)
    {
        bar.vwap = dollarVolume_us / unsignedVolume_us;
        bar.svi = static_cast<double>(signedVolume_us) / unsignedVolume_us;
    }
    if (hasValidQuote())
    {
        // quote derived
        double midpointClose = (latestBid + latestAsk) / 2.0;
        bar.midpointClose = midpointClose;
        bar.spreadClose = latestAsk - latestBid;
        bar.spreadBpts = 10'000LL * (bar.spreadClose) / midpointClose;
        bar.quoteImbalance = static_cast<double>(latestBidSize_us - latestAskSize_us) / (latestBidSize_us + latestAskSize_us);
        bar.microPrice = (latestAsk * latestBidSize_us + latestBid * latestAskSize_us) / (latestAskSize_us + latestBidSize_us);
        if (bar.spreadClose != 0.0)
        {
            bar.microPriceDev = (bar.microPrice - bar.midpointClose) / (bar.spreadClose);
        }

        // trade derived
        bar.vwapGap = (bar.vwap - midpointClose) / midpointClose;
    }

    // OHLC
    bar.open = open;
    bar.close = close;
    bar.high = high;
    bar.low = low;

    bar.priceMean = priceTotal / tradeCount;
    bar.sizeMean_us = static_cast<double>(unsignedVolume_us) / tradeCount;

    bar.priceStdev =
        std::sqrt(priceM2 / tradeCount);

    bar.sizeStdev_us =
        std::sqrt(sizeM2_us / tradeCount);

    // TODO, do this better
    auto sortedPrices = prices;
    auto sortedSizes = sizes_us;

    std::sort(sortedPrices.begin(), sortedPrices.end());
    std::sort(sortedSizes.begin(), sortedSizes.end());

    size_t n_price = prices.size() - 1;

    // truncating size
    bar.priceQ1 = sortedPrices[static_cast<size_t>(n_price * 0.25)];
    bar.priceQ2 = sortedPrices[static_cast<size_t>(n_price * 0.50)];
    bar.priceQ3 = sortedPrices[static_cast<size_t>(n_price * 0.75)];

    size_t n_size = sortedSizes.size() - 1;

    bar.sizeQ1_us = sortedSizes[static_cast<size_t>(n_size * 0.25)];
    bar.sizeQ2_us = sortedSizes[static_cast<size_t>(n_size * 0.50)];
    bar.sizeQ3_us = sortedSizes[static_cast<size_t>(n_size * 0.75)];

    return bar;
}
void MarketBucket::clear()
{
    startTimeStamp_ns = 0;
    endTimeStamp_ns = 0;

    tradeCount = 0;
    priceTotal = 0.0;
    unsignedVolume_us = 0;
    signedVolume_us = 0;
    dollarVolume_us = 0.0;

    open = high = low = close = 0.0;

    priceMeanRunning = 0.0;
    priceM2 = 0.0;
    sizeMeanRunning_us = 0.0;
    sizeM2_us = 0.0;

    prices.clear();
    sizes_us.clear();
}
bool MarketBucket::isEmpty()
{
    return tradeCount == 0;
}

bool MarketBucket::hasValidQuote() const
{
    return latestBid > 0.0 &&
           latestAsk > 0.0 &&
           latestBidSize_us > 0 &&
           latestAskSize_us > 0;
}