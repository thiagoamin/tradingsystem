# Benchmarks

Microbenchmarks for hot-path components in the ingestion and transform pipelines. Run via the `bench-release` CMake preset for representative numbers (debug info stripped) and `bench-debug` for testing bench code.

```bash
cmake --preset bench-release
cmake --build --preset bench-release --parallel
./build_bench_release/benchmark/<binary>
```

## Environment

| | |
|---|---|
| Hardware | [CPU model, cores, clock speed] |
| OS | [macOS version / Linux distro if run in CI/ Linux host later on] |
| Compiler | [Clang/GCC version] |
| Date measured | [date — numbers should be re-run and dated as code changes] |

## Market Bench

| Metric | p50 | p99 | Notes |
|---|---|---|---|
| Tick → bar latency | X µs | X µs | 15s bar window, N ticks/sec load |
| SPSC enqueue latency | X ns | X ns | |
| SPSC dequeue latency | X ns | X ns | |
| Buffer swap cost | X ns | X ns | double-buffer, dirty-flag design |
| Sustained throughput | X msgs/sec | | before queue backpressure |

## Transform layer

| Metric | p50 | p99 | Notes |
|---|---|---|---|
| Rolling OLS update (per bar) | X ns | X ns | window = N, factors = M |
| Residualization (per bar) | X ns | X ns | |

## Design rationale

- **SPSC queue depth = N**: chosen because [reasoning — e.g. beyond N, tail latency degraded due to cache pressure / below N, producer stalls under burst load]
- **Double-buffer vs. single-buffer + lock**: [reasoning — e.g. avoids lock contention on engine thread at cost of 2x memory for bar state]
- **`std::array` vs. `unordered_map` for instrument lookup**: [reasoning — e.g. O(1) with no hashing overhead, fixed known instrument set]
- **Ring buffer for rolling OLS window**: [reasoning — avoids reallocation, O(1) amortized update]

## Known bottlenecks / tradeoffs

- [Anything not yet optimized, or a deliberate tradeoff — e.g. "residualization is currently single-threaded across instruments; parallelizing is on the roadmap"]