#include "IbkrClient.h"
#include "utils/TimeUtils.h"
#include "utils/MarketConstants.h"
#include "OrionTradingContract.h"
#include "TagValue.h"

#include <iostream>

// 2s to wait for signal before timeout
IbkrClient::IbkrClient(MarketDataEngine &engine) : marketDataEngine_(engine),
                                                   osSignal_(2000),
                                                   pClientSocket_(std::make_unique<EClientSocket>(this, &osSignal_)),
                                                   state_(CONNECT),
                                                   orderId_(0),
                                                   subscribed_(false)
{
}

IbkrClient::~IbkrClient()
{
    disconnect();
}

bool IbkrClient::connect(const char *host, int port, int clientId)
{
    state_ = CONNECT;

    // TODO: Connection retry
    // 1. Log attempt to connect
    printf("Connecting to %s:%d clientId:%d\n", !(host && *host) ? "127.0.0.1" : host, port, clientId);

    // 2. Connection attempt
    bool ok = pClientSocket_->eConnect(host, port, clientId);

    if (ok)
    {
        printf("Successfully connected to %s:%d clientId:%d serverVersion: %d\n",
               pClientSocket_->host().c_str(), pClientSocket_->port(), clientId, pClientSocket_->EClient::serverVersion());

        pReader_ = std::make_unique<EReader>(pClientSocket_.get(), &osSignal_);
        pReader_->start();
    }
    else
        printf("Failed to connect to %s:%d clientId:%d\n",
               pClientSocket_->host().c_str(), pClientSocket_->port(), clientId);

    return ok;
}
void IbkrClient::disconnect()
{
    if (isConnected())
    {
        pClientSocket_->eDisconnect();
        std::cout << "Disconnected from IBKR\n";
    }
}
bool IbkrClient::isConnected() const
{
    return pClientSocket_ && pClientSocket_->isConnected();
}

// Main loop
void IbkrClient::run()
{
    // TODO: implement threads
    // TODO: implement better FSM
    switch (state_)
    {
    case CONNECT:
        printf("Waiting for IBKR session initialization...\n");
        break;
    case RUN:
        break;
    case ERROR:
        break;
    }

    processMessages();
}

void IbkrClient::connectAck()
{
    std::cout << "Connect ACK\n";
    pClientSocket_->startApi();
};

// can't subscribe until we get nextValidId callback
void IbkrClient::nextValidId(OrderId orderId)
{
    orderId_ = orderId;
    std::cout << "Next valid order id: " << orderId_ << "\n";

    if (!subscribed_)
    {
        subscribe();
        subscribed_ = true;
    }

    // TODO make no error occured to be in the RUN state
    state_ = RUN;
};
void IbkrClient::error(int id, time_t errorTime, int errorCode,
                       const std::string &errorString,
                       const std::string &advancedOrderRejectJson)
{
    char errorTimeStr[80];

    if (errorTime > 0)
    {
#if defined(IB_WIN32)
        ctime_s(errorTimeStr, sizeof(errorTimeStr), &(errorTime /= 1000));
#else
        ctime_r(&(errorTime /= 1000), errorTimeStr);
#endif
        errorTimeStr[strlen(errorTimeStr) - 1] = '\0';
    }
    else
    {
        errorTimeStr[0] = '\0';
    }

    if (!advancedOrderRejectJson.empty())
    {
        printf("Error. Id: %d, Time: %s, Code: %d, Msg: %s, AdvancedOrderRejectJson: %s\n",
               id, errorTimeStr, errorCode, errorString.c_str(),
               advancedOrderRejectJson.c_str());
    }
    else
    {
        printf("Error. Id: %d, Time: %s, Code: %d, Msg: %s\n",
               id, errorTimeStr, errorCode, errorString.c_str());
    }
}

// IBKR Tick Price Updates
void IbkrClient::tickPrice(TickerId tickerId, TickType field,
                           double price,
                           const TickAttrib &attribs)
{
    // map tickerId to instrumentid
    auto it = reqIdToInstrumentId_.find(tickerId);
    if (it == reqIdToInstrumentId_.end())
    {
        printf("UNKNOWN ticker id");
        return;
    }

    auto &quote = quote_cache_[it->second];
    quote.instrumentId = it->second;

    if (field == BID || field == DELAYED_BID)
    {
        quote.bid = price;
    }
    else if (field == ASK || field == DELAYED_ASK)
    {
        quote.ask = price;
    }
}

// IBKR Tick Size Updates
void IbkrClient::tickSize(TickerId tickerId, TickType field,
                          Decimal size)
{
    auto it = reqIdToInstrumentId_.find(tickerId);
    if (it == reqIdToInstrumentId_.end())
    {
        printf("UNKNOWN ticker id");
        return;
    }

    int64_t newSize_us = convertDecimalToMicroShares(size);

    auto &quote = quote_cache_[it->second];
    quote.instrumentId = it->second;

    if (field == BID_SIZE || field == DELAYED_BID_SIZE)
    {
        quote.bidSize_us = newSize_us;
        quote.timeStamp_ns = now_ns();

        // TODO: check if valid quote then push marketDataEngine otherwise log
    }
    else if (field == ASK_SIZE || field == DELAYED_ASK_SIZE)
    {

        quote.askSize_us = newSize_us;
        quote.timeStamp_ns = now_ns();

        // TODO: check if valid quote then push marketDataEngine otherwise log
    }
}

void IbkrClient::tickByTickAllLast(int reqId,
                                   int tickType,
                                   time_t time,
                                   double price,
                                   Decimal size,
                                   const TickAttribLast &tickAttribLast,
                                   const std::string &exchange,
                                   const std::string &specialConditions)
{
    auto it = reqIdToInstrumentId_.find(reqId);
    if (it == reqIdToInstrumentId_.end())
    {
        printf("UNKNOWN ticker id");
        return;
    }

    TradeTick event;

    event.instrumentId = it->second;
    event.timeStamp_ns = time;
    event.price = price;
    event.size = convertDecimalToMicroShares(size);

    marketDataEngine_.onTradeTick(event);
}

void IbkrClient::connectionClosed()
{
    std::cout << "Connection closed\n";

    subscribed_ = false;
}

// Core event loop
void IbkrClient::processMessages()
{
    osSignal_.waitForSignal();
    if (pReader_)
    {
        pReader_->processMsgs();
    }
}

void IbkrClient::subscribe()
{
    pClientSocket_->reqMarketDataType(4);

    reqQuoteData(1001, InstrumentId::SPY, OrionTradingContract::SPY());
    reqQuoteData(1002, InstrumentId::QQQ, OrionTradingContract::QQQ());
    reqQuoteData(1003, InstrumentId::TSLA, OrionTradingContract::TSLA());
    reqQuoteData(1004, InstrumentId::AAPL, OrionTradingContract::AAPL());
    reqQuoteData(1005, InstrumentId::MSFT, OrionTradingContract::MSFT());
    reqQuoteData(1006, InstrumentId::NVDA, OrionTradingContract::NVDA());
    reqQuoteData(1007, InstrumentId::GOOGL, OrionTradingContract::GOOGL());
    reqQuoteData(1008, InstrumentId::AMZN, OrionTradingContract::AMZN());

    reqTickByTickData(20001, InstrumentId::SPY, OrionTradingContract::SPY());
    reqTickByTickData(20002, InstrumentId::QQQ, OrionTradingContract::QQQ());
    reqTickByTickData(20003, InstrumentId::TSLA, OrionTradingContract::TSLA());
    reqTickByTickData(20004, InstrumentId::AAPL, OrionTradingContract::AAPL());
    reqTickByTickData(20005, InstrumentId::MSFT, OrionTradingContract::MSFT());
    reqTickByTickData(20006, InstrumentId::NVDA, OrionTradingContract::NVDA());
    reqTickByTickData(20007, InstrumentId::GOOGL, OrionTradingContract::GOOGL());
    reqTickByTickData(20008, InstrumentId::AMZN, OrionTradingContract::AMZN());

    std::cout << "Requested market data for Project Orion instruments\n";
}

void IbkrClient::reqQuoteData(TickerId reqId,
                              InstrumentId instrumentId,
                              const Contract &contract)
{
    reqIdToInstrumentId_[reqId] = instrumentId;

    pClientSocket_->reqMktData(
        reqId,
        contract,
        "",
        false,
        false,
        TagValueListSPtr());
}

void IbkrClient::reqTickByTickData(TickerId reqId,
                                   InstrumentId instrumentId,
                                   const Contract &contract)
{
    reqIdToInstrumentId_[reqId] = instrumentId;

    pClientSocket_->reqTickByTickData(
        reqId,
        contract,
        "AllLast", // All trades tickType
        0,
        false);
}

// Converts IBKR Decimal → fixed-point shares (1 share = 10,000 units)
int64_t IbkrClient::convertDecimalToMicroShares(Decimal size)
{
    // Best course of action to avoid double for better memory and make our code modular
    // Won't be the bottle neck in latency
    return static_cast<int64_t>(DecimalFunctions::decimalToDouble(size) * MarketConstants::kMicrosharesPerShare);
}