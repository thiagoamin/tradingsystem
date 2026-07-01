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
    { 1001, 20001, OrionTradingContract::SPY(), InstrumentId::SPY },
    { 1002, 20002, OrionTradingContract::QQQ(), InstrumentId::QQQ },
    { 1003, 20003, OrionTradingContract::TSLA(), InstrumentId::TSLA },
    { 1004, 20004, OrionTradingContract::AAPL(), InstrumentId::AAPL },
    { 1005, 20005, OrionTradingContract::MSFT(), InstrumentId::MSFT },
    { 1006, 20006, OrionTradingContract::NVDA(), InstrumentId::NVDA },
    { 1007, 20007, OrionTradingContract::GOOGL(), InstrumentId::GOOGL },
    { 1008, 20008, OrionTradingContract::AMZN(), InstrumentId::AMZN },
};