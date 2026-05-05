#include "IbkrClient.h"
#include "utils/TimeUtils.h"
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

    MarketTickType tickType = mapTickType(field);
    if (tickType == MarketTickType::Unknown)
    {
        printf("UNKNOWN tick type");
        return;
    }

    TickEvent event;

    event.instrumentId = it->second;
    event.timeStamp_ns = now_ns();
    event.tickType = mapTickType(field);
    event.price = price;
    event.size = 0;

    // TODO: push to MarketDataEngine / queue

    // printf("Tick Price. Ticker Id: %ld, Field: %d, Price: %s, CanAutoExecute: %d, PastLimit: %d, PreOpen: %d\n",
    //        tickerId, (int)field, Utils::doubleMaxString(price).c_str(), attribs.canAutoExecute, attribs.pastLimit, attribs.preOpen);
}

// IBKR Tick Size Updates
void IbkrClient::tickSize(TickerId tickerId, TickType field,
                          Decimal size)
{
    // TODO: make cache to get size
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

    subscribeMarketData(1001, 1, OrionTradingContract::TSLA());
    subscribeMarketData(1002, 2, OrionTradingContract::AAPL());
    subscribeMarketData(1003, 3, OrionTradingContract::SPY());
    subscribeMarketData(1004, 4, OrionTradingContract::MSFT());
    subscribeMarketData(1005, 5, OrionTradingContract::NVDA());
    subscribeMarketData(1006, 6, OrionTradingContract::GOOGL());
    subscribeMarketData(1007, 7, OrionTradingContract::AMZN());

    // TODO print if sub is successful
}

void IbkrClient::subscribeMarketData(TickerId reqId,
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

MarketTickType IbkrClient::mapTickType(TickType field)
{
    switch (field)
    {
    case BID:
        return MarketTickType::Bid;
    case ASK:
        return MarketTickType::Ask;
    case LAST:
        return MarketTickType::Last;
    case DELAYED_BID:
        return MarketTickType::DelayedBid;
    case DELAYED_ASK:
        return MarketTickType::DelayedAsk;
    case DELAYED_LAST:
        return MarketTickType::DelayedLast;
    default:
        return MarketTickType::Unknown;
    }
}