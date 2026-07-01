#include "IbkrClient.h"

#include <iostream>
#include <spdlog/spdlog.h>

#include "OrionTradingContract.h"
#include "TagValue.h"
#include "utils/MarketConstants.h"
#include "utils/TimeUtils.h"

// 2s to wait for signal before timeout
IbkrClient::IbkrClient(
    rigtorp::SPSCQueue<TradeTick>     &tickBuffer,
    rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer)
  : tickBuffer_(tickBuffer),
    quoteBuffer_(quoteBuffer),
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
    spdlog::info("Waiting for IBKR session initialization...\n");

    // TODO: Connection retry
    // 1. Log attempt to connect
    spdlog::info(
        "Connecting to {}:{} clientId:{}", !(host && *host) ? "127.0.0.1" : host, port, clientId);

    // 2. Connection attempt
    bool ok = pClientSocket_->eConnect(host, port, clientId);

    if (ok)
    {
        spdlog::info(
            "Successfully connected to {}:{} clientId:{} serverVersion:{}",
            pClientSocket_->host().c_str(), pClientSocket_->port(), clientId,
            pClientSocket_->EClient::serverVersion());

        pReader_ =
            std::make_unique<EReader>(pClientSocket_.get(), &osSignal_); // Construct object now

        pReader_->start(); ///< Start Thread #1: parses socket
    }
    else
    {
        spdlog::warn(
            "Failed to connect to {}:{} clientId:{}", pClientSocket_->host().c_str(),
            pClientSocket_->port(), clientId);
    }

    return ok;
}

void IbkrClient::disconnect()
{
    if (isConnected())
    {
        pClientSocket_->eDisconnect();
        spdlog::info("Disconnect from IBKR");
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
            break;
        case ERROR:
            break;
    }

    processMessages();
}

void IbkrClient::connectAck()
{
    spdlog::info("Connect ACK");
    pClientSocket_->startApi();
};

// can't subscribe until we get nextValidId callback
void IbkrClient::nextValidId(OrderId orderId)
{
    orderId_ = orderId;
    spdlog::info("Next valid order id: {}", orderId);

    if (!subscribed_)
    {
        subscribe();
    }

    state_ = RUN;
};

void IbkrClient::error(
    int                id,
    time_t             errorTime,
    int                errorCode,
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

    if (isInformational(errorCode))
    {
        spdlog::info("IBKR notice | code:{} msg:{}", errorCode, errorString);
        return;
    }

    if (isConnectionError(errorCode))
    {
        handleConnectionError(errorCode, errorString);
        return;
    }

    if (isOrderError(errorCode))
    {
        handleOrderError(id, errorCode, errorString, advancedOrderRejectJson);
        return;
    }

    if (isMarketDataError(errorCode))
    {
        spdlog::warn("Market data issue | code:{} msg:{}", errorCode, errorString);
        return;
    }

    spdlog::warn("IBKR | id:{} code:{} msg:{}", id, errorCode, errorString);
}

// IBKR Tick Price Updates
void IbkrClient::tickPrice(
    TickerId          tickerId,
    TickType          field,
    double            price,
    const TickAttrib &attribs)
{
    // 1. Get instrument id
    // map tickerId to instrumentid
    auto it = reqIdToInstrumentId_.find(tickerId);
    if (it == reqIdToInstrumentId_.end())
    {
        spdlog::warn("Unknown ticker id: {}", tickerId);
        return;
    }

    auto &quote        = quote_cache_[static_cast<size_t>(it->second)];
    quote.instrumentId = it->second;

    // 2. Check if bid or ask
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
void IbkrClient::tickSize(TickerId tickerId, TickType field, Decimal size)
{
    // 1. Get instrument id
    auto it = reqIdToInstrumentId_.find(tickerId);
    if (it == reqIdToInstrumentId_.end())
    {
        spdlog::warn("Unknown ticker id: {}", tickerId);
        return;
    }

    int64_t newSize_us = convertDecimalToMicroShares(size);

    auto &quote        = quote_cache_[static_cast<size_t>(it->second)];
    quote.instrumentId = it->second;

    // 2. Check if bid or ask
    if (field == BID_SIZE || field == DELAYED_BID_SIZE)
    {
        quote.bidSize_us   = newSize_us;
        quote.timeStamp_ns = TimeUtils::steadyTime_ns();
    }
    else if (field == ASK_SIZE || field == DELAYED_ASK_SIZE)
    {
        quote.askSize_us   = newSize_us;
        quote.timeStamp_ns = TimeUtils::steadyTime_ns();
    }

    if (!quote.dirty)
    {
        quote.dirty = true;
        dirtyQuoteInstruments_.push_back(it->second);
    }
}

void IbkrClient::tickByTickAllLast(
    int                   reqId,
    int                   tickType,
    time_t                time,
    double                price,
    Decimal               size,
    const TickAttribLast &tickAttribLast,
    const std::string    &exchange,
    const std::string    &specialConditions)
{
    auto it = reqIdToInstrumentId_.find(reqId);
    if (it == reqIdToInstrumentId_.end())
    {
        spdlog::warn("Unknown ticker id: {}", reqId);
        return;
    }

    TradeTick event;

    event.instrumentId           = it->second;
    event.exchangeTimestamp_ns   = static_cast<int64_t>(time) * TimeUtils::kNanosecondsPerSecond;
    event.recvSteadyTimestamp_ns = TimeUtils::steadyTime_ns();
    event.recvWallTimestamp_ns   = TimeUtils::wallTime_ns();
    event.price                  = price;
    event.size_us                = convertDecimalToMicroShares(size);

    if (price <= 0 || event.size_us <= 0)
    {
        spdlog::warn(
            "tickByTickAllLast bad data | reqId:{} price:{} size_us:{}", reqId, price,
            event.size_us);
        return;
    }

#ifdef BENCH
    if (!tickBuffer_.try_push(event))
    {
        ++droppedTicks;
    }
    else
    {
        ++ticksPushed;
    }
#else
    tickBuffer_.push(event);
#endif
}

void IbkrClient::connectionClosed()
{
    // TODO: Do more here
    spdlog::warn("Connection closed");
    subscribed_ = false;
}

void IbkrClient::flushDirtyQuotes()
{
    // 3. Send quote to market data engine
    for (auto id : dirtyQuoteInstruments_)
    {
        auto &quote = quote_cache_[static_cast<size_t>(id)];

        if (quote.bid > 0 && quote.ask > 0 && quote.bidSize_us > 0 && quote.askSize_us > 0)
        {
#ifdef BENCH
            if (!quoteBuffer_.try_push(quote))
            {
                ++droppedQuotes;
                printf("DROP! droppedQuotes=%d\n", droppedQuotes.load());
            }
            else
            {
                ++quotesPushed;
            } // NEW
#else
            quoteBuffer_.push(quote);
#endif
            quote.updateSeq += 1;
        }
        quote.dirty = false;
    }
    dirtyQuoteInstruments_.clear();
}

// Core event loop
void IbkrClient::processMessages()
{
    // TODO: blocking logic, figure timing, threads, and etc. no hangups
    osSignal_.waitForSignal();
    if (!pReader_)
    {
        spdlog::warn("processMessages called but reader not initialized");
        return;
    }
    pReader_->processMsgs();

    // TODO Add timer to push quote
    // Ibkr processMessages should pair both bid and ask, price and size all in one message
    flushDirtyQuotes();
}

void IbkrClient::subscribe()
{
    spdlog::info("Setting market data type: 4 (delayed frozen)");
    pClientSocket_->reqMarketDataType(4);

    for (auto &config : OrionTradingContract::kInstruments)
    {
        reqQuoteData(config.quoteReqId, config.instrumentId, config.contract);
        reqTickByTickData(config.tradeReqId, config.instrumentId, config.contract);
    }

    subscribed_ = true;
    spdlog::info("Subscribed to market data for Project Orion instruments");
}

void IbkrClient::reqQuoteData(TickerId reqId, InstrumentId instrumentId, const Contract &contract)
{
    reqIdToInstrumentId_[reqId] = instrumentId;

    pClientSocket_->reqMktData(reqId, contract, "", false, false, TagValueListSPtr());
}

void IbkrClient::reqTickByTickData(
    TickerId        reqId,
    InstrumentId    instrumentId,
    const Contract &contract)
{
    reqIdToInstrumentId_[reqId] = instrumentId;

    pClientSocket_->reqTickByTickData(
        reqId, contract,
        "AllLast", // All trades tickType
        0, false);
}

// Converts IBKR Decimal → fixed-point shares (1 share = 10,000 units)
int64_t IbkrClient::convertDecimalToMicroShares(Decimal size)
{
    // Best course of action to avoid double for better memory and make our code modular
    // Won't be the bottle neck in latency
    return static_cast<int64_t>(
        DecimalFunctions::decimalToDouble(size) * MarketConstants::kMicrosharesPerShare);
}

bool IbkrClient::isInformational(int code)
{
    return code >= IbkrErrorCodes::INFO_MIN && code < IbkrErrorCodes::INFO_MAX;
}

bool IbkrClient::isConnectionError(int code)
{
    return code == IbkrErrorCodes::CONNECTION_LOST || code == IbkrErrorCodes::PORT_RESET ||
           code == IbkrErrorCodes::NOT_CONNECTED ||
           code == IbkrErrorCodes::CONNECTION_RESTORED_LOST ||
           code == IbkrErrorCodes::CONNECTION_RESTORED_OK;
}

bool IbkrClient::isOrderError(int code)
{
    return code == IbkrErrorCodes::ORDER_REJECTED || code == IbkrErrorCodes::ORDER_CANCELLED;
}

bool IbkrClient::isMarketDataError(int code)
{
    return code == IbkrErrorCodes::NOT_SUBSCRIBED || code == IbkrErrorCodes::PARTIAL_SUBSCRIPTION ||
           code == IbkrErrorCodes::DELAYED_NOT_ENABLED;
}

void IbkrClient::handleConnectionError(int errorCode, const std::string &errorString)
{
    // Connection lost, trigger reconnect
    if (errorCode == IbkrErrorCodes::CONNECTION_LOST || errorCode == IbkrErrorCodes::PORT_RESET ||
        errorCode == IbkrErrorCodes::NOT_CONNECTED)
    {
        spdlog::error("IBKR connection lost | code:{} msg:{}", errorCode, errorString);
        state_ = ERROR;
        return;
    }

    // Connection restored, resubscribe if data lost
    if (errorCode == IbkrErrorCodes::CONNECTION_RESTORED_LOST)
    {
        spdlog::warn("IBKR reconnected, data lost - resubscribing | code:{}", errorCode);
        subscribed_ = false;
        return;
    }

    if (errorCode == IbkrErrorCodes::CONNECTION_RESTORED_OK)
    {
        spdlog::info("IBKR reconnected, data maintained | code:{}", errorCode);
        return;
    }
}

void IbkrClient::handleOrderError(
    int                id,
    int                errorCode,
    const std::string &errorString,
    const std::string &advancedOrderRejectJson)
{
    // Order errors, important for order management
    if (errorCode == IbkrErrorCodes::ORDER_REJECTED)
    {
        if (!advancedOrderRejectJson.empty())
        {
            spdlog::error(
                "Order rejected | id:{} msg:{} reject:{}", id, errorString,
                advancedOrderRejectJson);
        }
        else
        {
            spdlog::error("Order rejected | id:{} msg:{}", id, errorString);
        }
        return;
    }

    if (errorCode == IbkrErrorCodes::ORDER_CANCELLED)
    {
        spdlog::warn("Order cancelled | id:{} msg:{}", id, errorString);
        return;
    }
}