# Quantitative Trading System

This repository is building a modular algorithmic trading platform with two main execution modes:

- **Backtesting** on historical data in Python 🐍.
- **Paper trading / live trading infrastructure** in C++ ⚙️ using Interactive Brokers (IBKR).

The core architecture is:

1. Ingest market data.
2. Compute features/indicators.
3. Generate signal events.
4. Translate signals into target position actions.
5. Apply risk controls.
6. Execute orders and update the portfolio.

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
- `src/` - core C++ trading infrastructure
- `src/ibkr` - integrates our system with ibkr and wraps ibkr data callbacks
- `src/market_data` - market data ingestion
- `src/execution` - where execution pipelines will lie
- `src/core` - shared core logic between the layers
- `src/test` - gtest unit testing logic and e2e testing


