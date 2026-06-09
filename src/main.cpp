#include <thread>
#include <format>
#include <spdlog/async.h>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/rotating_file_sink.h>

#include "utils/TimeUtils.h"
#include "ibkr/IbkrClient.h"
#include "market_data/MarketDataEngine.h"

const unsigned MAX_ATTEMPTS = 5;
const unsigned SLEEP_TIME   = 3;

int main()
{
    // Initialize market data engine and client
    MarketDataEngine marketDataEngine;
    IbkrClient       client(marketDataEngine);
    const char      *host     = "127.0.0.1";
    int              port     = 7497;
    int              clientId = 0;

    // Initialize time ET
    TimeUtils::init();

    unsigned attempt = 0;

    // Initialize logger
    std::string log_path = std::format("logs/orion_{}.log", getCurrentDate());

    // Start SPD logger
    auto logger = spdlog::create_async<spdlog::sinks::rotating_file_sink_mt>(
        "orion", log_path, 1024 * 1024 * 10, 3); // mutex but not on hot path, runs async
    spdlog::set_default_logger(logger);

    for (;;)
    {
        ++attempt;
        spdlog::info(
            "Connection attempt {}/{} | client: {}, host: {}, port: {}", attempt, MAX_ATTEMPTS,
            clientId, host, port);

        client.connect(host, port, clientId);

        if (attempt >= MAX_ATTEMPTS)
        {
            spdlog::warn("Max connection attempts {} reached, ending session", MAX_ATTEMPTS);
            break;
        }

        // Main connection
        while (client.isConnected())
        {
            client.run();
        }

        spdlog::info("Sleeping {} seconds before next attempt", SLEEP_TIME);
        std::this_thread::sleep_for(std::chrono::seconds(SLEEP_TIME));
    }

    spdlog::info("End of Session");

    return 0;
}