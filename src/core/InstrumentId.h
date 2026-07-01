#pragma once
#include <cstdint>
#include <cstddef>

/**
 * @brief Unique internal identifiers for trading platform instruments.
 * @details Provides a strongly-typed mapping between internal system tokens
 * and liquid target assets, matching the order book registry.
 */
enum class InstrumentId : uint8_t
{
    SPY,   ///< SPDR S&P 500 ETF Trust.
    QQQ,   ///< Invesco QQQ Trust (NASDAQ-100).
    TSLA,  ///< Tesla, Inc. Common Stock.
    AAPL,  ///< Apple Inc. Common Stock.
    MSFT,  ///< Microsoft Corporation Common Stock.
    NVDA,  ///< NVIDIA Corporation Common Stock.
    GOOGL, ///< Alphabet Inc. Class A Common Stock.
    AMZN,  ///< Amazon.com, Inc. Common Stock.
    SIZE   ///< Sentinel — total count of instruments, not a real instrument.
};

constexpr size_t kNumInstruments = static_cast<size_t>(InstrumentId::SIZE);