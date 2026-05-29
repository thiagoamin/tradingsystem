#pragma once

#include <cstdint>
#include <core/InstrumentId.h>

/**
 * @brief Aggregated feature list containing microstructure indicators and pricing statistics needed for Strategy.
 *
 * @details Compiles transactional trade flows, limit order book imbalances, and raw order sizes
 * into a single unified mathematical footprint for alpha generation and model ingestion.
 */
struct FeatureBar
{
    /* -------------------------------- Metadata -------------------------------- */
    InstrumentId instrumentId;
    int64_t barId;

    int64_t startTimeStamp_ns; ///< UNIX epoch nanoseconds
    int64_t endTimeStamp_ns;   ///< UNIX epoch nanoseconds
    int64_t interval_ns;

    /* ----------------------------- Quote Features ----------------------------- */
    double bidClose;            // b_a,t
    double askClose;            // a_a,t
    int64_t bidsizeClose_us;    // B_a,t
    int64_t assizeClose_us;     // A_a,t
    double midpointClose;       // m_a,t
    double spreadClose;         // s_a,t
    double spreadBptsClose;     // s^bps_a,t
    double quoteImbalanceClose; // Imb_a,t
    double microPriceClose;     // μ_a,t
    double microPriceDevClose;  // MP_a,t

    // Extra
    double bidAvg;
    double askAvg;
    double midpointAvg;       // m_a,t
    double spreadAvg;         // s_a,t
    double spreadBptsAvg;     // s^bps_a,t
    double quoteImbalanceAvg; // Imb_a,t
    double microPriceAvg;     // μ_a,t
    double microPriceDevAvg;  // MP_a,t

    /* ------------------------------ Trade Derived ----------------------------- */
    int32_t tradeCount;        // N^T_a,t,h
    int64_t unsignedVolume_us; // V^T_a,t,h
    int64_t signedVolume_us;   // V^T_a,t,h * ϵ_a,k
    double dollarVolume_us;    // DV^T_a,t,h

    double vwap; ///< volume weighted average price
    double svi;  ///< signed volume imbalance
    double vwapGap;

    /* ------------------------------- OHLC/debug ------------------------------- */
    double open;
    double high;
    double low;
    double close;

    /* ---------------------------- Extra price stats --------------------------- */
    double priceMean;
    double priceStdev;

    double priceQ1;
    double priceQ2;
    double priceQ3;

    /* ---------------------------- Extra size stats ---------------------------- */
    double sizeMean_us;
    double sizeStdev_us;

    double sizeQ1_us;
    double sizeQ2_us;
    double sizeQ3_us;
};