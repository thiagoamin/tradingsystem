#pragma once

#include "Contract.h"

#include <string>
class OrionTradingContract
{
public:
    /* -------------------------------------------------------------------------- */
    /*                           Core Market Index ETFs                           */
    /* -------------------------------------------------------------------------- */

    /**
     * @brief Generates an IBKR Contract for the SPDR S&P 500 ETF Trust (SPY).
     */
    static Contract SPY();

    /**
     * @brief Generates an IBKR Contract for the Invesco QQQ Trust (QQQ tracking NASDAQ-100).
     */
    static Contract QQQ();

    /* -------------------------------------------------------------------------- */
    /*                                 US Equities                                */
    /* -------------------------------------------------------------------------- */

    /**
     * @brief Generates an IBKR Contract for Tesla, Inc. (TSLA).
     */
    static Contract TSLA();

    /**
     * @brief Generates an IBKR Contract for Apple Inc. (AAPL).
     */
    static Contract AAPL();

    /**
     * @brief Generates an IBKR Contract for Microsoft Corporation (MSFT).
     */
    static Contract MSFT();

    /**
     * @brief Generates an IBKR Contract for NVIDIA Corporation (NVDA).
     */
    static Contract NVDA();

    /**
     * @brief Generates an IBKR Contract for Alphabet Inc. (GOOGL Class A).
     */
    static Contract GOOGL();

    /**
     * @brief Generates an IBKR Contract for Amazon.com, Inc. (AMZN).
     */
    static Contract AMZN();

private:
    /**
     * @brief Factory method to construct a standardized, SMART-routed US equity contract.
     *
     * @param symbol The ticker symbol of the asset (e.g., "AAPL").
     * @return       Fully configured IBKR Contract object pinned to USD and stock asset types.
     */
    static Contract makeUsEquity(const std::string &symbol);
};