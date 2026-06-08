#pragma once
#include <cstdint>

/**
 * @brief Unique internal identifiers for trading platform instruments.
 * @details Provides a strongly-typed mapping between internal system tokens
 * and liquid target assets, matching the order book registry.
 */
enum class InstrumentId : int32_t
{
    SPY = 1,    ///< SPDR S&P 500 ETF Trust.
    QQQ = 2,    ///< Invesco QQQ Trust (NASDAQ-100).
    TSLA = 3,   ///< Tesla, Inc. Common Stock.
    AAPL = 4,   ///< Apple Inc. Common Stock.
    MSFT = 5,   ///< Microsoft Corporation Common Stock.
    NVDA = 6,   ///< NVIDIA Corporation Common Stock.
    GOOGL = 7,  ///< Alphabet Inc. Class A Common Stock.
    AMZN = 8    ///< Amazon.com, Inc. Common Stock.
};