#include <chrono>
#include <stdio.h>
#include <thread>
#include "rigtorp/SPSCQueue.h"
#include "Decimal.h"
#include "TickAttribLast.h"
#include "TickAttrib.h"

#include "core/InstrumentId.h"
#include "events/TradeTick.h"
#include "events/QuoteSnapshot.h"
#include "ibkr/IbkrClient.h"
#include "ibkr/OrionTradingContract.h"
#include "utils/TimeUtils.h"
#include "utils/LoggerInit.h"
#include "threads/TaskUtils.h"
#include "threads/Tasks.h"

enum class BenchMode
{
    UNIFORM,     // 100K/sec uniform
    BURST_MIXED, // 100K/sec avg with 4x burst spikes
    PURE_BURST   // no rate limit, max speed
};

constexpr BenchMode MODE = BenchMode::BURST_MIXED;

constexpr int     NUM_TICKS = (MODE == BenchMode::PURE_BURST) ? 10'000 : 1'000'000;
std::atomic<int>  flushCount{ 0 };
std::atomic<int>  barBuildCount{ 0 };
std::atomic<bool> producerDone{ false };

void timerThread(std::atomic<bool> &running, std::atomic<bool> &flushSignal, int64_t interval)
{
    runTimerLoop(running, flushSignal, interval);
}

// Producer thread: simulate IBKR firing callbacks as fast as possible
void producerThread(IbkrClient &client, std::atomic<bool> &flushSignal)
{
    TickAttribLast attrib{};
    TickAttrib     attribQuote{};

    // push 100,000 * 8 = 800,00 ticks out
    for (int i = 0; i < NUM_TICKS; ++i)
    {
        bool shouldFlush =
            flushSignal.load(std::memory_order_acquire); // read ONCE per outer iteration

        for (const auto &config : OrionTradingContract::kInstruments)
        {
            int64_t wakeAt = TimeUtils::steadyTime_ns();

            if constexpr (MODE == BenchMode::UNIFORM)
            {
                wakeAt += 10000LL; // 100K/sec
            }
            else if constexpr (MODE == BenchMode::BURST_MIXED)
            {
                bool isBurst = (i % 20000) < 10000; // 10K burst, 10K quiet, alternating

                wakeAt += isBurst ? 2500LL : 17500LL;
            }
            // PURE_BURST: no wait, wakeAt is already now

            // push trade tick
            client.tickByTickAllLast(
                config.tradeReqId, 1, 1700000000 + i,
                523.50 + (i % 100) * 0.01, // vary price slightly
                DecimalFunctions::doubleToDecimal(100.0), attrib, "NYSE", "");

            if (MODE != BenchMode::PURE_BURST)
            {
                while (TimeUtils::steadyTime_ns() < wakeAt)
                {
                }
            } // spin 10000ns = 100K ticks/sec

            if (shouldFlush)
            {
                client.tickPrice(config.quoteReqId, BID, 523.10 + (i % 100) * 0.01, attribQuote);
                client.tickPrice(config.quoteReqId, ASK, 523.12 + (i % 100) * 0.01, attribQuote);
                client.tickSize(
                    config.quoteReqId, BID_SIZE, DecimalFunctions::doubleToDecimal(100.0));
                client.tickSize(
                    config.quoteReqId, ASK_SIZE, DecimalFunctions::doubleToDecimal(50.0));
                flushCount++;
            }
        }
        client.flushDirtyQuotes();

        if (shouldFlush)
            flushSignal.store(false, std::memory_order_release);
    }
    producerDone.store(true, std::memory_order_release);
}

// Consumer thread: drain the queue, record latency
void consumerThread(
    rigtorp::SPSCQueue<TradeTick>     &tickBuffer,
    rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer,
    std::atomic<bool>                 &running,
    std::atomic<int>                  &quotesPushed,
    std::atomic<int>                  &ticksPushed,
    std::atomic<bool>                 &preFlushSignal,
    std::atomic<bool>                 &flushSignal,
    std::vector<int64_t>              &tickLatencies_ns,
    std::vector<int64_t>              &quoteLatencies_ns,
    MarketDataEngine                  &engine)
{
    int consumedTrades = 0;
    int consumedQuotes = 0;
    while (!producerDone.load(std::memory_order_acquire) || consumedTrades < ticksPushed.load() ||
           consumedQuotes < quotesPushed.load())
    {
        TradeTick *tick = tickBuffer.front();
        if (tick)
        {
            int64_t now = TimeUtils::steadyTime_ns();
            tickLatencies_ns.push_back(
                now - tick->recvSteadyTimestamp_ns); // how long from market ingestion to build
            engine.onTradeTick(*tick);
            tickBuffer.pop();
            ++consumedTrades;
        }

        QuoteSnapshot *quote = quoteBuffer.front();
        if (quote)
        {
            int64_t now = TimeUtils::steadyTime_ns();
            quoteLatencies_ns.push_back(now - quote->timeStamp_ns);
            engine.onQuoteSample(*quote);
            quoteBuffer.pop();
            ++consumedQuotes;
        }

        if (preFlushSignal.load(std::memory_order_acquire))
        {
            engine.preFlush();
            preFlushSignal.store(false, std::memory_order_release);
            flushSignal.store(true, std::memory_order_release);
        }
    }

    running.store(false);
}

void flushThread(
    std::atomic<bool> &flushSignal,
    MarketDataEngine  &engine,
    std::atomic<bool> &running)
{
    while (running.load(std::memory_order_relaxed))
    {
        if (flushSignal.load(std::memory_order_acquire))
        {
            int64_t boundaryId = TimeUtils::wallTime_ns() / TimeUtils::kFifteenSec_ns - 1;

            auto flushStart = TimeUtils::steadyTime_ns();
            engine.flush(boundaryId);
            auto flushTime = TimeUtils::steadyTime_ns() - flushStart;
            printf("Flush took: %ld ns\n", static_cast<long>(flushTime));

            flushSignal.store(false, std::memory_order_release);
            barBuildCount++;
        }
    }

    // drain any final pending flush
    if (flushSignal.load(std::memory_order_acquire))
    {
        int64_t boundaryId = TimeUtils::wallTime_ns() / TimeUtils::kFifteenSec_ns - 1;
        engine.flush(boundaryId);
        barBuildCount++;
    }
}

void seedReqIds(IbkrClient &client)
{
    for (auto &config : OrionTradingContract::kInstruments)
    {
        client.injectReqId(config.quoteReqId, config.instrumentId);
        client.injectReqId(config.tradeReqId, config.instrumentId);
    }
}

int main()
{
    // Used to figure out how big spscqueue should be
    int                               buffSize = 10000;
    rigtorp::SPSCQueue<TradeTick>     tradeBuffer(buffSize);
    rigtorp::SPSCQueue<QuoteSnapshot> quoteBuffer(4 * kNumInstruments);

    printf("Buffer size: %d\n", buffSize);
    printf("Number of ticks sending: %d\n", NUM_TICKS);

    std::atomic<bool> running{ true };
    std::atomic<bool> quoteSignal{ false };
    std::atomic<bool> pushSignal{ false };
    std::atomic<bool> barSignal{ false };

    IbkrClient client(tradeBuffer, quoteBuffer);

    MarketDataEngine engine;

    // start sdplog
    if (!initLogger())
    {
        printf("Starting system without logging \n");
    }

    // Add to ids to reqIdToInstrumentId_ for quote and trade tick
    seedReqIds(client);

    std::vector<int64_t> tickLatencies_ns;
    std::vector<int64_t> quoteLatencies_ns;
    tickLatencies_ns.reserve(NUM_TICKS * kNumInstruments);

    // START
    auto startTime = TimeUtils::steadyTime_ns();

    // Consumer
    std::thread timer250msThread(
        timerThread, std::ref(running), std::ref(quoteSignal),
        TimeUtils::kTwoHundredFiftyMiliSec_ns);
    std::thread timer15sThread(
        timerThread, std::ref(running), std::ref(barSignal), TimeUtils::kFifteenSec_ns);
    std::thread engineThread = std::thread(
        consumerThread, std::ref(tradeBuffer), std::ref(quoteBuffer), std::ref(running),
        std::ref(client.quotesPushed), std::ref(client.ticksPushed), std::ref(barSignal),
        std::ref(pushSignal), std::ref(tickLatencies_ns), std::ref(quoteLatencies_ns),
        std::ref(engine));
    std::thread barBuildThread =
        std::thread(flushThread, std::ref(pushSignal), std::ref(engine), std::ref(running));

    // Producer
    std::thread mockDataThread(producerThread, std::ref(client), std::ref(quoteSignal));

    while (running.load(std::memory_order_relaxed))
    {
    }

    // END
    auto endTime = TimeUtils::steadyTime_ns();

    engineThread.join();
    timer250msThread.join();
    timer15sThread.join();
    barBuildThread.join();
    mockDataThread.join();

    /* --------------------------------- Results -------------------------------- */

    double totalMs         = (endTime - startTime) / 1e6;
    double tickThroughput  = (NUM_TICKS * kNumInstruments) / (totalMs / 1000.0);
    double quoteThroughput = (quoteLatencies_ns.size()) / (totalMs / 1000.0);

    // printf("First 20 tick latencies (ns):\n"); // debugging
    // for (size_t i = 0; i < 20 && i < tickLatencies_ns.size(); ++i)
    //     printf("  %ld\n", static_cast<long>(tickLatencies_ns[i]));

    // printf("First 20 quote latencies (ns):\n");
    // for (size_t i = 0; i < 20 && i < quoteLatencies_ns.size(); ++i)
    //     printf("  %ld\n", static_cast<long>(quoteLatencies_ns[i]));

    /* -------------------------------- Tick Data ------------------------------- */
    if (!tickLatencies_ns.empty())
    {
        std::sort(tickLatencies_ns.begin(), tickLatencies_ns.end());
        size_t idx_p50 = static_cast<size_t>(tickLatencies_ns.size() * 0.50);
        size_t idx_p99 = static_cast<size_t>(tickLatencies_ns.size() * 0.99);

        printf("Total Time:      %.2f ms\n", totalMs);
        printf("Tick throughput: %.0f ticks/sec\n", tickThroughput);
        printf("Tick latency p50: %ld ns\n", static_cast<long>(tickLatencies_ns[idx_p50]));
        printf("Tick latency p99: %ld ns\n", static_cast<long>(tickLatencies_ns[idx_p99]));
        printf("Tick latency max: %ld ns\n", static_cast<long>(tickLatencies_ns.back()));
        printf("Tick dropped packets: %d \n", client.droppedTicks.load());
        printf("Total tick pushed: %d \n", client.ticksPushed.load());
    }
    else
    {
        printf("Tick latency: no data\n");
    }

    /* ------------------------------- Quote Data ------------------------------- */
    if (!quoteLatencies_ns.empty())
    {
        size_t idxQ_p50 = static_cast<size_t>(quoteLatencies_ns.size() * 0.50);
        size_t idxQ_p99 = static_cast<size_t>(quoteLatencies_ns.size() * 0.99);

        printf("Quote throughput: %.0f quotes/sec\n", quoteThroughput);
        printf("Quote latency p50: %ld ns\n", static_cast<long>(quoteLatencies_ns[idxQ_p50]));
        printf("Quote latency p99: %ld ns\n", static_cast<long>(quoteLatencies_ns[idxQ_p99]));
        printf("Quote latency max: %ld ns\n", static_cast<long>(quoteLatencies_ns.back()));
        printf("Quote dropped packets: %d \n", client.droppedQuotes.load());

        printf("Quotes pushed: %d\n", client.quotesPushed.load());
        printf("Quotes consumed: %zu\n", quoteLatencies_ns.size());
        printf("Quote dropped packets: %d\n", client.droppedQuotes.load());
        printf("Flush count %d\n", flushCount.load());
    }
    else
    {
        printf("Quote latency: no data\n");
    }

    printf("Bars built: %d\n", barBuildCount.load());

    // TODO: clean up pring after upgrading to C++ 23

    return 0;
}