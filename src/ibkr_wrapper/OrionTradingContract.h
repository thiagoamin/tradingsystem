#pragma once

#include "Contract.h"

#include <string>
class OrionTradingContract
{
public:
    static Contract TSLA();  // Tesla
    static Contract AAPL();  // Apple
    static Contract SPY();   // S&P ETF
    static Contract MSFT();  // Microsoft
    static Contract NVDA();  // Nvidia
    static Contract GOOGL(); // Google
    static Contract AMZN();  // Amazon

private:
    static Contract makeStock(const std::string &symbol);
};