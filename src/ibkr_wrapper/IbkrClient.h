#pragma once

#include "DefaultEWrapper.h"
#include "EReaderOSSignal.h"
#include "EReader.h"
#include "EClientSocket.h"
#include "events/tradeTickEvent.h"
#include "events/quoteSnapshotEvent.h"
#include "Contract.h"
#include "Decimal.h"

#include <cstring>
#include <cstdio>
#include <memory>
#include <string>
#include <ctime>
#include <unordered_map>

enum STATE
{
    CONNECT,
    RUN,
    ERROR,
};

class IbkrClient : public DefaultEWrapper
{
public:
    IbkrClient();
    ~IbkrClient();

    // public functions
    bool connect(const char *host, int port, int clientId);
    void disconnect();
    bool isConnected() const;
    void run(); // run trading system

    // IBKR callbacks
    void connectAck() override;
    void nextValidId(OrderId orderId) override;
    void error(int id,
               time_t errorTime,
               int errorCode,
               const std::string &errorString,
               const std::string &advancedOrderRejectJson) override;
    void tickPrice(TickerId tickerId,
                   TickType field,
                   double price,
                   const TickAttrib &attribs) override;
    void tickSize(TickerId tickerId,
                  TickType field,
                  Decimal size) override;
    void tickByTickAllLast(int reqId,
                           int tickType,
                           time_t time,
                           double price,
                           Decimal size,
                           const TickAttribLast &tickAttribLast,
                           const std::string &exchange,
                           const std::string &specialConditions) override;

private:
    EReaderOSSignal osSignal_;
    std::unique_ptr<EClientSocket> pClientSocket_;
    std::unique_ptr<EReader> pReader_;

    std::unordered_map<TickerId, int32_t> reqId_to_instrument_; // TODO static?
    std::unordered_map<TickerId, QuoteSnapshot> quote_cache_;   // TODO static?
    STATE state_;
    bool subscribed_;
    OrderId orderId_;

    // private functions
    void processMessages();
    void subscribe();
    void reqQuoteData(TickerId reqId, int32_t instrumentId, const Contract &contract);
    void reqTickByTickData(TickerId reqId, int32_t instrumentId, const Contract &contract);
    int64_t convertDecimalToMicroShares(Decimal size);
};