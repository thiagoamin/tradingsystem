#include "rigtorp/SPSCQueue.h"

#include "utils/TimeUtils.h"
#include "utils/LoggerInit.h"
#include "ibkr/IbkrClient.h"
#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "market_data/MarketDataEngine.h"
#include "threads/Tasks.h"

const unsigned MAX_ATTEMPTS = 5;
const unsigned SLEEP_TIME   = 3;

int main()
{
    // Initialize time ET
    TimeUtils::init();

    rigtorp::SPSCQueue<TradeTick>     tickBuffer(10000);
    rigtorp::SPSCQueue<QuoteSnapshot> quoteBuffer(32);
    MarketDataEngine                  engine;

    // Initialize logger
    if (!initLogger())
    {
        printf("Starting system without logging \n");
    }

    // Initialize client
    IbkrClient  client(tickBuffer, quoteBuffer);
    const char *host     = "127.0.0.1";
    int         port     = 7497;
    int         clientId = 0;

    // Initialize and start thread
    Tasks tasks(engine, tickBuffer, quoteBuffer);
    tasks.start();

    unsigned attempt = 0;

    // TODO: handle thread, ibkr, etc if exception thrown
    // TOOD: add manual shutdown
    for (;;)
    {
        ++attempt;
        spdlog::info("Starting session, attempt number {}/{}", attempt, MAX_ATTEMPTS);

        client.connect(host, port, clientId);

        if (attempt >= MAX_ATTEMPTS)
        {
            spdlog::warn("Max connection attempts {} reached, ending session", MAX_ATTEMPTS);
            break;
        }

        // Main connection
        while (client.isConnected())
        {
            client.run(); // Tick ingestion thread (#3)
        }

        spdlog::info("Sleeping {} seconds before next attempt", SLEEP_TIME);
        std::this_thread::sleep_for(std::chrono::seconds(SLEEP_TIME));
    }

    spdlog::warn("Ending session");

    // End threads
    tasks.stop();

    // End client connection
    client.disconnect();

    // End log
    spdlog::shutdown();

    return 0;
}