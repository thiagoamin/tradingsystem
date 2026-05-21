#include <iostream>

#include "DefaultEWrapper.h"
#include "EClientSocket.h"
#include "EReaderOSSignal.h"
#include "EReader.h"

class TestWrapper : public DefaultEWrapper
{
public:
    void error(int id, time_t errorTime, int errorCode,
               const std::string &errorString,
               const std::string &advancedOrderRejectJson) override
    {
        if (errorCode == 2104 || errorCode == 2106 || errorCode == 2158)
        {
            std::cout << "Info: " << errorString << std::endl;
            return;
        }

        std::cout << "Error. Id: " << id
                  << ", Code: " << errorCode
                  << ", Msg: " << errorString << std::endl;
    }

    void connectAck() override
    {
        std::cout << "Connected ACK" << std::endl;
    }

    void nextValidId(OrderId orderId) override
    {
        std::cout << "Next valid order id: " << orderId << std::endl;
    }

    void connectionClosed() override
    {
        std::cout << "Connection closed" << std::endl;
    }
};

int main()
{
    TestWrapper wrapper;
    EReaderOSSignal signal(2000);
    EClientSocket client(&wrapper, &signal);

    const char *host = "127.0.0.1";
    int port = 7497;
    int clientId = 0;

    if (!client.eConnect(host, port, clientId))
    {
        std::cerr << "Failed to connect to TWS" << std::endl;
        return 1;
    }

    std::cout << "Connected to TWS" << std::endl;

    EReader reader(&client, &signal);
    reader.start();

    while (client.isConnected())
    {
        std::cout << "waiting..." << std::endl;
        signal.waitForSignal();

        std::cout << "processing msgs..." << std::endl;
        reader.processMsgs();

        static bool requestedIds = false;
        if (!requestedIds)
        {
            client.reqIds(-1);
            requestedIds = true;
            std::cout << "Requested order ids" << std::endl;
        }
    }

    client.eDisconnect();
    std::cout << "Disconnected" << std::endl;
    return 0;
}