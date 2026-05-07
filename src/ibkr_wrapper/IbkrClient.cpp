#include "IbkrClient.h"
#include "utils/TimeUtils.h"
#include "utils/MarketConstants.h"
#include "OrionTradingContract.h"
#include "TagValue.h"

#include <iostream>

// 2s to wait for signal before timeout
IbkrClient::IbkrClient() : osSignal_(2000),
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
        break;
    case RUN:
        processMessages();
        break;
    case ERROR:
        break;
    }
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

    // TODO: redo this when disconnect
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
    // map tickerId to reqId
    // TODO rename it
    auto it = reqId_to_instrument_.find(tickerId);
    if (it == reqId_to_instrument_.end())
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
    auto it = reqId_to_instrument_.find(tickerId);
    if (it == reqId_to_instrument_.end())
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
    auto it = reqId_to_instrument_.find(reqId);
    if (it == reqId_to_instrument_.end())
    {
        printf("UNKNOWN ticker id");
        return;
    }

    TradeTick event;

    event.instrumentId = it->second;
    event.timeStamp_ns = time;
    event.price = price;
    event.size = convertDecimalToMicroShares(size);

    // TODO: feed into my bar builder
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

    reqQuoteData(1001, 1, OrionTradingContract::SPY());
    reqQuoteData(1002, 2, OrionTradingContract::QQQ());
    reqQuoteData(1003, 3, OrionTradingContract::TSLA());
    reqQuoteData(1004, 4, OrionTradingContract::AAPL());
    reqQuoteData(1005, 5, OrionTradingContract::MSFT());
    reqQuoteData(1006, 6, OrionTradingContract::NVDA());
    reqQuoteData(1007, 7, OrionTradingContract::GOOGL());
    reqQuoteData(1008, 8, OrionTradingContract::AMZN());

    reqTickByTickData(20001, 1, OrionTradingContract::SPY());
    reqTickByTickData(20002, 2, OrionTradingContract::QQQ());
    reqTickByTickData(20003, 3, OrionTradingContract::TSLA());
    reqTickByTickData(20004, 4, OrionTradingContract::AAPL());
    reqTickByTickData(20005, 5, OrionTradingContract::MSFT());
    reqTickByTickData(20006, 6, OrionTradingContract::NVDA());
    reqTickByTickData(20007, 7, OrionTradingContract::GOOGL());
    reqTickByTickData(20008, 8, OrionTradingContract::AMZN());

    // TODO print if sub is successful
}

void IbkrClient::reqQuoteData(TickerId reqId,
                              int32_t instrumentId,
                              const Contract &contract)
{
    reqId_to_instrument_[reqId] = instrumentId;

    pClientSocket_->reqMktData(
        reqId,
        contract,
        "",
        false,
        false,
        TagValueListSPtr());
}

void IbkrClient::reqTickByTickData(TickerId reqId,
                                   int32_t instrumentId,
                                   const Contract &contract)
{
    reqId_to_instrument_[reqId] = instrumentId;

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