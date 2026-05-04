#include "OrionTradingContract.h"

Contract OrionTradingContract::makeStock(const std::string &symbol)
{
    Contract c;
    c.symbol = symbol; // "AAPL", "TSLA"
    c.secType = "STK";
    c.exchange = "SMART";
    c.currency = "USD";
    return c;
}

Contract OrionTradingContract::TSLA()
{
    return makeStock("TSLA");
}

Contract OrionTradingContract::AAPL()
{
    return makeStock("AAPL");
}

Contract OrionTradingContract::SPY()
{
    return makeStock("SPY");
}
Contract OrionTradingContract::MSFT()
{
    return makeStock("MSFT");
}

Contract OrionTradingContract::NVDA()
{
    return makeStock("NVDA");
}

Contract OrionTradingContract::GOOGL()
{
    return makeStock("GOOGL");
}

Contract OrionTradingContract::AMZN()
{
    return makeStock("AMZN");
}
