#pragma once

/**
 * @file    IbkrClient.h
 * @author  Phi Lam (lamyenphi14@gmail.com)
 * @brief   Main interface for managing the connection and communication with Interactive Brokers.
 *
 * This module wraps the TWS/IB Gateway API, providing a state-driven client that
 * pushes market data updates to a MarketDataEngine instance. This helps bridge the layer between
 * IBKR and our trading system. Our trading system won't know IBKR specifics (data types, functions,
 * etc.).
 *
 * @version 0.1
 * @date    2026-05-26
 *
 * @copyright Copyright (c) 2026
 *
 */

#include <cstdio>
#include <cstring>
#include <ctime>
#include <memory>
#include <string>
#include <unordered_map>
#include "rigtorp/SPSCQueue.h"

#include "Contract.h"
#include "Decimal.h"
#include "DefaultEWrapper.h"
#include "EClientSocket.h"
#include "EReader.h"
#include "EReaderOSSignal.h"
#include "ibkr/IbkrErrorCodes.h"
#include "core/InstrumentId.h"
#include "events/QuoteSnapshot.h"
#include "events/TradeTick.h"
#include "market_data/MarketDataEngine.h"

/**
 *  @enum STATE
 *  @brief Represents the internal connection and running states of the client.
 */
enum STATE
{
    CONNECT,
    RUN,
    ERROR,
};

/**
 * @class IbkrClient
 * @brief EWrapper implementation that ingests IBKR market data callbacks and pushes to SPSCQueues.
 *
 */
class IbkrClient : public DefaultEWrapper
{
   public:
    /**
     * @brief Construct a new Ibkr Client object
     *
     * @param tickBuffer
     * @param quoteBuffer
     */
    IbkrClient(
        rigtorp::SPSCQueue<TradeTick>     &tickBuffer,
        rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer);

    /**
     * @brief Disconnects from IBKR.
     *
     */
    ~IbkrClient();

    /**
     * @brief Establishes connection to IBKR.
     *
     * @param host      Server IP where IBKR is running (e.g., "127.0.0.1" or "localhost").
     * @param port      Default network port (7497 - TWS, 4002 - IB Gateway)
     * @param clientId  A unique identifier for this client session.
     * @return true     If connection was successfully established.
     * @return false    If the connection failed (e.g., timeout, invalid host).
     */
    bool connect(const char *host, int port, int clientId);

    /**
     * @brief Disconnects connection from IBKR.
     *
     */
    void disconnect();

    /**
     * @brief Checks connection to IBKR.
     *
     * @return true  Connection is established.
     * @return false Connection is not established.
     */
    bool isConnected() const;

    /**
     * @brief Executes the client's main event loop and state machine tick.
     *
     */
    void run();

    /* -------------------------------------------------------------------------- */
    /*               IBKR Callbacks(Overridden from DefaultEWrapper)              */
    /* -------------------------------------------------------------------------- */

    /**
     * @brief Called when the initial connection handshake with TWS/Gateway succeeds.
     *
     */
    void connectAck() override;

    /**
     * @brief Receives the next available valid order ID upon a successful connection.
     *
     * @param orderId The next sequential ID to use when placing orders.
     */
    void nextValidId(OrderId orderId) override;

    /**
     * @brief Callback for handling system, connection, or order execution errors from IBKR.
     *
     * @param id                       The request ID associated with the error (-1 indicates a
     * system/connection notification).
     * @param errorTime                The timestamp when the error occurred.
     * @param errorCode                The specific IBKR error code mapping to the failure reason.
     * @param errorString              The descriptive error message text.
     * @param advancedOrderRejectJson  Structured JSON containing detailed rejection metadata for
     * advanced orders.
     */
    void error(
        int                id,
        time_t             errorTime,
        int                errorCode,
        const std::string &errorString,
        const std::string &advancedOrderRejectJson) override;
    /**
     * @brief Receives market data price updates (e.g., Bid, Ask, Last) for a subscription and
     * awaits tickSize for the full cached Quote Data (tickPrice and tickSize callback occur roughly
     * every 250ms according to IBKR).
     *
     * @param tickerId  The unique ID assigned to the data request.
     * @param field     The type of price field being updated (mapped via TickType enum).
     * @param price     The current price value.
     * @param attribs   Extra metadata flags regarding the price update (e.g., pre-open, past
     * limit).
     */
    void tickPrice(TickerId tickerId, TickType field, double price, const TickAttrib &attribs)
        override;

    /**
     * @brief Receives market data size updates (e.g., Bid Size, Ask Size) for a subscription
     * immediately after tickPrice callback (tickPrice and tickSize callback occur roughly every
     * 250ms according to IBKR).
     *
     * @param tickerId  The unique ID assigned to the data request.
     * @param field     The type of size field being updated (mapped via TickType enum).
     * @param size      The current size value wrapped in IBKR's Decimal type.
     */
    void tickSize(TickerId tickerId, TickType field, Decimal size) override;
    /**
     * @brief Receives real-time, tick-by-tick trade execution updates.
     *
     * @param reqId              The unique ID assigned to the data subscription request.
     * @param tickType           The specific tick type (e.g., 0 for Last, 1 for AllLast).
     * @param time               The UNIX timestamp of the trade execution.
     * @param price              The execution price of the trade.
     * @param size               The execution volume/size of the trade.
     * @param tickAttribLast     Regulatory and exchange-specific execution attributes.
     * @param exchange           The venue where the trade occurred.
     * @param specialConditions  Additional condition modifiers attached to the trade print.
     */
    void tickByTickAllLast(
        int                   reqId,
        int                   tickType,
        time_t                time,
        double                price,
        Decimal               size,
        const TickAttribLast &tickAttribLast,
        const std::string    &exchange,
        const std::string    &specialConditions) override;
    /**
     * @brief Called when the network socket connection to TWS/Gateway is dropped.
     *
     */
    void connectionClosed() override;

   private:
    EReaderOSSignal osSignal_; ///< Condition variable signaling when raw network packets arrive.
    std::unique_ptr<EClientSocket> pClientSocket_;
    ///< Unique ownership over the active IBKR socket connection.
    std::unique_ptr<EReader> pReader_;
    ///< Unique ownership over the asynchronous network packet reader.
    std::unordered_map<TickerId, InstrumentId> reqIdToInstrumentId_;
    ///< Maps IBKR request IDs to InstrumentId enum.
    std::unordered_map<InstrumentId, QuoteSnapshot> quote_cache_;
    ///< Local cache storing the latest L1 quotes per instrument.
    rigtorp::SPSCQueue<TradeTick>     &tickBuffer_;
    rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer_;
    STATE   state_;      ///< Current phase of the client's connection finite state machine.
    OrderId orderId_;    ///< The next valid, sequential order ID tracked for execution.
    bool    subscribed_; ///< Track if active market data subscriptions have been initialized.

    /* -------------------------------------------------------------------------- */
    /*                               Helper Functions                             */
    /* -------------------------------------------------------------------------- */

    /**
     * @brief Processes the local network socket event loop queue and dispatches payloads to
     * EWrapper callbacks.
     *
     */
    void processMessages();

    /**
     * @brief Executes the initial baseline data subscriptions across target instrument (stock)
     * registries. Identifier: (1000s for quote, 20000s for trade).
     */
    void subscribe();

    /**
     * @brief Subscribes to standard top-of-book streaming updates (Level 1 data).
     *
     * @param reqId         A newly generated, unique subscription tracking handle (1000s).
     * @param instrumentId  The destination internal tracking identifier based on InstrumentId enum.
     * @param contract      The physical asset criteria specifying target exchange and instrument
     * symbols.
     */
    void reqQuoteData(TickerId reqId, InstrumentId instrumentId, const Contract &contract);

    /**
     * @brief Subscribes to comprehensive granular tick-by-tick historical execution feeds.
     *
     * @param reqId         A newly generated, unique subscription tracking handle (20000s).
     * @param instrumentId  The destination internal tracking identifier based on InstrumentId enum.
     * @param contract      The physical asset criteria specifying target exchange and instrument
     * symbols.
     */
    void reqTickByTickData(TickerId reqId, InstrumentId instrumentId, const Contract &contract);

    /**
     * @brief Converts an IBKR API fixed-point Decimal size object down to regular micro-shares (1
     * share = 1,000,000 micro-shares).
     *
     * @param size  The incoming platform abstraction data container value.
     * @return      Integer representation scaled in millionths of a share (or basic volume count).
     */
    int64_t convertDecimalToMicroShares(Decimal size);

    /**
     * @brief Check if errorCode is informational
     *
     * @param code is the errorCode given by Ibkr error() callback
     * @return true If code is informational
     * @return false If code is not informational
     */
    bool isInformational(int code);

    /**
     * @brief Check if errorCode is a connection related
     *
     * @param code is the errorCode given by Ibkr error() callback
     * @return true If code is a connection error
     * @return false If code is not a connection error
     */
    bool isConnectionError(int code);

    /**
     * @brief Check if errorCode is an order related
     *
     * @param code is the errorCode given by Ibkr error() callback
     * @return true If code is an order error
     * @return false If code is not an order error
     */
    bool isOrderError(int code);

    /**
     * @brief Check if errorCode is market data related
     *
     * @param code is the errorCode given by Ibkr error() callback
     * @return true If code is a market data error
     * @return false If code is not a market data error
     */
    bool isMarketDataError(int code);

    /**
     * @brief
     *
     * @param errorCode
     * @param errorString
     */
    void handleConnectionError(int errorCode, const std::string &errorString);

    /**
     * @brief
     *
     * @param id
     * @param errorCode
     * @param errorString
     * @param advancedOrderRejectJson
     */
    void handleOrderError(
        int                id,
        int                errorCode,
        const std::string &errorString,
        const std::string &advancedOrderRejectJson);

   public:
    /* -------------------------------------------------------------------------- */
    /*                        Helper Functions for Testing                        */
    /* -------------------------------------------------------------------------- */

    void inline injectReqId(TickerId reqId, InstrumentId instrumentId)
    {
        reqIdToInstrumentId_[reqId] = instrumentId;
    }
};