#pragma once

#include "Contract.h"

#include <string>

class OrionTradingContract
{
public:
    static Contract TSLA(); // Tesla
    static Contract AAPL(); // Apple
    static Contract SPY();  // S&P ETF

private:
    static Contract makeStock(const std::string &symbol);
};