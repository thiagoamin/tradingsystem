#pragma once

#include <cstdint>
#include <core/InstrumentId.h>

using TickerId = long;

// Trade tick even = external (market-driven) event
/**
 * @brief Transactional execution event capturing a discrete market trade print.
 *
 * @details Represents an external, market-driven transaction. Contains precise
 * local ingress profiling timestamps alongside exchange-reported clock times.
 */
struct TradeTick
{
    /* -------------------------------- Metadata -------------------------------- */
    InstrumentId instrumentId;
    int64_t exchangeTimestamp_ns; ///< IBKR time_t * 1e9, coarse

    ///< Latency profiling timstamps
    int64_t recvSteadyTimestamp_ns; ///< High-resolution local monotonic CPU clock tick upon socket ingress in ns.
    int64_t recvWallTimestamp_ns;   ///< Real-world system clock time (UNIX epoch ns) upon arrival

    /* ----------------------------- Transaction State --------------------------- */
    double price;
    int64_t size_us;

    // TODO: do I need other features
};