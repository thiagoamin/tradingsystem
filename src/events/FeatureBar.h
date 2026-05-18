#pragma once

#include <cstdint>
#include <core/InstrumentId.h>

struct FeatureBar
{
    /* --- Metadata --- */
    InstrumentId instrumentId;

    int64_t startTimeStamp_ns;
    int64_t endTimeStamp_ns;
    int64_t interval_ns;

    /* --- Basic OHLC --- */
    double open;
    double high; // q4
    double low;
    double close;

    int64_t volume;
    int32_t trade_count;

    /* --- Statistical Features --- */
    double price_change; // close - open

    // Price Distribution
    double price_mean;  // Average price
    double price_stdev; // Price standard deviation during the 15s

    // Size/Volume Distribution
    double size_mean;  // Average trade size
    double size_stdev; // Size standard deviation

    // Distribution Quantiles
    double price_q1; // 25th percentile of price
    double price_q2; // 50th percentile (Median)
    double price_q3; // 75th percentile
};