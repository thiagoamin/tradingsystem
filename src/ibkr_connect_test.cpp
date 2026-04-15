#include <iostream>
#include <thread>
#include <chrono>

#include "DefaultEWrapper.h"
#include "EClientSocket.h"
#include "EReaderOSSignal.h"

class TestWrapper : public DefaultEWrapper
{
public:
    void error(int id, time_t errorTime, int errorCode, const std::string &errorString, const std::string &advancedOrderRejectJson) override
    {
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
};

int main()
{
    TestWrapper wrapper;
    EReaderOSSignal signal(2000);
    EClientSocket client(&wrapper, &signal);

    const char *host = "127.0.0.1";
    int port = 7497;
    int clientId = 0;

    bool connected = client.eConnect(host, port, clientId);
    if (!connected)
    {
        std::cerr << "Failed to connect to TWS" << std::endl;
        return 1;
    }

    std::cout << "Connected to TWS" << std::endl;

    client.reqIds(-1);

    std::this_thread::sleep_for(std::chrono::seconds(5));

    client.eDisconnect();
    std::cout << "Disconnected" << std::endl;
    return 0;
}