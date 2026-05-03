#pragma once

#include "DefaultEWrapper.h"
#include "EReaderOSSignal.h"
#include "EReader.h"
#include "EClientSocket.h"
#include "events/tick_event.h"

#include <cstring>
#include <cstdio>
#include <memory>
#include <string>
#include <ctime>

class IbkrClient : public DefaultEWrapper
{
public:
    IbkrClient();
    ~IbkrClient();

    bool connect(const char *host, int port, int clientId);
    void disconnect();
    bool isConnected() const;
    void processMessages();

    // IBKR callbacks
    void connectAck() override;
    void nextValidId(OrderId orderId) override;
    void error(int id, time_t errorTime, int errorCode,
               const std::string &errorString,
               const std::string &advancedOrderRejectJson) override;

    void tickPrice(TickerId tickerId, TickType field,
                   double price,
                   const TickAttrib &attribs) override;

private:
    EReaderOSSignal osSignal_;
    std::unique_ptr<EClientSocket> pClientSocket_;
    std::unique_ptr<EReader> pReader_;

    OrderId orderId_;

    MarketTickType mapTickType(TickType field);
};