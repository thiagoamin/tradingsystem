#include "IbkrClient.h"

#include <iostream>

// 2s to wait for signal before timeout
IbkrClient::IbkrClient() : osSignal_(2000), pClientSocket_(std::make_unique<EClientSocket>(this, &osSignal_)), orderId_(0)
{
}

IbkrClient::~IbkrClient()
{
    disconnect();
}

bool IbkrClient::connect(const char *host, int port, int clientId)
{
    // 1. Log attempt to connect
    printf("Connecting to %s:%d clientId:%d\n", !(host && *host) ? "127.0.0.1" : host, port, clientId);

    // 2. Connection attempt
    bool ok = pClientSocket_->eConnect(host, port, clientId);

    if (ok)
    {
        printf("Successfully connected to %s:%d clientId:%d serverVersion: %d\n", pClientSocket_->host().c_str(), pClientSocket_->port(), clientId, pClientSocket_->EClient::serverVersion());

        pReader_ = std::make_unique<EReader>(pClientSocket_.get(), &osSignal_);
        pReader_->start();
    }
    else
        printf("Failed to connect to %s:%d clientId:%d\n", pClientSocket_->host().c_str(), pClientSocket_->port(), clientId);

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
void IbkrClient::processMessages()
{
    osSignal_.waitForSignal();
    if (pReader_)
    {
        pReader_->processMsgs();
    }
}

void IbkrClient::connectAck()
{
    std::cout << "Connect ACK\n";
    pClientSocket_->startApi();
};
void IbkrClient::nextValidId(OrderId orderId)
{
    orderId_ = orderId;
    std::cout << "Next valid order id: " << orderId_ << "\n";
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