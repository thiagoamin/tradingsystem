#include "MarketBucket.h"

#include <algorithm>
#include <cmath>

MarketBucket::MarketBucket()
{
    prices_.reserve(4096);
    sizes_us_.reserve(4096);
}

void MarketBucket::addTick(const TradeTick &tick)
{
    // OHLC
    if (tradeCount_ == 0)
    {
        startTimeStamp_ns_ = tick.exchangeTimestamp_ns;
        open_              = tick.price;
        high_              = tick.price;
        low_               = tick.price;
    }

    close_           = tick.price;
    endTimeStamp_ns_ = tick.exchangeTimestamp_ns;

    high_ = (high_ > tick.price) ? high_ : tick.price;
    low_  = (low_ < tick.price) ? low_ : tick.price;

    // accumulation
    tradeCount_++;
    priceTotal_ += tick.price;
    unsignedVolume_us_ += tick.size_us;
    dollarVolume_us_ += tick.price * tick.size_us;

    // Only add to signed volume if there is a valid quote
    if (hasValidQuote())
    {
        double midpoint = (latestBid_ + latestAsk_) / 2.0;
        int    sign     = tick.price >= midpoint ? +1 : -1;

        signedVolume_us_ += sign * tick.size_us;
    }

    // array
    prices_.push_back(tick.price);
    sizes_us_.push_back(tick.size_us);

    // Price Welford
    double priceDelta = tick.price - priceMeanRunning_;
    priceMeanRunning_ += priceDelta / tradeCount_;

    double priceDelta2 = tick.price - priceMeanRunning_;
    priceM2_ += priceDelta * priceDelta2;

    // Size Welford
    double size = static_cast<double>(tick.size_us);

    double sizeDelta = size - sizeMeanRunning_us_;
    sizeMeanRunning_us_ += sizeDelta / tradeCount_;

    double sizeDelta2 = size - sizeMeanRunning_us_;
    sizeM2_us_ += sizeDelta * sizeDelta2;
}

void MarketBucket::addQuote(const QuoteSnapshot &quote)
{
    // quote
    quoteCount_++;

    latestBid_        = quote.bid;
    latestAsk_        = quote.ask;
    latestBidSize_us_ = quote.bidSize_us;
    latestAskSize_us_ = quote.askSize_us;

    bidTotal_ += latestBid_;
    askTotal_ += latestAsk_;
    bidSizeTotal_us_ += quote.bidSize_us;
    askSizeTotal_us_ += quote.askSize_us;
}

FeatureBar MarketBucket::build(InstrumentId id, int64_t bucketId) const
{
    FeatureBar bar = {};

    bar.instrumentId      = id;
    bar.barId             = bucketId;
    bar.startTimeStamp_ns = startTimeStamp_ns_;
    bar.endTimeStamp_ns   = endTimeStamp_ns_;
    bar.interval_ns       = endTimeStamp_ns_ - startTimeStamp_ns_;

    // OHLC
    bar.open  = open_;
    bar.close = close_;
    bar.high  = high_;
    bar.low   = low_;

    // trade derived
    bar.tradeCount        = tradeCount_;
    bar.unsignedVolume_us = unsignedVolume_us_;
    bar.signedVolume_us   = signedVolume_us_;
    bar.dollarVolume_us   = dollarVolume_us_;

    // zero guards
    if (unsignedVolume_us_ != 0)
    {
        bar.vwap = dollarVolume_us_ / unsignedVolume_us_;
        bar.svi  = static_cast<double>(signedVolume_us_) / unsignedVolume_us_;
    }

    // Shouldn't happen but prevent dividsion by zero.
    if (tradeCount_ > 0)
    {
        bar.priceMean   = priceTotal_ / tradeCount_;
        bar.sizeMean_us = static_cast<double>(unsignedVolume_us_) / tradeCount_;

        bar.priceStdev = std::sqrt(priceM2_ / tradeCount_);

        bar.sizeStdev_us = std::sqrt(sizeM2_us_ / tradeCount_);

        // TODO, do this better
        auto sortedPrices = prices_;
        auto sortedSizes  = sizes_us_;

        /*  Candidate fix: replace with a streaming/approximate quantile estimator (P² algorithm)
  for O(1) per-tick update instead of O(n log n) at flush time. Not yet implemented. */
        std::sort(sortedPrices.begin(), sortedPrices.end());
        std::sort(sortedSizes.begin(), sortedSizes.end());

        size_t n_price = prices_.size() - 1;

        // truncating size
        bar.priceQ1 = sortedPrices[static_cast<size_t>(n_price * 0.25)];
        bar.priceQ2 = sortedPrices[static_cast<size_t>(n_price * 0.50)];
        bar.priceQ3 = sortedPrices[static_cast<size_t>(n_price * 0.75)];

        size_t n_size = sortedSizes.size() - 1;

        bar.sizeQ1_us = sortedSizes[static_cast<size_t>(n_size * 0.25)];
        bar.sizeQ2_us = sortedSizes[static_cast<size_t>(n_size * 0.50)];
        bar.sizeQ3_us = sortedSizes[static_cast<size_t>(n_size * 0.75)];
    }

    if (hasValidQuote())
    {
        // quote derived
        double bidAvg     = bidTotal_ / quoteCount_;
        double askAvg     = askTotal_ / quoteCount_;
        double bidSizeAvg = static_cast<double>(bidSizeTotal_us_) / quoteCount_;
        double askSizeAvg = static_cast<double>(askSizeTotal_us_) / quoteCount_;

        double midpointClose = (latestBid_ + latestAsk_) / 2.0;
        double midpointAvg   = (bidAvg + askAvg) / 2.0;
        double spreadClose   = latestAsk_ - latestBid_;
        double spreadAvg     = askAvg - bidAvg;

        bar.bidAvg = bidAvg;
        bar.askAvg = askAvg;

        bar.bidClose        = latestBid_;
        bar.askClose        = latestAsk_;
        bar.bidSizeClose_us = latestBidSize_us_;
        bar.askSizeClose_us = latestAskSize_us_;

        bar.midpointClose = midpointClose;
        bar.midpointAvg   = midpointAvg;
        bar.spreadClose   = spreadClose;
        bar.spreadAvg     = spreadAvg;

        bar.spreadBptsClose = 10'000LL * (spreadClose) / midpointClose;
        bar.spreadBptsAvg   = 10'000LL * (spreadAvg) / midpointAvg;

        bar.quoteImbalanceClose = static_cast<double>(latestBidSize_us_ - latestAskSize_us_) /
                                  (latestBidSize_us_ + latestAskSize_us_);
        bar.quoteImbalanceAvg   = (bidSizeAvg - askSizeAvg) / (bidSizeAvg + askSizeAvg);

        bar.microPriceClose = (latestAsk_ * latestBidSize_us_ + latestBid_ * latestAskSize_us_) /
                              (latestAskSize_us_ + latestBidSize_us_);
        bar.microPriceAvg = (askAvg * bidSizeAvg + bidAvg * askSizeAvg) / (askSizeAvg + bidSizeAvg);

        if (spreadClose != 0.0)
        {
            bar.microPriceDevClose = (bar.microPriceClose - midpointClose) / (spreadClose);
        }
        if (spreadAvg != 0.0)
        {
            bar.microPriceDevAvg = (bar.microPriceAvg - midpointAvg) / (spreadAvg);
        }

        // trade derived
        if (midpointClose != 0.0)
        {
            bar.vwapGap = (bar.vwap - midpointClose) / midpointClose;
        }
    }

    return bar;
}

void MarketBucket::clear()
{
    startTimeStamp_ns_ = 0;
    endTimeStamp_ns_   = 0;

    tradeCount_        = 0;
    priceTotal_        = 0.0;
    unsignedVolume_us_ = 0;
    signedVolume_us_   = 0;
    dollarVolume_us_   = 0.0;

    quoteCount_      = 0;
    bidTotal_        = 0.0;
    askTotal_        = 0.0;
    bidSizeTotal_us_ = 0;
    askSizeTotal_us_ = 0;

    open_ = high_ = low_ = close_ = 0.0;

    priceMeanRunning_   = 0.0;
    priceM2_            = 0.0;
    sizeMeanRunning_us_ = 0.0;
    sizeM2_us_          = 0.0;

    prices_.clear();
    sizes_us_.clear();
}

bool MarketBucket::isEmpty() const
{
    return tradeCount_ == 0;
}

bool MarketBucket::hasValidQuote() const
{
    return latestBid_ > 0.0 && latestAsk_ > 0.0 && latestBidSize_us_ > 0 && latestAskSize_us_ > 0;
}

bool MarketBucket::isQuoteEmpty() const
{
    return quoteCount_ == 0;
}