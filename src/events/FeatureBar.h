#pragma once

#include <cstdint>
#include <core/InstrumentId.h>

struct FeatureBar
{
    /* --- Metadata --- */
    InstrumentId instrumentId;
    int64_t barId;

    int64_t startTimeStamp_ns;
    int64_t endTimeStamp_ns;
    int64_t interval_ns;

    /* --- Quote Features --- */
    double midpointClose;
    double spreadClose;
    double spreadBpts;
    double quoteImbalance;
    double microPrice;
    double microPriceDev;

    /* --- Trade Derived --- */
    int32_t tradeCount;
    int64_t unsignedVolume_us;
    int64_t signedVolume_us;
    double dollarVolume_us;

    double vwap;
    double svi; // signed volume imbalance
    double vwapGap;

    /* --- OHLC/debug --- */
    double open;
    double high;
    double low;
    double close;

    // ---------- Optional price stats ----------
    double priceMean;
    double priceStdev;

    double priceQ1;
    double priceQ2;
    double priceQ3;

    // ---------- Optional size stats ----------
    double sizeMean_us;
    double sizeStdev_us;

    double sizeQ1_us;
    double sizeQ2_us;
    double sizeQ3_us;
};