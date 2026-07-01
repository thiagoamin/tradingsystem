#pragma once

#include <cstdint>

#include "core/InstrumentId.h"

/**
 * @brief Discrete time-driven snapshot tracking top-of-book market depth state.
 *
 * @details Captures the final synchronized limit order book state before the
 * conclusion of each continuous ~250ms observation interval.
 */
struct QuoteSnapshot
{
    /* -------------------------------- Metadata -------------------------------- */
    int64_t timeStamp_ns; // absolute time in nanoseconds

    /* ---------------------------- Top of Book State --------------------------- */
    double  bid;
    double  ask;
    int64_t bidSize_us; // 1 share = 1,000,000 μ shares
    int64_t askSize_us; // 1 share = 1,000,000 μ shares

    InstrumentId instrumentId;

    /* ---------------------- Push Quote Data Dependencies ---------------------- */
    bool     dirty     = false;
    uint32_t updateSeq = 0;

    // TODO: features needed later?
    // bidConditions
    // askConditions
    // bidExchanges
    // askExchanges
};