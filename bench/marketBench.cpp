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
#include "utils/TimeUtils.h"
#include "utils/LoggerInit.h"
#include "threads/TaskUtils.h"
#include "threads/Tasks.h"

constexpr int NUM_TICKS = 100'000;
#define THROUGHPUT_ONLY 1
std::atomic<int> quoteCount{ 0 };

// all reqIds mapped to instruments
const std::vector<std::pair<TickerId, InstrumentId>> kTradeReqIds = {
    { 20001, InstrumentId::SPY },   { 20002, InstrumentId::QQQ },  { 20003, InstrumentId::TSLA },
    { 20004, InstrumentId::AAPL },  { 20005, InstrumentId::MSFT }, { 20006, InstrumentId::NVDA },
    { 20007, InstrumentId::GOOGL }, { 20008, InstrumentId::AMZN },
};

const std::vector<std::pair<TickerId, InstrumentId>> kQuoteReqIds = {
    { 1001, InstrumentId::SPY },   { 1002, InstrumentId::QQQ },  { 1003, InstrumentId::TSLA },
    { 1004, InstrumentId::AAPL },  { 1005, InstrumentId::MSFT }, { 1006, InstrumentId::NVDA },
    { 1007, InstrumentId::GOOGL }, { 1008, InstrumentId::AMZN },
};

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
        for (auto &[reqId, _] : kTradeReqIds)
        {
            // push trade tick
            client.tickByTickAllLast(
                reqId, 1, 1700000000 + i,
                523.50 + (i % 100) * 0.01, // vary price slightly
                DecimalFunctions::doubleToDecimal(100.0), attrib, "NYSE", "");

            if (flushSignal.load(std::memory_order_acquire))
            {
                client.tickPrice(reqId, BID, 523.10 + (i % 100) * 0.01, attribQuote);
                client.tickPrice(reqId, ASK, 523.12 + (i % 100) * 0.01, attribQuote);
                client.tickSize(reqId, BID_SIZE, DecimalFunctions::doubleToDecimal(100.0));
                client.tickSize(reqId, ASK_SIZE, DecimalFunctions::doubleToDecimal(50.0));
                quoteCount++;
            }
        }
        flushSignal.store(false, std::memory_order_release);
    }
}
#if THROUGHPUT_ONLY
// Consumer thread: drain the queue, record latency
void consumerThread(
    rigtorp::SPSCQueue<TradeTick>     &tickBuffer,
    rigtorp::SPSCQueue<QuoteSnapshot> &quoteBuffer,
    std::atomic<bool>                 &running,
    std::vector<int64_t>              &tickLatencies_ns,
    std::vector<int64_t>              &quoteLatencies_ns)
{
    int consumedTrades = 0;
    int consumedQuotes = 0;
    while (consumedTrades < NUM_TICKS * kTradeReqIds.size() || consumedQuotes < quoteCount.load())
    {
        TradeTick *tick = tickBuffer.front();
        if (tick)
        {
            int64_t now = TimeUtils::steadyTime_ns();
            tickLatencies_ns.push_back(
                now - tick->recvSteadyTimestamp_ns); // how long from market ingestion to build
            tickBuffer.pop();
            ++consumedTrades;
        }

        QuoteSnapshot *quote = quoteBuffer.front();
        if (quote)
        {
            int64_t now = TimeUtils::steadyTime_ns();
            quoteLatencies_ns.push_back(now - quote->timeStamp_ns);
            quoteBuffer.pop();
            ++consumedQuotes;
        }
    }

    running.store(false);
}
#endif

void seedReqIds(IbkrClient &client)
{
    for (auto &[reqId, instrId] : kTradeReqIds)
        client.injectReqId(reqId, instrId);
    for (auto &[reqId, instrId] : kQuoteReqIds)
        client.injectReqId(reqId, instrId);
}

int main()
{
    // Used to figure out how big spscqueue should be
    rigtorp::SPSCQueue<TradeTick>     tradeBuffer(1 << 20);
    rigtorp::SPSCQueue<QuoteSnapshot> quoteBuffer(1 << 20);

    std::atomic<bool> running{ true };
    std::atomic<bool> quoteSignal{ false };

    IbkrClient client(tradeBuffer, quoteBuffer);
    printf("droppedQuotes initial: %d\n", client.droppedQuotes.load());
    printf("droppedTicks initial: %d\n", client.droppedTicks.load());

    // start sdplog
    if (!initLogger())
    {
        printf("Starting system without logging \n");
    }

    // Add to ids to reqIdToInstrumentId_ for quote and trade tick
    seedReqIds(client);

    std::vector<int64_t> tickLatencies_ns;
    std::vector<int64_t> quoteLatencies_ns;
    tickLatencies_ns.reserve(NUM_TICKS * kTradeReqIds.size());

    // START
    auto startTime = TimeUtils::steadyTime_ns();

    // Consumer
    std::thread timer250msThread(
        timerThread, std::ref(running), std::ref(quoteSignal),
        TimeUtils::kTwoHundredFiftyMiliSec_ns);
    std::thread engineThread;

    MarketDataEngine engine;

#if THROUGHPUT_ONLY

    engineThread = std::thread(
        consumerThread, std::ref(tradeBuffer), std::ref(quoteBuffer), std::ref(running),
        std::ref(tickLatencies_ns), std::ref(quoteLatencies_ns));
#else
    Tasks tasks(engine, tradeBuffer, quoteBuffer);
    tasks.start();
#endif

    // Producer
    std::thread mockDataThread(producerThread, std::ref(client), std::ref(quoteSignal));

    while (running.load(std::memory_order_relaxed))
    {
    }

    // END
    auto endTime = TimeUtils::steadyTime_ns();

#if THROUGHPUT_ONLY
    engineThread.join();
#else
    tasks.stop();
#endif
    timer250msThread.join();
    mockDataThread.join();

    /* --------------------------------- Results -------------------------------- */

    double totalMs         = (endTime - startTime) / 1e6;
    double tickThroughput  = (NUM_TICKS * kTradeReqIds.size()) / (totalMs / 1000.0);
    double quoteThroughput = (quoteLatencies_ns.size()) / (totalMs / 1000.0);

    /* -------------------------------- Tick Data ------------------------------- */
    std::sort(tickLatencies_ns.begin(), tickLatencies_ns.end());
    size_t idx_p50 = static_cast<size_t>(tickLatencies_ns.size() * 0.50);
    size_t idx_p99 = static_cast<size_t>(tickLatencies_ns.size() * 0.99);

    printf("Total Time:      %.2f ms\n", totalMs);
    printf("Tick throughput: %.0f ticks/sec\n", tickThroughput);
    printf("Tick latency p50: %ld ns\n", static_cast<long>(tickLatencies_ns[idx_p50]));
    printf("Tick latency p99: %ld ns\n", static_cast<long>(tickLatencies_ns[idx_p99]));
    printf("Tick latency max: %ld ns\n", static_cast<long>(tickLatencies_ns.back()));
    printf("Tick dropped packets: %d \n", client.droppedTicks.load());

    /* ------------------------------- Quote Data ------------------------------- */
    size_t idxQ_p50 = static_cast<size_t>(quoteLatencies_ns.size() * 0.50);
    size_t idxQ_p99 = static_cast<size_t>(quoteLatencies_ns.size() * 0.99);

    printf("Quote throughput: %.0f quotes/sec\n", quoteThroughput);
    printf("Quote latency p50: %ld ns\n", static_cast<long>(quoteLatencies_ns[idxQ_p50]));
    printf("Quote latency p99: %ld ns\n", static_cast<long>(quoteLatencies_ns[idxQ_p99]));
    printf("Quote latency max: %ld ns\n", static_cast<long>(quoteLatencies_ns.back()));
    printf("Quote dropped packets: %d \n", client.droppedQuotes.load());

    printf("Quotes pushed: %d\n", quoteCount.load());
    printf("Quotes consumed: %zu\n", quoteLatencies_ns.size());
    printf("Quote dropped packets: %d\n", client.droppedQuotes.load());

    return 0;
}