#include "OrionTradingContract.h"

Contract OrionTradingContract::makeUsEquity(const std::string &symbol)
{
    Contract c;
    c.symbol   = symbol;
    c.secType  = "STK";
    c.exchange = "SMART"; // Routes across major US exchanges
    c.currency = "USD";
    return c;
}

Contract OrionTradingContract::SPY()
{
    return makeUsEquity("SPY");
}

Contract OrionTradingContract::QQQ()
{
    return makeUsEquity("QQQ");
}

Contract OrionTradingContract::TSLA()
{
    return makeUsEquity("TSLA");
}

Contract OrionTradingContract::AAPL()
{
    return makeUsEquity("AAPL");
}

Contract OrionTradingContract::MSFT()
{
    return makeUsEquity("MSFT");
}

Contract OrionTradingContract::NVDA()
{
    return makeUsEquity("NVDA");
}

Contract OrionTradingContract::GOOGL()
{
    return makeUsEquity("GOOGL");
}

Contract OrionTradingContract::AMZN()
{
    return makeUsEquity("AMZN");
}

const std::vector<InstrumentConfig> OrionTradingContract::kInstruments = {
    { 1001, 20001, InstrumentId::SPY, OrionTradingContract::SPY() },
    { 1002, 20002, InstrumentId::QQQ, OrionTradingContract::QQQ() },
    { 1003, 20003, InstrumentId::TSLA, OrionTradingContract::TSLA() },
    { 1004, 20004, InstrumentId::AAPL, OrionTradingContract::AAPL() },
    { 1005, 20005, InstrumentId::MSFT, OrionTradingContract::MSFT() },
    { 1006, 20006, InstrumentId::NVDA, OrionTradingContract::NVDA() },
    { 1007, 20007, InstrumentId::GOOGL, OrionTradingContract::GOOGL() },
    { 1008, 20008, InstrumentId::AMZN, OrionTradingContract::AMZN() },
};