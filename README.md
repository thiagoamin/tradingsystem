# Quantitative Trading System

This repository is building a modular algorithmic trading platform with two main execution modes:

- **Research/Backtesting** on historical data in Python 🐍.
- **Paper trading / live trading infrastructure** in C++20 ⚙️ using Interactive Brokers (IBKR).

## Architecture

1. Ingest market data.
2. Compute features/indicators.
3. Generate signal events.
4. Translate signals into target position actions.
5. Apply risk controls.
6. Execute orders and update the portfolio.

## Status

| Layer | Language | Status |
|---|---|---|
| Ingestion (IBKR ticks → bars) | C++20 | ✅ Done |
| Feature transforms (rolling OLS, residualization) | C++20 | 🚧 In progress |
| Strategy / signal generation | C++20 | ⏳ Planned |
| Execution / order routing | C++20 | ⏳ Planned |
| Research pipeline #1 (backtesting, predictors) | Python | ✅ Done |
| Research pipeline #2 (backtesting, predictors) | Python | 🚧 In progress |


## Research Infrastructure
- `research/fetchers/` - provider-specific ingestion and local storage, currently mainly ThetaData EOD/intraday fetchers, downloaders, audit logs, and cache writers.
- `research/tools/` - reusable Python research framework: data sources, processing, contracts, transformers, predictors, strategies, backtests, splits, metrics, and evaluation.
- `research/tools/contracts/` - declarative contracts for required data, variables, components, train/inference inputs, and strategy outputs.
- `research/tools/data/` - pluggable research data sources, including cache-first and ThetaData-backed daily panel sources.
- `research/tools/processing/` - raw data to research panels, currently daily EOD close/volume/return panels and split adjustment logic.
- `research/tools/transformer/` - transformations such as factor residualization, residual state features, and OU mean-reversion state.
- `research/tools/predictor/` - forecasting models, including residual regime predictors.
- `research/tools/strategy/` - strategy signal logic, including OU s-score and hybrid residual strategies.
- `research/tools/backtest/`, `research/tools/metrics/`, `research/tools/evaluation/` - simulation, performance metrics, and attribution.
- `research/experiments/` - experiment entry points, paper replications, diagnostics, walk-forward tests, and strategy comparisons.
- `research/theory/` and `research/experiments/*/theory/` - LaTeX theory notes and replication plans.
- `research/raw_data_cache/` - local cached raw/derived data; git-ignored.
- `research/experiment_outputs/` - generated experiment outputs and diagnostics; git-ignored.


## C++ Paper/ Live Trading Infrastructure
- `src/ibkr/` — IBKR API integration, tick callback wrapping
- `src/market_data/` — tick ingestion, bar construction (double-buffered, SPSC-queued)
- `src/transform/` — streaming feature computation (rolling OLS, residualization)
- `src/strategy/` — signal generation *(planned)*
- `src/execution/` — order routing and portfolio updates *(planned)*
- `src/core/` — shared types/utilities across layers
- `src/utils/` — shared utility code (logging, time handling, etc.)
- `test/` — gtest unit + integration tests
- - `third_party/` — vendored/external dependencies
- `bench/` — microbenchmarks for hot-path components (queue throughput, buffer swap latency, feature computation cost); results and design rationale documented in [`bench/README.md`](benchmark/README.md)

## Build

This project uses CMake presets for different build configurations:

| Preset | Purpose |
|---|---|
| `dev` | Local development build (debug symbols, fast iteration) |
| `bench-debug` | Benchmarking with debug info retained |
| `bench-release` | Optimized build for latency/throughput benchmarking |
| `prod` | Production build (full optimizations) |
| `test` | Build + run gtest suite |

```bash
cmake --preset <preset-name>
cmake --build --preset <preset-name>
```

### Platform status

Currently developed on macOS with **target deployment platform in Linux** since production trading infrastructure will run on a Linux host. CI runs on Linux (GitHub Actions), giving continuous verification that the project builds and passes tests on the target platform even without local Linux dev access.

## Dependencies

**Environment**
- Protobuf 3.12.4
- libbid (Intel RDFP Math Library — decimal floating-point arithmetic for price/quantity precision)
- Clang 14+ (developed against Clang 22)
- GCC 13+ (required for full C++20 support)

**Third-party (direct)**
- IBKR TWS API 10.37

**Libraries / submodules**
- spdlog — logging
- [rigtorp/SPSCQueue](https://github.com/rigtorp/SPSCQueue) — lock-free single-producer/single-consumer queue used for LL

### Getting dependencies

Most dependencies are vendored as git submodules:

```bash
git clone --recurse-submodules <repo-url>
```

If already cloned without submodules:

```bash
git submodule update --init
```

**Protobuf** and **libbid** are installed outside the submodule tree:
- On Phi's macOS (dev): Protobuf via `brew install protobuf`; libbid is not directly buildable on macOS, so a prebuilt `libbid.dylib` (bundled with the IBKR client) is used instead, referenced via `DYLD_LIBRARY_PATH` in `.vscode/settings.json`:
```jsonc
  "DYLD_LIBRARY_PATH": "${workspaceFolder}/third_party/ibkr_10.37/source/cppclient/client/lib"
```
- On Linux (CI): both are built from source into a prebuilt CI image so CI runs don't rebuild them on every push. This is done to minimize build times by **76%** from 6:20 to 1:32.

### Compiler requirements

C++20 support requires:
- Clang 14+
- GCC 13+

## Dev Tooling & CI

- **Formatting**: custom Python wrapper around `clang-format` — [`scripts/utilities/fix_formatting.py`](scripts/utilities/fix_formatting.py)
- **Editor config**: VS Code `launch.json`, `tasks.json`, and `settings.json` under `.vscode/` for consistent build, run, and debug configuration across contributors, including platform-specific library paths (e.g. `DYLD_LIBRARY_PATH` for macOS)
- **CI**: GitHub Actions, running on every pull request:
  1. **Format check** — runs `fix_formatting.py` (Clang 22) and fails if it produces a diff
  2. **Build** — builds the `prod` preset inside a prebuilt Linux container image with dependencies (Protobuf, libbid) preinstalled
  3. **Test** — builds the `test` preset and runs the full `ctest` suite

  See [`.github/workflows/`](.github/workflows/) for the full pipeline and [`Dockerfile`](Dockerfile) for the CI image definition.

<details>
<summary>Dockerfile (CI image — prebuilds Protobuf and libbid for Linux)</summary>

```dockerfile
FROM --platform=linux/amd64 ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    python3 \
    python3-pip \
    valgrind \
    autoconf \
    automake \
    libtool \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Protobuf 3.12.4
RUN wget https://github.com/protocolbuffers/protobuf/releases/download/v3.12.4/protobuf-cpp-3.12.4.tar.gz && \
    tar -xzf protobuf-cpp-3.12.4.tar.gz && \
    cd protobuf-3.12.4 && \
    ./configure && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    cd / && \
    rm -rf protobuf-3.12.4 protobuf-cpp-3.12.4.tar.gz

# Install libbid
RUN git clone https://github.com/xmake-mirror/IntelRDFPMathLib.git && \
    cd IntelRDFPMathLib/LIBRARY && \
    make CC=gcc && \
    cp libbid.a /usr/local/lib/ && \
    cd / && \
    rm -rf IntelRDFPMathLib

WORKDIR /workspace
```

</details>
