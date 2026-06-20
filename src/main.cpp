#include <thread>
#include <atomic>
#include <format>
#include <filesystem>
#include <spdlog/async.h>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include "rigtorp/SPSCQueue.h"

#include "utils/TimeUtils.h"
#include "ibkr/IbkrClient.h"
#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "market_data/MarketDataEngine.h"

const unsigned MAX_ATTEMPTS = 5;
const unsigned SLEEP_TIME   = 3;

rigtorp::SPSCQueue<TradeTick>     tickBuffer(4096);
rigtorp::SPSCQueue<QuoteSnapshot> quoteBuffer(64);
std::atomic<bool>                 running{ true };
std::atomic<bool>                 flushSignal{ false };

void timerTask()
{
    while (running.load(std::memory_order_relaxed))
    {
        // calculate next 15s boundary
        auto now_ns = TimeUtils::wall_time_ns();

        int64_t next_boundary = (now_ns / TimeUtils::kFifteenSec_ns + 1) *
                                TimeUtils::kFifteenSec_ns; // start at boundary 15s instead of 0
        int64_t sleep_ns      = next_boundary - now_ns;

        std::this_thread::sleep_for(std::chrono::nanoseconds(sleep_ns));
        flushSignal.store(true, std::memory_order_release);
    }
}

void engineTask()
{
    MarketDataEngine marketDataEngine;

    while (running.load(std::memory_order_relaxed))
    {
        if (flushSignal.load(std::memory_order_acquire))
        {
            int64_t boundaryId = TimeUtils::wall_time_ns() / TimeUtils::kFifteenSec_ns - 1;
            marketDataEngine.flush(boundaryId);
            flushSignal.store(false, std::memory_order_release);
        }

        TradeTick *tick = tickBuffer.front();
        if (tick)
        {
            marketDataEngine.onTradeTick(*tick);
            tickBuffer.pop();
        }

        QuoteSnapshot *quote = quoteBuffer.front();
        if (quote)
        {
            marketDataEngine.onQuoteSample(*quote);
            quoteBuffer.pop();
        }
    }
}

int main()
{
    // Initialize time ET
    TimeUtils::init();

    // Initialize logger
    spdlog::init_thread_pool(8192, 1);
    std::filesystem::create_directories("logs");
    std::string log_path = std::format("logs/orion_{}.log", TimeUtils::getCurrentDate());
    auto        logger   = spdlog::create_async<spdlog::sinks::rotating_file_sink_mt>(
        "orion", log_path, 1024 * 1024 * 10, 3); // mutex but not on hot path, runs async
    spdlog::set_default_logger(logger);

    // Initialize client
    IbkrClient  client(tickBuffer, quoteBuffer);
    const char *host     = "127.0.0.1";
    int         port     = 7497;
    int         clientId = 0;

    // Engine thread (#1)
    std::thread engine_thread(engineTask);

    // Timer thread (#2)
    std::thread timer_thread(timerTask);

    unsigned attempt = 0;

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
    spdlog::shutdown();

    // end threads
    running.store(false);

    // wait for tasks to return
    engine_thread.join();
    timer_thread.join();

    return 0;
}