#include <thread>

#include "ibkr/IbkrClient.h"
#include "market_data/MarketDataEngine.h"

const unsigned MAX_ATTEMPTS = 5;
const unsigned SLEEP_TIME = 3;

int main()
{
    MarketDataEngine marketDataEngine;
    IbkrClient client(marketDataEngine);
    const char* host = "127.0.0.1";
    int port = 7497;
    int clientId = 0;

    unsigned attempt = 0;

    for (;;)
    {
        ++attempt;

        client.connect(host, port, clientId);

        while (client.isConnected())
        {
            client.run();
        }

        if (attempt > MAX_ATTEMPTS)
        {
            printf("Max connection attempts #%d ran, ending session\n", MAX_ATTEMPTS);
            break;
        }

        printf("Sleeping %u seconds before next attempt\n", SLEEP_TIME);
        std::this_thread::sleep_for(std::chrono::seconds(SLEEP_TIME));
    }

    printf("End of Session\n");

    return 0;
}