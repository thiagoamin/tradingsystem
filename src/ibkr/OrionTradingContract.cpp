#include "OrionTradingContract.h"

Contract OrionTradingContract::makeUsEquity(const std::string& symbol)
{
    Contract c;
    c.symbol = symbol;
    c.secType = "STK";
    c.exchange = "SMART";  // Routes across major US exchanges
    c.currency = "USD";
    return c;
}

Contract OrionTradingContract::SPY() { return makeUsEquity("SPY"); }

Contract OrionTradingContract::QQQ() { return makeUsEquity("QQQ"); }

Contract OrionTradingContract::TSLA() { return makeUsEquity("TSLA"); }

Contract OrionTradingContract::AAPL() { return makeUsEquity("AAPL"); }

Contract OrionTradingContract::MSFT() { return makeUsEquity("MSFT"); }

Contract OrionTradingContract::NVDA() { return makeUsEquity("NVDA"); }

Contract OrionTradingContract::GOOGL() { return makeUsEquity("GOOGL"); }

Contract OrionTradingContract::AMZN() { return makeUsEquity("AMZN"); }